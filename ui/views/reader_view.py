"""PDF reader: interactive PDF via QWebEngineView + PDF.js.

Accessibility-first:
- PDF is rendered by PDF.js in a QWebEngineView — identical to Firefox.
- Text is selectable directly on the PDF canvas (no separate extraction panel).
- Annotations are written into the working-copy PDF via PyMuPDF and rendered
  natively by PDF.js on subsequent page loads.
- Right-click on selected text → Highlight / Underline / Strikeout / Create card.
- Right-click on an annotation → Edit comment / Create card / Delete.
- Notes and Dictionary tool panes stay accessible at all times.
- Layout is adaptive: all three panes are resizable and independently collapsible.
"""

from __future__ import annotations

import base64
import html
import json
import os
from dataclasses import dataclass

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QKeySequence,
    QShortcut,
    QShowEvent,
    QTextDocument,
)
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from data.models.source import SourceDocument
from domain.sources import render_service
from domain.sources.annotation_service import AnnotationService
from domain.sources.source_service import SourceService
from ui.theme.tokens import PALETTES
from ui.views.note_form import AddNoteDialog
from ui.views.pdf_bridge import PdfBridge

_HIGHLIGHT_COLORS: list[tuple[str, str]] = [
    ("Yellow", "#ffd43b"),
    ("Green", "#b2f2bb"),
    ("Blue", "#a5d8ff"),
    ("Pink", "#ffc9c9"),
    ("Orange", "#ffd8a8"),
]

_VIEWER_HTML = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "assets", "pdf_viewer", "viewer.html",
)


@dataclass
class _SplitterMemory:
    sizes: list[int] | None = None
    user_adjusted: bool = False

    def mark_adjusted(self, sizes: list[int]) -> None:
        if sizes and sum(sizes) > 0:
            self.sizes = list(sizes)
            self.user_adjusted = True

    def restore(self, splitter: QSplitter) -> bool:
        if self.sizes and sum(self.sizes) > 0:
            splitter.setSizes(self.sizes)
            return True
        return False


def merge_line_rects(rects: list[dict]) -> list[dict]:
    """Collapse per-span normalised rects into one rect per visual line.

    Mirrors mergeLineRects() in viewer-bridge.js — both use the same 60 %
    vertical-center threshold so Python and JS produce identical results.
    Called in _rects_to_quads() as defense-in-depth after the JS merge.
    """
    if len(rects) <= 1:
        return list(rects)
    ordered = sorted(rects, key=lambda r: (r["y0"], r["x0"]))
    merged: list[dict] = []
    cur = dict(ordered[0])
    for r in ordered[1:]:
        cur_mid = (cur["y0"] + cur["y1"]) / 2
        r_mid   = (r["y0"]  + r["y1"])  / 2
        line_h  = max(cur["y1"] - cur["y0"], r["y1"] - r["y0"])
        if line_h > 0 and abs(r_mid - cur_mid) < line_h * 0.6:
            cur["x0"] = min(cur["x0"], r["x0"])
            cur["x1"] = max(cur["x1"], r["x1"])
            cur["y0"] = min(cur["y0"], r["y0"])
            cur["y1"] = max(cur["y1"], r["y1"])
        else:
            merged.append(cur)
            cur = dict(r)
    merged.append(cur)
    return merged


