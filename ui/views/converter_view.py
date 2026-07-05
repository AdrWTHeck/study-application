"""Standalone EPUB ↔ PDF converter view.

A centered utility panel. No database integration — the user picks an input
file, chooses a direction, sets a few options, and gets an output file. The
conversion runs on a single background thread that owns all the data; the GUI
only receives progress *messages* over a queued Qt signal (no shared-memory
lock on the data path) and can request cancellation via a synchronized flag.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

class _ConversionWorker(QObject):
    """Runs one conversion on its own thread and reports back via signals.

    The worker owns the conversion data exclusively, so the only cross-thread
    state is the cancel :class:`threading.Event` (set from the GUI thread, read
    by the converter) and the queued ``progress``/``finished`` signals.
    """

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool)

    def __init__(self, direction: str, input_path: str, output_path: str, options: dict) -> None:
        super().__init__()
        self._direction = direction
        self._input = input_path
        self._output = output_path
        self._options = options
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        """Request cancellation (safe to call from the GUI thread)."""
        self._cancel_event.set()

    def run(self) -> None:
        try:
            from converter import epub_to_pdf, pdf_to_epub
            fn = epub_to_pdf if self._direction == "epub_to_pdf" else pdf_to_epub
            ok = fn(
                self._input,
                self._output,
                self._options,
                progress_callback=self._emit_progress,
                cancel_callback=self._cancel_event.is_set,
            )
        except Exception:
            ok = False
        self.finished.emit(ok)

    def _emit_progress(self, percent: int, message: str) -> None:
        # Marshalled onto the GUI thread by Qt's queued connection.
        self.progress.emit(percent, message)


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------

class ConverterView(QWidget):
    """Centered EPUB ↔ PDF converter panel."""

    def __init__(self, context=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setObjectName("Page")
        self.setAccessibleName("File converter")

        self._thread: QThread | None = None
        self._worker: _ConversionWorker | None = None
        self._output_path: str = ""
        self._running = False

        self._build_ui()

        # React to density/theme changes so spacing reflows with the rest of the app.
        theme = getattr(context, "theme", None) if context is not None else None
        if theme is not None and hasattr(theme, "changed"):
            theme.changed.connect(self._on_theme_changed)

    # -- token-aware spacing -------------------------------------------------

    def _sp(self, mult: float) -> int:
        """Density-aware spacing unit, falling back to 8px when no context."""
        tokens = getattr(self._context, "theme", None)
        tokens = tokens.tokens if tokens is not None else None
        if tokens is not None:
            return tokens.density.space(mult)
        return round(8 * mult)

    # -- construction --------------------------------------------------------

    def _build_ui(self) -> None:
        self._outer = QVBoxLayout(self)
        self._outer.setSpacing(0)
        self._outer.addStretch(1)

        card = QWidget()
        card.setObjectName("SurfacePanel")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._card_layout = QVBoxLayout(card)

        # Header
        title_lbl = QLabel("File Converter")
        title_lbl.setObjectName("PageTitle")
        sub_lbl = QLabel("Convert between EPUB and PDF")
        sub_lbl.setObjectName("PageSubtitle")
        self._card_layout.addWidget(title_lbl)
        self._card_layout.addWidget(sub_lbl)

        # Direction
        dir_box = QGroupBox("Direction")
        dir_box.setAccessibleName("Conversion direction")
        dir_layout = QVBoxLayout(dir_box)

        self._radio_epub_pdf = QRadioButton("EPUB  →  PDF")
        self._radio_epub_pdf.setAccessibleName("Convert EPUB to PDF")
        self._radio_epub_pdf.setChecked(True)
        self._radio_pdf_epub = QRadioButton("PDF  →  EPUB")
        self._radio_pdf_epub.setAccessibleName("Convert PDF to EPUB")

        self._dir_group = QButtonGroup(self)
        self._dir_group.addButton(self._radio_epub_pdf, 0)
        self._dir_group.addButton(self._radio_pdf_epub, 1)
        self._dir_group.idToggled.connect(self._on_direction_changed)

        dir_layout.addWidget(self._radio_epub_pdf)
        dir_layout.addWidget(self._radio_pdf_epub)
        self._card_layout.addWidget(dir_box)

        # Input file
        input_box = QGroupBox("Input file")
        input_layout = QHBoxLayout(input_box)

        self._input_path = QLineEdit()
        self._input_path.setPlaceholderText("Select an EPUB file…")
        self._input_path.setReadOnly(True)
        self._input_path.setAccessibleName("Input file path")

        self._browse_btn = QPushButton("Browse…")
        self._browse_btn.setAccessibleName("Browse for input file")
        self._browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._browse_btn.clicked.connect(self._browse_input)

        input_layout.addWidget(self._input_path, 1)
        input_layout.addWidget(self._browse_btn)
        self._card_layout.addWidget(input_box)

        # Options — stacked so each direction shows only its relevant controls
        self._opts_stack = QStackedWidget()

        # EPUB → PDF options
        e2p_box = QGroupBox("Options")
        e2p_form = QFormLayout(e2p_box)
        e2p_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._font_size = QSpinBox()
        self._font_size.setRange(8, 24)
        self._font_size.setValue(12)
        self._font_size.setSuffix(" pt")
        self._font_size.setAccessibleName("Body font size in points")

        self._include_cover = QCheckBox("Include cover page")
        self._include_cover.setChecked(True)
        self._include_cover.setAccessibleName("Add a title and author cover page")

        self._include_toc = QCheckBox("Include table of contents")
        self._include_toc.setChecked(True)
        self._include_toc.setAccessibleName("Add a table of contents page")

        self._include_images_e2p = QCheckBox("Embed images")
        self._include_images_e2p.setChecked(True)
        self._include_images_e2p.setAccessibleName("Embed chapter images in the PDF")

        e2p_form.addRow("Font size:", self._font_size)
        e2p_form.addRow("", self._include_cover)
        e2p_form.addRow("", self._include_toc)
        e2p_form.addRow("", self._include_images_e2p)
        self._opts_stack.addWidget(e2p_box)

        # PDF → EPUB options
        p2e_box = QGroupBox("Options  (leave blank to use PDF metadata)")
        p2e_form = QFormLayout(p2e_box)
        p2e_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._override_title = QLineEdit()
        self._override_title.setPlaceholderText("Title from metadata")
        self._override_title.setAccessibleName("Override book title")

        self._override_author = QLineEdit()
        self._override_author.setPlaceholderText("Author from metadata")
        self._override_author.setAccessibleName("Override author name")

        self._include_images_p2e = QCheckBox("Embed images")
        self._include_images_p2e.setChecked(True)
        self._include_images_p2e.setAccessibleName("Embed images from the PDF")

        p2e_form.addRow("Title:", self._override_title)
        p2e_form.addRow("Author:", self._override_author)
        p2e_form.addRow("", self._include_images_p2e)
        self._opts_stack.addWidget(p2e_box)

        self._card_layout.addWidget(self._opts_stack)

        # Convert / Cancel button (one button, role depends on state)
        self._convert_btn = QPushButton("Convert")
        self._convert_btn.setObjectName("PrimaryButton")
        self._convert_btn.setAccessibleName("Start file conversion")
        self._convert_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._convert_btn.clicked.connect(self._on_primary_clicked)
        self._card_layout.addWidget(self._convert_btn)

        # Progress bar (hidden until a run is in flight)
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setAccessibleName("Conversion progress")
        self._progress.setVisible(False)
        self._card_layout.addWidget(self._progress)

        # Status line
        self._status = QLabel("Ready")
        self._status.setObjectName("ConverterStatus")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setWordWrap(True)
        self._card_layout.addWidget(self._status)

        self._outer.addWidget(card)
        self._outer.addStretch(2)

        self._apply_spacing()

    def _apply_spacing(self) -> None:
        """(Re)apply density-aware margins and spacing to the layouts."""
        self._outer.setContentsMargins(0, self._sp(6), 0, self._sp(6))
        self._card_layout.setContentsMargins(self._sp(6), self._sp(5), self._sp(6), self._sp(5))
        self._card_layout.setSpacing(self._sp(2))
        self._progress.setMinimumHeight(self._sp(3))
        self._status.setMinimumHeight(self._sp(4.5))

    # -- event handlers ------------------------------------------------------

    def _on_theme_changed(self) -> None:
        self._apply_spacing()

    def _on_direction_changed(self, btn_id: int, checked: bool) -> None:
        if not checked:
            return
        self._opts_stack.setCurrentIndex(btn_id)
        placeholder = "Select an EPUB file…" if btn_id == 0 else "Select a PDF file…"
        self._input_path.setPlaceholderText(placeholder)
        self._input_path.clear()
        self._set_status("Ready", "")

    def _browse_input(self) -> None:
        if self._radio_epub_pdf.isChecked():
            title, filt = "Select EPUB file", "EPUB files (*.epub)"
        else:
            title, filt = "Select PDF file", "PDF files (*.pdf)"
        path, _ = QFileDialog.getOpenFileName(self, title, "", filt)
        if path:
            self._input_path.setText(path)
            self._set_status("Ready", "")

    def _on_primary_clicked(self) -> None:
        if self._running:
            self._request_cancel()
        else:
            self._start_conversion()

    def _start_conversion(self) -> None:
        input_path = self._input_path.text().strip()
        if not input_path:
            self._set_status("Please select an input file first.", "error")
            return
        if not os.path.isfile(input_path):
            self._set_status("File not found — please browse again.", "error")
            return

        direction = "epub_to_pdf" if self._radio_epub_pdf.isChecked() else "pdf_to_epub"

        stem = Path(input_path).stem
        default_dir = str(Path(input_path).parent)
        if direction == "epub_to_pdf":
            caption, filt, default_name = "Save PDF as…", "PDF files (*.pdf)", f"{stem}.pdf"
        else:
            caption, filt, default_name = "Save EPUB as…", "EPUB files (*.epub)", f"{stem}.epub"

        output_path, _ = QFileDialog.getSaveFileName(
            self, caption, os.path.join(default_dir, default_name), filt
        )
        if not output_path:
            return  # user cancelled the save dialog

        self._output_path = output_path

        if direction == "epub_to_pdf":
            options = {
                "font_size": self._font_size.value(),
                "margin": 40,
                "include_cover": self._include_cover.isChecked(),
                "include_toc": self._include_toc.isChecked(),
                "include_images": self._include_images_e2p.isChecked(),
            }
        else:
            options = {
                "title": self._override_title.text().strip() or None,
                "author": self._override_author.text().strip() or None,
                "include_images": self._include_images_p2e.isChecked(),
            }

        self._set_running(True)
        self._run_in_thread(direction, input_path, output_path, options)

    def _request_cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._convert_btn.setEnabled(False)
            self._set_status("Cancelling…", "running")

    def _run_in_thread(self, direction: str, input_path: str, output_path: str, options: dict) -> None:
        thread = QThread()
        worker = _ConversionWorker(direction, input_path, output_path, options)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_done)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        thread.finished.connect(thread.deleteLater)

        # Keep references alive until the thread has actually finished.
        self._thread = thread
        self._worker = worker
        thread.start()

    def _on_progress(self, percent: int, message: str) -> None:
        self._progress.setValue(percent)
        self._set_status(message, "running")

    def _on_thread_finished(self) -> None:
        # Drop references only once the QThread has truly stopped, so the wrapper
        # is never destroyed while the thread is still running.
        self._thread = None
        self._worker = None

    def _on_done(self, ok: bool) -> None:
        self._set_running(False)
        if ok:
            self._progress.setValue(100)
            self._set_status(f"Done — saved to:\n{self._output_path}", "success")
        else:
            self._set_status(
                "Conversion did not finish (cancelled or failed). "
                "See converter.log for details.",
                "error",
            )

    # -- state helpers -------------------------------------------------------

    def _set_running(self, active: bool) -> None:
        self._running = active
        self._convert_btn.setEnabled(True)
        self._convert_btn.setText("Cancel" if active else "Convert")
        self._convert_btn.setAccessibleName(
            "Cancel the running conversion" if active else "Start file conversion"
        )
        self._progress.setVisible(active)
        if active:
            self._progress.setValue(0)
        # Single-flight guard: lock inputs while a conversion runs.
        for w in (self._browse_btn, self._radio_epub_pdf, self._radio_pdf_epub, self._opts_stack):
            w.setEnabled(not active)

    def _set_status(self, text: str, state: str) -> None:
        self._status.setText(text)
        self._status.setProperty("state", state)
        style = self._status.style()
        if style is not None:
            style.unpolish(self._status)
            style.polish(self._status)