class ReaderView(QWidget):
    finished = pyqtSignal()

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setObjectName("Page")
        self.setAccessibleName("PDF reader")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._session = None
        self._service: SourceService | None = None
        self._source_id: int | None = None
        self._source: SourceDocument | None = None
        self._source_kind = "pdf"
        self._file_path = ""
        self._page = 1
        self._page_count = 1
        self._zoom = 1.5
        self._hl_filter_color: str | None = None

        # PDF viewer state — all None until _ensure_webview() runs
        self._webview: QWebEngineView | None = None
        self._channel: QWebChannel | None = None
        self._bridge: PdfBridge = PdfBridge(self)  # created early (pure QObject)
        self._viewer_ready = False
        self._pdf_loaded_in_viewer = False
        self._pending_pdf_load = False
        self._webview_inited = False  # True once _ensure_webview() has run

        self._side_visible = True
        self._tools_visible = True
        self._side_memory = _SplitterMemory()
        self._tools_memory = _SplitterMemory()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_topbar())

        self._reader_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._reader_splitter.setObjectName("ReaderMainSplitter")
        self._reader_splitter.addWidget(self._build_side_panel())
        self._reader_splitter.addWidget(self._build_pdf_pane())
        self._tabs = self._build_tool_tabs()
        self._reader_splitter.addWidget(self._tabs)

        self._reader_splitter.setChildrenCollapsible(False)
        self._reader_splitter.setCollapsible(0, True)
        self._reader_splitter.setCollapsible(1, False)
        self._reader_splitter.setCollapsible(2, True)
        self._reader_splitter.setHandleWidth(6)
        self._reader_splitter.splitterMoved.connect(self._on_reader_splitter_moved)
        self._tabs.currentChanged.connect(self._on_tool_tab_changed)

        self._layout_initialized = False
        self._restore_or_default_splitters()
        root.addWidget(self._reader_splitter, 1)

        self._notes_timer = QTimer(self)
        self._notes_timer.setSingleShot(True)
        self._notes_timer.setInterval(500)
        self._notes_timer.timeout.connect(self._save_notes)

        toggle_side = QShortcut(QKeySequence("Ctrl+Shift+O"), self)
        toggle_side.activated.connect(self._toggle_side_panel)
        toggle_tools = QShortcut(QKeySequence("Ctrl+Shift+T"), self)
        toggle_tools.activated.connect(self._toggle_tools_panel)
        fit_sc = QShortcut(QKeySequence("Ctrl+0"), self)
        fit_sc.activated.connect(self._fit_width)
        prev_sc = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        prev_sc.activated.connect(lambda: self._go(self._page - 1))
        next_sc = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        next_sc.activated.connect(lambda: self._go(self._page + 1))

        # 1–5 keys pick the annotation color (useful before right-clicking)
        for _i in range(len(_HIGHLIGHT_COLORS)):
            def _make_slot(idx: int = _i):  # noqa: ANN202
                return lambda: self._color_combo.setCurrentIndex(idx)
            QShortcut(QKeySequence(str(_i + 1)), self).activated.connect(_make_slot())

        del_sc = QShortcut(QKeySequence(Qt.Key.Key_Delete), self._side_highlights)
        del_sc.setContext(Qt.ShortcutContext.WidgetShortcut)
        del_sc.activated.connect(self._delete_annotation_from_list)

        if self._context and getattr(self._context, "theme", None) is not None:
            self._context.theme.changed.connect(self._on_theme_changed)

        self._theme_applied_count = 0

    # ── Construction ──────────────────────────────────────────────────────────

    def _build_topbar(self) -> QWidget:
        bar_widget = QWidget()
        bar_widget.setObjectName("ReaderTopBar")
        bar_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        bar = QHBoxLayout(bar_widget)
        bar.setContentsMargins(6, 4, 6, 4)
        bar.setSpacing(4)

        def _btn(label: str, tip: str, slot) -> QPushButton:
            b = QPushButton(label)
            b.setObjectName("ReaderToolBtn")
            b.setAccessibleName(tip)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            return b

        bar.addWidget(_btn("← Library", "Back to library", self._finish))
        self._toggle_side_btn = _btn(
            "Hide outline", "Show or hide outline panel (Ctrl+Shift+O)", self._toggle_side_panel
        )
        bar.addWidget(self._toggle_side_btn)
        bar.addWidget(self._toolbar_sep())

        self._title = QLabel("")
        self._title.setObjectName("ReaderTitle")
        self._title.setWordWrap(False)
        self._title.setMinimumWidth(0)
        bar.addWidget(self._title, 1)
        bar.addWidget(self._toolbar_sep())

        self._prev = _btn("‹", "Previous page", lambda: self._go(self._page - 1))
        bar.addWidget(self._prev)
        self._page_label = QLabel("")
        self._page_label.setObjectName("ReaderPageLabel")
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bar.addWidget(self._page_label)
        self._next = _btn("›", "Next page", lambda: self._go(self._page + 1))
        bar.addWidget(self._next)
        bar.addWidget(self._toolbar_sep())

        bar.addWidget(_btn("−", "Zoom out", lambda: self._set_zoom(self._zoom / 1.2)))
        bar.addWidget(_btn("+", "Zoom in",  lambda: self._set_zoom(self._zoom * 1.2)))
        self._zoom_label = QLabel("150%")
        self._zoom_label.setObjectName("ReaderZoomLabel")
        self._zoom_label.setFixedWidth(44)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bar.addWidget(self._zoom_label)
        bar.addWidget(_btn("Fit", "Fit to page width (Ctrl+0)", self._fit_width))
        bar.addWidget(self._toolbar_sep())

        self._bookmark_btn = _btn("☆", "Bookmark this page", self._toggle_page_bookmark)
        self._bookmark_btn.setCheckable(True)
        bar.addWidget(self._bookmark_btn)
        bar.addWidget(self._toolbar_sep())

        # Annotation color picker (used when right-click → Highlight/Underline/Strikeout)
        color_label = QLabel("Color:")
        color_label.setObjectName("FieldLabel")
        bar.addWidget(color_label)
        self._color_combo = QComboBox()
        self._color_combo.setAccessibleName("Annotation colour")
        for name, value in _HIGHLIGHT_COLORS:
            self._color_combo.addItem(name, value)
        bar.addWidget(self._color_combo)
        bar.addWidget(self._toolbar_sep())

        self._toggle_tools_btn = _btn(
            "Hide tools", "Show or hide tools panel (Ctrl+Shift+T)", self._toggle_tools_panel
        )
        bar.addWidget(self._toggle_tools_btn)

        # Annotation status — shows brief feedback when a highlight/annotation
        # action fails (e.g. text not found in the PDF stream). Auto-hides after 3 s.
        self._annot_status = QLabel("")
        self._annot_status.setObjectName("ReaderHint")
        self._annot_status.setVisible(False)
        bar.addWidget(self._annot_status, alignment=Qt.AlignmentFlag.AlignRight)
        return bar_widget

    def _toolbar_sep(self) -> QWidget:
        sep = QWidget()
        sep.setObjectName("ReaderToolSep")
        sep.setFixedWidth(1)
        sep.setFixedHeight(22)
        return sep

    def _build_side_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("ReaderSidePanel")
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        panel.setMinimumWidth(0)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        heading = QLabel("Source")
        heading.setObjectName("SettingsSection")
        layout.addWidget(heading)

        self._source_meta = QLabel("No source open")
        self._source_meta.setObjectName("SettingsHint")
        self._source_meta.setWordWrap(True)
        layout.addWidget(self._source_meta)

        self._page_jump = QLineEdit()
        self._page_jump.setPlaceholderText("Go to page…")
        self._page_jump.setAccessibleName("Go to page")
        self._page_jump.returnPressed.connect(self._jump_to_typed_page)
        layout.addWidget(self._page_jump)

        bm_label = QLabel("Bookmarks")
        bm_label.setObjectName("FieldLabel")
        layout.addWidget(bm_label)

        self._side_bookmarks = QListWidget()
        self._side_bookmarks.setAccessibleName("Source bookmarks")
        self._side_bookmarks.itemDoubleClicked.connect(self._jump_to_item)
        self._side_bookmarks.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._side_bookmarks.customContextMenuRequested.connect(self._bookmark_list_menu)
        layout.addWidget(self._side_bookmarks, 1)

        bm_remove = QPushButton("Remove selected")
        bm_remove.setAccessibleName("Remove selected bookmark")
        bm_remove.clicked.connect(self._remove_bookmark)
        layout.addWidget(bm_remove, alignment=Qt.AlignmentFlag.AlignLeft)

        hl_label = QLabel("Annotations")
        hl_label.setObjectName("FieldLabel")
        layout.addWidget(hl_label)

        chips_row = QHBoxLayout()
        chips_row.setSpacing(4)
        self._hl_filter_chips: list[QPushButton] = []

        all_chip = QPushButton("All")
        all_chip.setCheckable(True)
        all_chip.setChecked(True)
        all_chip.setAccessibleName("Show all annotations")
        all_chip.setObjectName("HlFilterChip")
        all_chip.setFixedHeight(22)
        all_chip.clicked.connect(lambda: self._set_highlight_filter(None, all_chip))
        chips_row.addWidget(all_chip)
        self._hl_all_chip = all_chip
        self._hl_filter_chips.append(all_chip)

        self._hl_swatch_chips: list[tuple[QPushButton, str]] = []
        for chip_name, chip_color in _HIGHLIGHT_COLORS:
            chip = QPushButton()
            chip.setCheckable(True)
            chip.setAccessibleName(f"Filter {chip_name} annotations")
            chip.setObjectName("HlFilterChip")
            chip.setFixedHeight(22)
            chip.setFixedWidth(22)
            chip.clicked.connect(
                lambda _c, col=chip_color, b=chip: self._set_highlight_filter(col, b)
            )
            chips_row.addWidget(chip)
            self._hl_filter_chips.append(chip)
            self._hl_swatch_chips.append((chip, chip_color))
        self._restyle_swatch_chips()

        chips_row.addStretch(1)
        layout.addLayout(chips_row)

        self._side_highlights = QListWidget()
        self._side_highlights.setAccessibleName("Source annotations")
        self._side_highlights.itemDoubleClicked.connect(self._jump_to_item)
        self._side_highlights.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._side_highlights.customContextMenuRequested.connect(self._highlight_list_menu)
        layout.addWidget(self._side_highlights, 2)

        hl_erase = QPushButton("Delete selected")
        hl_erase.setAccessibleName("Delete selected annotation")
        hl_erase.clicked.connect(self._delete_annotation_from_list)
        layout.addWidget(hl_erase, alignment=Qt.AlignmentFlag.AlignLeft)

        export_btn = QPushButton("Export annotations…")
        export_btn.setAccessibleName("Export annotations — copy to clipboard")
        export_btn.clicked.connect(self._show_export_menu)
        layout.addWidget(export_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        return panel

    def _build_pdf_pane(self) -> QWidget:
        pane = QWidget()
        pane.setObjectName("ReaderPagePane")
        pane.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        pane.setMinimumWidth(240)

        self._pdf_pane_layout = QVBoxLayout(pane)
        self._pdf_pane_layout.setContentsMargins(0, 0, 0, 0)
        self._pdf_pane_layout.setSpacing(0)

        # Placeholder shown until _ensure_webview() runs on first showEvent()
        self._webview_placeholder = QLabel("")
        self._webview_placeholder.setStyleSheet("background:#404040;")
        self._pdf_pane_layout.addWidget(self._webview_placeholder, 1)
        return pane

    def _ensure_webview(self) -> None:
        """Create QWebEngineView lazily on first show.

        Deferred from __init__ because QWebEngineView() blocks until the
        Chromium backend completes its init handshake, which requires a running
        event loop.  Headless tests never show the widget, so they never block.
        """
        if self._webview_inited:
            return
        self._webview_inited = True
        wv = QWebEngineView()
        wv.setAccessibleName("PDF viewer")
        s = wv.settings()
        if s is not None:
            s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
            s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        pg = wv.page()
        ch = QWebChannel(pg)
        ch.registerObject("bridge", self._bridge)
        if pg is not None:
            pg.setWebChannel(ch)
        wv.loadFinished.connect(self._on_viewer_loaded)
        self._webview_placeholder.hide()
        self._pdf_pane_layout.addWidget(wv, 1)
        wv.load(QUrl.fromLocalFile(_VIEWER_HTML))
        self._channel = ch
        self._webview = wv

    def _build_tool_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.setObjectName("ReaderTools")
        tabs.setAccessibleName("Reader tools")
        tabs.addTab(self._build_notes_pane(), "Notes")           # 0
        tabs.addTab(self._build_dictionary_pane(), "Dictionary") # 1
        return tabs

    def _build_notes_pane(self) -> QWidget:
        pane = QWidget()
        pane.setObjectName("Page")
        pane.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(pane)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        hint = QLabel("Notes are saved automatically.")
        hint.setObjectName("SettingsHint")
        layout.addWidget(hint)

        self._notes = QPlainTextEdit()
        self._notes.setAccessibleName("Source notes")
        self._notes.textChanged.connect(lambda: self._notes_timer.start())
        layout.addWidget(self._notes, 1)

        export_btn = QPushButton("Export notes as card…")
        export_btn.setAccessibleName("Create a card from notes text")
        export_btn.clicked.connect(self._export_notes_as_card)
        layout.addWidget(export_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        return pane

    def _build_dictionary_pane(self) -> QWidget:
        pane = QWidget()
        pane.setObjectName("Page")
        pane.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(pane)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._dict_search = QLineEdit()
        self._dict_search.setPlaceholderText("Look up a word…")
        self._dict_search.setAccessibleName("Dictionary search")
        self._dict_search.textChanged.connect(self._dict_suggest)
        self._dict_search.returnPressed.connect(
            lambda: self._dict_lookup(self._dict_search.text())
        )
        layout.addWidget(self._dict_search)

        self._dict_suggestions = QListWidget()
        self._dict_suggestions.setAccessibleName("Dictionary suggestions")
        self._dict_suggestions.itemClicked.connect(
            lambda item: self._dict_lookup(item.text())
        )
        layout.addWidget(self._dict_suggestions, 1)

        self._dict_result = QTextBrowser()
        self._dict_result.setAccessibleName("Definition")
        self._dict_result.setOpenLinks(False)
        layout.addWidget(self._dict_result, 2)

        speak = QPushButton("🔊 Speak definition")
        speak.setAccessibleName("Speak definition")
        speak.clicked.connect(self._speak_definition)
        layout.addWidget(speak, alignment=Qt.AlignmentFlag.AlignLeft)
        return pane

    # ── Adaptive layout ───────────────────────────────────────────────────────

    def _restore_or_default_splitters(self) -> None:
        stored = self._tools_memory.sizes or self._side_memory.sizes
        if stored and len(stored) == 3 and sum(stored) > 0:
            self._reader_splitter.setSizes(stored)
        else:
            self._reader_splitter.setSizes([200, 680, 320])

    def _apply_proportional_defaults(self) -> None:
        width = max(800, self.width())
        if self._side_memory.user_adjusted or self._tools_memory.user_adjusted:
            stored = self._tools_memory.sizes or self._side_memory.sizes
            if stored and len(stored) == 3 and sum(stored) > 0:
                self._reader_splitter.setSizes(stored)
            return
        outline = round(width * 0.18)
        tools   = round(width * 0.27)
        page    = max(240, width - outline - tools)
        self._reader_splitter.setSizes([outline, page, tools])

    def showEvent(self, event: QShowEvent) -> None:  # type: ignore[override]
        super().showEvent(event)
        if not self._layout_initialized:
            self._apply_proportional_defaults()
            self._layout_initialized = True
        self._ensure_webview()

    def _on_theme_changed(self) -> None:
        self._theme_applied_count += 1
        self._restyle_swatch_chips()

    def _restyle_swatch_chips(self) -> None:
        """Re-apply the annotation-colour filter chips' chrome from theme tokens.

        The swatch *fill* is data (the annotation colour) and stays inline, but
        the border must come from the palette so the chip still reads correctly
        in light/dark/high-contrast themes instead of a hardcoded grey/black.
        """
        if not hasattr(self, "_hl_swatch_chips"):
            return
        theme = getattr(self._context, "theme", None) if self._context else None
        palette = theme.tokens.palette if theme is not None else None
        border = palette.border if palette is not None else "#888888"
        checked_border = palette.accent if palette is not None else "#4263eb"
        for chip, chip_color in self._hl_swatch_chips:
            chip.setStyleSheet(
                f"QPushButton{{background:{chip_color};border:1px solid {border};border-radius:3px;}}"
                f"QPushButton:checked{{border:2px solid {checked_border};border-radius:3px;}}"
            )

    def _on_tool_tab_changed(self, _index: int) -> None:
        if not hasattr(self, "_reader_splitter"):
            return
        sizes = self._reader_splitter.sizes()
        if len(sizes) != 3:
            return
        total = sum(sizes)
        if total <= 0 or sizes[2] >= 80:
            return
        tools   = round(total * 0.27)
        outline = sizes[0]
        page    = max(240, total - outline - tools)
        self._reader_splitter.setSizes([outline, page, tools])
        self._tools_visible = True
        self._toggle_tools_btn.setText("Hide tools")

    def _on_reader_splitter_moved(self, _pos: int, index: int) -> None:
        sizes = self._reader_splitter.sizes()
        if index == 1:
            self._side_memory.mark_adjusted(sizes)
        elif index == 2:
            self._tools_memory.mark_adjusted(sizes)

    def _toggle_side_panel(self) -> None:
        if not hasattr(self, "_reader_splitter"):
            return
        sizes = self._reader_splitter.sizes()
        total = sum(sizes) if sizes else max(600, self.width())
        self._side_visible = not self._side_visible
        if self._side_visible:
            remembered = self._side_memory.sizes
            if remembered and len(remembered) == 3 and remembered[0] > 40:
                self._reader_splitter.setSizes(remembered)
            else:
                outline = round(total * 0.18)
                tools   = sizes[2] if len(sizes) == 3 else round(total * 0.27)
                page    = max(240, total - outline - tools)
                self._reader_splitter.setSizes([outline, page, tools])
            self._toggle_side_btn.setText("Hide outline")
        else:
            self._side_memory.mark_adjusted(sizes)
            tools = sizes[2] if len(sizes) == 3 else 0
            self._reader_splitter.setSizes([0, max(240, total - tools), tools])
            self._toggle_side_btn.setText("Show outline")

    def _toggle_tools_panel(self) -> None:
        if not hasattr(self, "_reader_splitter"):
            return
        sizes = self._reader_splitter.sizes()
        total = sum(sizes) if sizes else max(600, self.width())
        self._tools_visible = not self._tools_visible
        if self._tools_visible:
            remembered = self._tools_memory.sizes
            if remembered and len(remembered) == 3 and remembered[2] > 40:
                self._reader_splitter.setSizes(remembered)
            else:
                tools   = round(total * 0.27)
                outline = sizes[0] if len(sizes) == 3 else round(total * 0.18)
                page    = max(240, total - outline - tools)
                self._reader_splitter.setSizes([outline, page, tools])
            self._toggle_tools_btn.setText("Hide tools")
        else:
            self._tools_memory.mark_adjusted(sizes)
            outline = sizes[0] if len(sizes) == 3 else 0
            self._reader_splitter.setSizes([outline, max(240, total - outline), 0])
            self._toggle_tools_btn.setText("Show tools")

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    @property
    def splitter_sizes(self) -> list[int]:
        return self._reader_splitter.sizes() if hasattr(self, "_reader_splitter") else []

    @property
    def _active_pdf_path(self) -> str | None:
        if self._source is not None and self._source.working_copy_path:
            return self._source.working_copy_path
        if self._file_path:
            return self._file_path
        return None

    def open_source(self, source_id: int) -> None:
        self._close_session()

        if self._context.db is None:
            self._show_reader_error("No database available.")
            return

        self._session = self._context.db.new_session()
        self._service = SourceService(self._session)

        doc = self._service.sources.get(source_id)
        if doc is None:
            self._show_reader_error("Source not found.")
            self._close_session()
            return

        self._source_id   = source_id
        self._source      = doc
        self._source_kind = doc.kind
        self._file_path   = doc.file_path
        self._page_count  = max(1, int(doc.page_count or 1))
        self._title.setText(doc.title or "Untitled source")
        self._source_meta.setText(
            f"{doc.title or 'Untitled source'}\n"
            f"{self._page_count} page{'s' if self._page_count != 1 else ''}"
        )

        self._notes.blockSignals(True)
        self._notes.setPlainText(doc.notes_text or "")
        self._notes.blockSignals(False)

        # Reset viewer state so the next _go() reloads the PDF bytes
        self._pdf_loaded_in_viewer = False

        self._refresh_side_lists()
        if self._side_highlights.currentItem() is None:
            self._select_last_highlight()
        self._go(doc.last_opened_page or 1, save=False)

    def _close_session(self) -> None:
        if self._session is not None:
            try:
                self._session.commit()
            except Exception:
                self._session.rollback()
            finally:
                self._session.close()
        self._session = None
        self._service = None
        self._source   = None

    def _finish(self) -> None:
        self._save_notes()
        if self._service is not None and self._source_id is not None:
            try:
                self._service.update_position(self._source_id, self._page)
                if self._session is not None:
                    self._session.commit()
            except Exception:
                if self._session is not None:
                    self._session.rollback()
        self._close_session()
        self.finished.emit()

    # ── PDF viewer ────────────────────────────────────────────────────────────

    def _on_viewer_loaded(self, ok: bool) -> None:
        self._viewer_ready = ok
        if ok and self._pending_pdf_load and self._active_pdf_path:
            self._load_pdf_in_viewer()

    def _load_pdf_in_viewer(self) -> None:
        """Read PDF bytes and send to JS to initialize (or reinitialize) PDF.js."""
        if not self._viewer_ready or self._active_pdf_path is None:
            self._pending_pdf_load = True
            return
        if self._source_kind != "pdf":
            return
        try:
            raw = open(self._active_pdf_path, "rb").read()
        except OSError:
            return
        b64 = json.dumps(base64.b64encode(raw).decode())
        if self._webview is None:
            return
        self._webview.page().runJavaScript(f"loadPdfBase64({b64}, {self._page})")
        self._refresh_annot_rects_in_js()
        self._pdf_loaded_in_viewer = True
        self._pending_pdf_load = False

    def _reload_pdf_page(self) -> None:
        """Re-read PDF working copy (after annotation write/delete) and push to JS."""
        self._pdf_loaded_in_viewer = False
        self._load_pdf_in_viewer()

    def _refresh_annot_rects_in_js(self) -> None:
        """Push current-page annotation hit-test rects to the JS annotation layer."""
        if not self._viewer_ready or self._active_pdf_path is None:
            return
        if self._source_kind != "pdf":
            return
        try:
            page_annots = AnnotationService.get_page_annotations(
                self._active_pdf_path, self._page - 1
            )
            rects = [{"xref": a.xref, "rect": a.rect} for a in page_annots]
        except Exception:
            rects = []
        if self._webview is None:
            return
        self._webview.page().runJavaScript(f"setPageAnnotations({json.dumps(rects)})")

    # ── Navigation ────────────────────────────────────────────────────────────

    def _go(self, page: int, save: bool = True) -> None:
        page = max(1, min(int(page), self._page_count))
        self._page = page

        self._page_label.setText(f"Page {page} / {self._page_count}")
        self._page_jump.setText("")
        self._page_jump.setPlaceholderText(f"Go to page… current {page}")
        self._prev.setEnabled(page > 1)
        self._next.setEnabled(page < self._page_count)

        if self._source_kind == "pdf":
            if not self._pdf_loaded_in_viewer:
                self._load_pdf_in_viewer()
            elif self._viewer_ready and self._webview is not None:
                self._refresh_annot_rects_in_js()
                self._webview.page().runJavaScript(f"goToPage({page})")

        if save and self._service is not None and self._source_id is not None:
            try:
                self._service.update_position(self._source_id, page)
                if self._session is not None:
                    self._session.commit()
            except Exception:
                if self._session is not None:
                    self._session.rollback()

        self._update_bookmark_btn_state()

    def _update_page_label(self) -> None:
        """Sync page label after JS-driven navigation (called by PdfBridge)."""
        self._page_label.setText(f"Page {self._page} / {self._page_count}")
        self._prev.setEnabled(self._page > 1)
        self._next.setEnabled(self._page < self._page_count)
        self._update_bookmark_btn_state()

    def _jump_to_typed_page(self) -> None:
        text = self._page_jump.text().strip()
        if not text:
            return
        try:
            self._go(int(text))
        except ValueError:
            self._page_jump.selectAll()

    def _set_zoom(self, zoom: float) -> None:
        self._zoom = max(0.5, min(float(zoom), 4.0))
        self._zoom_label.setText(f"{int(round(self._zoom * 100))}%")
        if self._viewer_ready and self._webview is not None:
            self._webview.page().runJavaScript(f"setZoom({self._zoom})")

    def _fit_width(self) -> None:
        path = self._active_pdf_path
        if self._source_kind != "pdf" or not path:
            return
        try:
            base = render_service.render_page(path, self._page - 1, zoom=1.0)
        except Exception:
            return
        if self._webview is None:
            return
        available = max(200, self._webview.width() - 24)
        if base.width > 0:
            self._set_zoom(available / base.width)

    # ── Annotation actions (called from PdfBridge context menu) ───────────────

    def _show_annot_status(self, msg: str) -> None:
        """Display *msg* in the topbar status label, then auto-hide after 3 s."""
        self._annot_status.setText(msg)
        self._annot_status.setVisible(True)
        QTimer.singleShot(3000, lambda: self._annot_status.setVisible(False))

    def _rects_to_quads(self, sel_rects: list[dict], page_index: int) -> list:
        """Convert normalised JS selection rects (0..1) to fitz.Quad objects.

        sel_rects come from range.getClientRects() normalised against the
        .page-wrapper bounding box.  Multiplying by the PDF page dimensions
        (in points) gives the correct PDF coordinate without any text search.
        """
        path = self._active_pdf_path
        if not path or not sel_rects:
            return []
        try:
            import fitz
            rects = merge_line_rects(sel_rects)
            with fitz.open(path) as doc:
                if page_index < 0 or page_index >= doc.page_count:
                    return []
                page = doc.load_page(page_index)
                pw, ph = page.rect.width, page.rect.height
                quads = []
                for r in rects:
                    x0 = max(0.0, float(r["x0"])) * pw
                    y0 = max(0.0, float(r["y0"])) * ph
                    x1 = min(1.0, float(r["x1"])) * pw
                    y1 = min(1.0, float(r["y1"])) * ph
                    if x1 > x0 and y1 > y0:
                        quads.append(fitz.Rect(x0, y0, x1, y1).quad)
            return quads
        except Exception:
            return []

    def _annotate_text(self, text: str, mode: str,
                       sel_rects: list[dict] | None = None) -> None:
        """Create a PDF annotation on *text* at the current page.

        When *sel_rects* is provided (normalised 0..1 bounding boxes from the JS
        DOM selection), annotation quads are derived from those positions directly —
        no text search required.  Falls back to search_text_quads when called
        programmatically (e.g. from tests) where no rects are available.
        """
        path = self._active_pdf_path
        if not text or path is None:
            return
        color = self._color_combo.currentData() or "#ffd43b"
        if mode in ("underline", "strikeout"):
            color = "#000000"

        # Primary: position-based quads from the JS DOM selection
        quads = self._rects_to_quads(sel_rects, self._page - 1) if sel_rects else []

        # Fallback: string search (programmatic callers, or position path unavailable)
        if not quads:
            quads = render_service.search_text_quads(path, self._page - 1, text)

        if not quads:
            self._show_annot_status("Text not found — try a shorter selection")
            return
        try:
            if mode == "underline":
                AnnotationService.add_underline(path, self._page - 1, quads, color, subject=text)
            elif mode == "strikeout":
                AnnotationService.add_strikeout(path, self._page - 1, quads, color, subject=text)
            else:
                AnnotationService.add_highlight(path, self._page - 1, quads, color, subject=text)
            self._reload_pdf_page()
            self._refresh_side_lists()
        except Exception:
            pass

    def _delete_annotation_at_rects(
        self, sel_rects: list[dict], page_index: int
    ) -> None:
        """Delete the annotation whose rect most overlaps the current selection."""
        path = self._active_pdf_path
        if not path or not sel_rects:
            return
        page_idx = page_index if page_index >= 0 else self._page - 1
        annots = AnnotationService.get_page_annotations(path, page_idx)
        if not annots:
            self._show_annot_status("No annotations on this page")
            return
        sx0 = min(r["x0"] for r in sel_rects)
        sy0 = min(r["y0"] for r in sel_rects)
        sx1 = max(r["x1"] for r in sel_rects)
        sy1 = max(r["y1"] for r in sel_rects)
        best_xref, best_overlap = -1, 0.0
        for a in annots:
            ar = a.rect
            ox = max(0.0, min(ar["x1"], sx1) - max(ar["x0"], sx0))
            oy = max(0.0, min(ar["y1"], sy1) - max(ar["y0"], sy0))
            overlap = ox * oy
            if overlap > best_overlap:
                best_overlap, best_xref = overlap, a.xref
        if best_xref >= 0 and best_overlap > 0:
            self._delete_annotation_by_xref(best_xref, page_idx)
        else:
            self._show_annot_status("No annotation found at selection")

    def _clear_page_annotations(self) -> None:
        """Delete every annotation on the current page."""
        path = self._active_pdf_path
        if not path:
            return
        annots = AnnotationService.get_page_annotations(path, self._page - 1)
        if not annots:
            self._show_annot_status("No annotations on this page")
            return
        for a in annots:
            try:
                AnnotationService.delete_annotation(path, self._page - 1, a.xref)
            except Exception:
                pass
        self._reload_pdf_page()
        self._refresh_side_lists()

    def _create_card_from_text(self, text: str) -> None:
        """Open AddNoteDialog pre-filled with selected PDF text."""
        if not text:
            return
        AddNoteDialog(
            self._context,
            initial_values={"Front": text, "Text": text},
            parent=self,
        ).exec()

    def _lookup_word(self, word: str) -> None:
        """Look up *word* in the dictionary tab."""
        word = word.strip(".,;:!?()[]{}\"\"''").strip()
        if not word:
            return
        self._tabs.setCurrentWidget(self._dict_search.parentWidget())
        self._dict_search.setText(word)
        self._dict_lookup(word)

    def _edit_comment_dialog(self, xref: int, page_index: int | None = None) -> None:
        path = self._active_pdf_path
        if path is None:
            return
        page_idx = page_index if page_index is not None else self._page - 1
        annots = AnnotationService.get_page_annotations(path, page_idx)
        annot = next((a for a in annots if a.xref == xref), None)
        if annot is None:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Edit comment")
        layout = QVBoxLayout(dialog)
        box = QPlainTextEdit(annot.content)
        box.setMinimumWidth(320)
        box.setMinimumHeight(100)
        layout.addWidget(box)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            AnnotationService.update_comment(path, page_idx, xref, box.toPlainText())
            self._refresh_side_lists()

    def _card_from_annotation(self, xref: int, page_index: int | None = None) -> None:
        path = self._active_pdf_path
        if path is None:
            return
        page_idx = page_index if page_index is not None else self._page - 1
        annots = AnnotationService.get_page_annotations(path, page_idx)
        annot = next((a for a in annots if a.xref == xref), None)
        if annot is None:
            return
        AddNoteDialog(
            self._context,
            initial_values={"Front": annot.subject or "", "Text": annot.content or ""},
            parent=self,
        ).exec()

    def _delete_annotation_by_xref(self, xref: int, page_index: int | None = None) -> None:
        path = self._active_pdf_path
        if path is None:
            return
        page_idx = page_index if page_index is not None else self._page - 1
        try:
            AnnotationService.delete_annotation(path, page_idx, xref)
        except Exception:
            return
        if page_idx == self._page - 1:
            self._reload_pdf_page()
        self._refresh_side_lists()

    def _delete_annotation_from_list(self) -> None:
        item = self._side_highlights.currentItem()
        if item is None:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data or len(data) < 3:
            return
        xref, page, _type = data
        self._delete_annotation_by_xref(xref, page)

    # ── Side lists ────────────────────────────────────────────────────────────

    def _set_highlight_filter(self, color: str | None, active_chip: QPushButton) -> None:
        self._hl_filter_color = color
        for chip in self._hl_filter_chips:
            chip.setChecked(chip is active_chip)
        self._refresh_side_lists()

    def _refresh_side_lists(self) -> None:
        self._side_highlights.blockSignals(True)
        self._side_highlights.clear()

        path = self._active_pdf_path
        if path and self._source_kind == "pdf":
            try:
                annotations = AnnotationService.get_all_annotations(path)
            except Exception:
                annotations = []

            if self._hl_filter_color is not None:
                annotations = [a for a in annotations if a.color_hex == self._hl_filter_color]

            type_icons = {8: "H", 0: "N", 9: "U", 11: "S"}
            current_pg: int | None = None
            for annot in annotations:
                if annot.page != current_pg:
                    current_pg = annot.page
                    sep = QListWidgetItem(f"── Page {annot.page + 1} ──")
                    sep.setFlags(Qt.ItemFlag.NoItemFlags)
                    sep.setForeground(QColor(self._dim_color))
                    self._side_highlights.addItem(sep)

                icon = type_icons.get(annot.type_code, "?")
                has_comment = bool((annot.content or "").strip())
                subject = (annot.subject or "").replace("\n", " ").strip()
                prefix = "✏ " if has_comment else "  "
                label = f"{prefix}[{icon}] p{annot.page + 1}: {subject[:55]}"
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, (annot.xref, annot.page, annot.type_code))
                tooltip = subject
                if has_comment:
                    tooltip += f"\n✏ {(annot.content or '').strip()}"
                item.setToolTip(tooltip)
                bg = QColor(annot.color_hex)
                item.setBackground(bg)
                luminance = 0.299 * bg.redF() + 0.587 * bg.greenF() + 0.114 * bg.blueF()
                item.setForeground(QColor("#000000") if luminance > 0.5 else QColor("#ffffff"))
                self._side_highlights.addItem(item)

        self._side_highlights.blockSignals(False)

        self._side_bookmarks.clear()
        if self._service is not None and self._source_id is not None:
            try:
                bookmarks = list(self._service.bookmarks_for(self._source_id))
            except Exception:
                bookmarks = []
            for bookmark in bookmarks:
                label_text = bookmark.label or "Bookmark"
                item = QListWidgetItem(f"p{bookmark.page}: {label_text}")
                item.setData(Qt.ItemDataRole.UserRole, (bookmark.id, bookmark.page))
                self._side_bookmarks.addItem(item)

        self._update_bookmark_btn_state()

    def _jump_to_item(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        try:
            if len(data) == 2:
                self._go(int(data[1]))          # bookmark: 1-based page
            else:
                self._go(int(data[1]) + 1)      # annotation: 0-based page
        except Exception:
            return

    def _add_bookmark(self, label: str = "") -> None:
        if self._service is None or self._source_id is None:
            return
        try:
            self._service.add_bookmark(self._source_id, self._page, label=label)
            if self._session is not None:
                self._session.commit()
            self._refresh_side_lists()
        except Exception:
            if self._session is not None:
                self._session.rollback()

    def _select_last_highlight(self) -> None:
        for row in range(self._side_highlights.count() - 1, -1, -1):
            item = self._side_highlights.item(row)
            if item and item.data(Qt.ItemDataRole.UserRole):
                self._side_highlights.setCurrentRow(row)
                return

    def _update_bookmark_btn_state(self) -> None:
        if not hasattr(self, "_bookmark_btn") or self._service is None or self._source_id is None:
            return
        try:
            bookmarks = self._service.bookmarks_for(self._source_id)
            is_bm = any(b.page == self._page for b in bookmarks)
        except Exception:
            is_bm = False
        self._bookmark_btn.setText("★" if is_bm else "☆")
        self._bookmark_btn.setChecked(is_bm)

    def _toggle_page_bookmark(self) -> None:
        if self._service is None or self._source_id is None:
            return
        try:
            bookmarks = self._service.bookmarks_for(self._source_id)
            page_bms = [b for b in bookmarks if b.page == self._page]
            if page_bms:
                for bm in page_bms:
                    self._service.remove_bookmark(bm.id)
            else:
                self._service.add_bookmark(self._source_id, self._page)
            if self._session is not None:
                self._session.commit()
            self._refresh_side_lists()
        except Exception:
            if self._session is not None:
                self._session.rollback()

    def _remove_bookmark(self) -> None:
        item = self._side_bookmarks.currentItem()
        if item is None or self._service is None:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        try:
            self._service.remove_bookmark(data[0])
            if self._session is not None:
                self._session.commit()
            self._refresh_side_lists()
        except Exception:
            if self._session is not None:
                self._session.rollback()

    def _highlight_list_menu(self, pos) -> None:
        item = self._side_highlights.itemAt(pos)
        if not item or not item.data(Qt.ItemDataRole.UserRole):
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if len(data) < 3:
            return
        xref, page, _type = data
        menu = QMenu(self)
        menu.addAction("Edit comment",      lambda: self._edit_comment_dialog(xref, page))
        menu.addAction("Create card",       lambda: self._card_from_annotation(xref, page))
        menu.addAction("Jump to page",      lambda: self._go(page + 1))
        menu.addSeparator()
        menu.addAction("Delete annotation", lambda: self._delete_annotation_by_xref(xref, page))
        menu.exec(self._side_highlights.mapToGlobal(pos))

    def _bookmark_list_menu(self, pos) -> None:
        item = self._side_bookmarks.currentItem()
        if not item:
            return
        menu = QMenu(self)
        menu.addAction("Jump to page",     lambda: self._jump_to_item(item))
        menu.addAction("Remove bookmark",  self._remove_bookmark)
        menu.addAction("Edit label…",      lambda: self._relabel_bookmark(item))
        menu.exec(self._side_bookmarks.mapToGlobal(pos))

    def _relabel_bookmark(self, item: QListWidgetItem) -> None:
        if self._service is None or self._source_id is None:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        bm_id, page = data
        label, ok = QInputDialog.getText(self, "Edit label", "Bookmark label:")
        if not ok:
            return
        try:
            self._service.remove_bookmark(bm_id)
            self._service.add_bookmark(self._source_id, page, label=label.strip())
            if self._session is not None:
                self._session.commit()
            self._refresh_side_lists()
        except Exception:
            if self._session is not None:
                self._session.rollback()

    # ── Export ────────────────────────────────────────────────────────────────

    def _show_export_menu(self) -> None:
        menu = QMenu(self)
        menu.addAction("Copy as Markdown", self._export_highlights)
        menu.addAction("Copy as Anki pairs", self._copy_as_pairs)
        menu.exec(QCursor.pos())

    def _export_highlights(self) -> None:
        path = self._active_pdf_path
        if path is None:
            return
        try:
            annotations = AnnotationService.get_all_annotations(path)
        except Exception:
            return
        if not annotations:
            return
        doc = self._service.sources.get(self._source_id) if self._service and self._source_id else None
        title = (doc.title if doc else None) or "Annotations"
        type_icons = {8: "H", 0: "N", 9: "U", 11: "S"}
        lines = [f"# {title} — Annotations", ""]
        current_pg: int | None = None
        for annot in annotations:
            if annot.page != current_pg:
                current_pg = annot.page
                lines += [f"## Page {annot.page + 1}", ""]
            icon = type_icons.get(annot.type_code, "?")
            text = (annot.subject or "").replace("\n", " ").strip()
            lines.append(f"> [{icon}] {text}")
            if annot.content:
                lines += ["", f"✏ {annot.content.strip()}"]
            lines.append("")
        from PyQt6.QtWidgets import QApplication
        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText("\n".join(lines))

    def _copy_as_pairs(self) -> None:
        path = self._active_pdf_path
        if path is None:
            return
        try:
            annotations = AnnotationService.get_all_annotations(path)
        except Exception:
            return
        if not annotations:
            return
        lines = []
        for annot in annotations:
            front = (annot.subject or "").replace("\n", " ").strip()
            back  = (annot.content or "").replace("\n", " ").strip()
            lines.append(f"{front} | {back}")
        from PyQt6.QtWidgets import QApplication
        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText("\n".join(lines))

    # ── Notes ─────────────────────────────────────────────────────────────────

    def _append_to_notes(self, text: str) -> None:
        """Append selected text to the notes editor and trigger autosave."""
        if self._source_id is None:
            return
        current = self._notes.toPlainText()
        sep = "\n\n" if current.strip() else ""
        self._notes.setPlainText(current + sep + text)
        cursor = self._notes.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._notes.setTextCursor(cursor)
        self._notes_timer.start()

    def _save_notes(self) -> None:
        if self._service is None or self._source_id is None or self._session is None:
            return
        try:
            self._service.update_notes(self._source_id, self._notes.toPlainText())
            self._session.commit()
        except Exception:
            self._session.rollback()

    def _export_notes_as_card(self) -> None:
        text = self._notes.toPlainText().strip()
        if not text:
            return
        AddNoteDialog(
            self._context,
            initial_values={"Text": text, "Front": ""},
            parent=self,
        ).exec()

    # ── Dictionary ────────────────────────────────────────────────────────────

    def _dict_suggest(self, prefix: str) -> None:
        self._dict_suggestions.clear()
        if self._context.dictionary and prefix.strip():
            for word in self._context.dictionary.prefix_search(prefix, limit=15):
                self._dict_suggestions.addItem(word)

    def _dict_lookup(self, word: str) -> None:
        self._dict_result.setHtml(self._dictionary_html(word))

    def _dictionary_html(self, word: str) -> str:
        if not self._context.dictionary or not word.strip():
            return "<p><i>Type a word to look it up.</i></p>"
        result = self._context.dictionary.lookup(word.strip())
        if result is None:
            return f'<p><i>No definition found for "{html.escape(word)}".</i></p>'
        parts = [f"<h3>{html.escape(result.word)}</h3>"]
        for sense in result.senses:
            pos = f"<i>{html.escape(sense.pos)}</i> " if sense.pos else ""
            parts.append(f"<p>{pos}{html.escape(sense.gloss)}</p>")
        parts.append(
            f"<p style='color:{self._dim_color}'>source: {html.escape(result.source)}</p>"
        )
        return "".join(parts)

    def _speak_definition(self) -> None:
        if not self._context.tts:
            return
        document = QTextDocument()
        document.setHtml(self._dict_result.toHtml())
        text = document.toPlainText().strip()
        if text:
            self._context.tts.speak(text)

    @property
    def _dim_color(self) -> str:
        theme = self._context.settings.get("theme") if self._context else "dark"
        return PALETTES.get(theme, PALETTES["dark"]).text_dim

    # ── Error display ─────────────────────────────────────────────────────────

    def _show_reader_error(self, message: str) -> None:
        self._title.setText("Reader")
        self._source_meta.setText(message)
