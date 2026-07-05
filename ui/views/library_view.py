"""The Library page: PDF and text sources organized into folders (categories).

A narrow folder sidebar on the left lets users navigate between "All Sources",
"Favorites", named folders, and "Uncategorized".  The source list in the centre
filters to the selected folder.  The reader opens on the right.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from app.context import AppContext
from domain.decks.hierarchy import is_child_of
from domain.sources.source_service import SourceService
from ui.components.folder_tree import FolderTreeWidget
from ui.components.labels import ElidedLabel
from ui.utils.layouts import apply_page_margins, clear_layout
from ui.views.reader_view import ReaderView

# Sentinel path values for special virtual folders in the sidebar tree.
# Must not contain "::" so the tree widget keeps them as top-level flat items.
_ALL           = "__all__"
_FAVORITES     = "__favorites__"
_UNCATEGORIZED = "__uncategorized__"


@dataclass
class _Row:
    id: int
    title: str
    page_count: int
    last_opened_page: int
    is_favorite: bool
    category: str | None
    tags: list[str]
    kind: str


class LibraryView(QWidget):
    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setObjectName("Page")
        self.setAccessibleName("Library")

        self._pending_folder: str | None = None   # newly created empty folder

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._splitter)

        self._folder_sidebar = self._build_folder_sidebar()
        self._browser        = self._build_browser()
        self._reader         = ReaderView(context)
        self._reader.finished.connect(self._on_reader_finished)
        self._placeholder    = self._build_placeholder()
        self._right_stack    = QStackedWidget()
        self._right_stack.addWidget(self._placeholder)
        self._right_stack.addWidget(self._reader)

        self._splitter.addWidget(self._folder_sidebar)
        self._splitter.addWidget(self._browser)
        self._splitter.addWidget(self._right_stack)
        self._splitter.setSizes([160, 280, 900])

        self._rows: list[_Row] = []
        self.refresh()

        _theme = self._context.theme if self._context else None
        if _theme is not None:
            _theme.changed.connect(self._apply_theme)

    def _apply_theme(self) -> None:
        self._render_rows()

    # ── Folder sidebar ──────────────────────────────────────────────────────

    def _build_folder_sidebar(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("FolderSidebar")
        panel.setMaximumWidth(200)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 16, 8, 8)
        layout.setSpacing(6)

        header = QLabel("FOLDERS")
        header.setObjectName("SidebarTitle")
        header.setAccessibleName("Folders")
        layout.addWidget(header)

        self._folder_tree = FolderTreeWidget(context=self._context)
        self._folder_tree.setObjectName("FolderList")
        self._folder_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._folder_tree.customContextMenuRequested.connect(self._folder_context_menu)
        self._folder_tree.item_selected.connect(lambda _: self._render_rows())
        layout.addWidget(self._folder_tree, 1)

        new_btn = QPushButton("New Folder")
        new_btn.setObjectName("NewFolderButton")
        new_btn.setAccessibleName("Create new folder")
        new_btn.clicked.connect(self._new_folder)
        layout.addWidget(new_btn)
        return panel

    def _refresh_folders(self) -> None:
        """Rebuild the folder tree from current source data (preserves selection)."""
        cur_key = self._selected_folder_key()

        # Aggregate counts
        cat_counts: dict[str, int] = {}
        fav_count = 0
        for r in self._rows:
            if r.category:
                cat_counts[r.category] = cat_counts.get(r.category, 0) + 1
            if r.is_favorite:
                fav_count += 1
        uncat_count = sum(1 for r in self._rows if not r.category)

        # For nested categories (e.g. "Science::Biology"), also count ancestors
        ancestor_counts: dict[str, int] = {}
        for cat, cnt in cat_counts.items():
            parts = cat.split("::")
            for depth in range(1, len(parts)):
                ancestor = "::".join(parts[:depth])
                ancestor_counts[ancestor] = ancestor_counts.get(ancestor, 0) + cnt

        items: list[dict] = []

        # Special flat items (no "::" so they stay top-level)
        items.append({"path": _ALL, "label": "All Sources", "data": _ALL,
                      "badges": [("count", len(self._rows))]})
        if fav_count:
            items.append({"path": _FAVORITES, "label": "Favorites", "data": _FAVORITES,
                          "badges": [("count", fav_count)]})

        # Named folder hierarchy (categories with "::" become nested nodes)
        all_paths = set(cat_counts.keys()) | set(ancestor_counts.keys())
        if self._pending_folder and self._pending_folder not in all_paths:
            cat_counts[self._pending_folder] = 0
            all_paths.add(self._pending_folder)

        for cat in sorted(all_paths):
            count = cat_counts.get(cat, 0) + ancestor_counts.get(cat, 0)
            items.append({"path": cat, "data": cat,
                          "badges": [("count", count)] if count else []})

        # Uncategorized at the bottom
        if uncat_count:
            items.append({"path": _UNCATEGORIZED, "label": "Uncategorized", "data": _UNCATEGORIZED,
                          "badges": [("count", uncat_count)]})

        self._folder_tree.populate(items)
        self._select_folder_key(cur_key)

    def _selected_folder_key(self) -> str:
        data = self._folder_tree.selected_data()
        return data if isinstance(data, str) else _ALL

    def _select_folder_key(self, key: str) -> None:
        """Select the tree item whose data equals *key*."""
        def _find(item) -> bool:
            if item.data(0, Qt.ItemDataRole.UserRole) == key:
                self._folder_tree.setCurrentItem(item)
                return True
            for i in range(item.childCount()):
                if _find(item.child(i)):
                    return True
            return False

        for i in range(self._folder_tree.topLevelItemCount()):
            if _find(self._folder_tree.topLevelItem(i)):
                return
        # Default to first item
        if self._folder_tree.topLevelItemCount():
            self._folder_tree.setCurrentItem(self._folder_tree.topLevelItem(0))

    def _folder_context_menu(self, pos) -> None:
        item = self._folder_tree.itemAt(pos)
        if item is None:
            return
        key = item.data(0, Qt.ItemDataRole.UserRole)
        if key in (_ALL, _FAVORITES, _UNCATEGORIZED, "", None):
            return
        menu = QMenu(self)
        menu.addAction("Rename folder…", lambda: self._rename_folder(key))
        menu.addSeparator()
        menu.addAction("Delete folder (move sources out)", lambda: self._delete_folder(key))
        menu.exec(self._folder_tree.mapToGlobal(pos))

    def _new_folder(self) -> None:
        name, ok = QInputDialog.getText(self, "New folder", "Folder name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        existing = {r.category for r in self._rows if r.category}
        if name in existing:
            self._select_folder_key(name)
            return
        self._pending_folder = name
        self._refresh_folders()
        self._select_folder_key(name)
        self._render_rows()

    def _rename_folder(self, old_name: str) -> None:
        new_name, ok = QInputDialog.getText(
            self, "Rename folder", "New name:", text=old_name
        )
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return
        new_name = new_name.strip()
        if self._context.db is None:
            return
        with self._context.db.session() as session:
            svc = SourceService(session)
            for r in self._rows:
                if r.category == old_name:
                    svc.set_category(r.id, new_name)
        if self._pending_folder == old_name:
            self._pending_folder = new_name
        self.refresh()

    def _delete_folder(self, folder_name: str) -> None:
        sources_in = [r for r in self._rows if r.category == folder_name]
        n = len(sources_in)
        confirm = QMessageBox.question(
            self, "Delete folder",
            f"Remove folder \"{folder_name}\"? "
            f"The {n} source{'s' if n != 1 else ''} in it will become uncategorized.",
        )
        if confirm != QMessageBox.StandardButton.Yes or self._context.db is None:
            return
        with self._context.db.session() as session:
            svc = SourceService(session)
            for r in sources_in:
                svc.set_category(r.id, "")
        if self._pending_folder == folder_name:
            self._pending_folder = None
        self.refresh()

    # ── Browser (source list) ────────────────────────────────────────────────

    def _build_browser(self) -> QWidget:
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Library")
        title.setObjectName("TopTitle")
        import_btn = QPushButton("Import file")
        import_btn.setAccessibleName("Import source file")
        import_btn.clicked.connect(self._import)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(import_btn)
        layout.addLayout(header)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search sources…")
        self._search.setAccessibleName("Search sources")
        self._search.textChanged.connect(lambda _: self._render_rows())
        layout.addWidget(self._search)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._list_container = QWidget()
        self._list_container.setObjectName("Page")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setSpacing(8)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._list_container)
        layout.addWidget(scroll, 1)
        return page

    # ── Data ─────────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        self._rows = []
        if self._context.db is not None:
            with self._context.db.session() as session:
                svc = SourceService(session)
                self._rows = [
                    _Row(
                        d.id, d.title, d.page_count, d.last_opened_page,
                        d.is_favorite, d.category, [t.name for t in d.tags], d.kind,
                    )
                    for d in svc.list_sources()
                ]
        # Clear pending folder once it has real sources
        if self._pending_folder:
            if any(r.category == self._pending_folder for r in self._rows):
                self._pending_folder = None
        self._refresh_folders()
        self._render_rows()

    def _render_rows(self) -> None:
        clear_layout(self._list_layout)

        if self._context.db is None:
            self._list_layout.addWidget(QLabel("No database available."))
            return

        key   = self._selected_folder_key()
        query = self._search.text().lower().strip()
        rows  = [
            r for r in self._rows
            if self._matches_folder(r, key)
            and (not query or query in r.title.lower())
        ]
        if not rows:
            msg = (
                "No sources in this folder yet. Right-click a source to move it here."
                if key not in (_ALL, _FAVORITES, _UNCATEGORIZED)
                else "No sources here yet. Import a file to start reading."
            )
            lbl = QLabel(msg)
            lbl.setObjectName("PageSubtitle")
            lbl.setWordWrap(True)
            self._list_layout.addWidget(lbl)
            return
        for row in rows:
            self._list_layout.addWidget(self._source_row(row))

    @staticmethod
    def _matches_folder(row: _Row, key: str) -> bool:
        if key == _ALL:
            return True
        if key == _FAVORITES:
            return row.is_favorite
        if key == _UNCATEGORIZED:
            return not row.category
        # Match exact folder or any sub-folder (Science matches Science::Biology)
        return row.category == key or (
            row.category is not None and is_child_of(row.category, key)
        )

    # ── Source rows ──────────────────────────────────────────────────────────

    def _source_row(self, row: _Row) -> QWidget:
        widget = QWidget()
        widget.setObjectName("DeckRow")
        widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        widget.customContextMenuRequested.connect(
            lambda pos, r=row, w=widget: self._source_menu(r, w, pos)
        )
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        kind_lbl = QLabel(row.kind.upper())
        kind_lbl.setObjectName("KindBadge")
        kind_lbl.setFixedWidth(36)
        kind_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(kind_lbl)

        star = "* " if row.is_favorite else ""
        name = ElidedLabel(star + row.title)
        name.setObjectName("DeckName")
        name.setAccessibleName(row.title)
        layout.addWidget(name, 1)

        meta_bits: list[str] = []
        if row.category:
            meta_bits.append(row.category)
        if row.tags:
            meta_bits.append(" ".join(f"#{t}" for t in row.tags))
        meta_bits.append(f"{row.page_count} page{'s' if row.page_count != 1 else ''}")
        if row.page_count > 0 and row.last_opened_page > 1:
            meta_bits.append(f"p.{row.last_opened_page}/{row.page_count}")
        meta = ElidedLabel("  ·  ".join(meta_bits))
        meta.setObjectName("SettingsHint")
        meta.setMaximumWidth(280)
        layout.addWidget(meta)

        open_btn = QPushButton("Open")
        open_btn.setAccessibleName(f"Open {row.title}")
        open_btn.clicked.connect(lambda _=False, sid=row.id: self._open(sid))
        layout.addWidget(open_btn)
        return widget

    def _source_menu(self, row: _Row, anchor: QWidget, pos) -> None:
        menu = QMenu(self)
        menu.addAction(
            "Unfavorite" if row.is_favorite else "Favorite",
            lambda: self._set(lambda s: s.set_favorite(row.id, not row.is_favorite)),
        )
        menu.addAction("Rename…", lambda: self._rename(row))

        # "Move to folder" replaces the old "Set category…" plain-text input
        folder_menu = menu.addMenu("Move to folder")
        if folder_menu is not None:
            existing_folders = sorted({r.category for r in self._rows if r.category})
            for cat in existing_folders:
                folder_menu.addAction(
                    cat,
                    lambda _=False, c=cat: self._set(lambda s: s.set_category(row.id, c)),
                )
            folder_menu.addSeparator()
            folder_menu.addAction("New folder…", lambda: self._move_to_new_folder(row))
            if row.category:
                folder_menu.addSeparator()
                folder_menu.addAction(
                    "Remove from folder",
                    lambda: self._set(lambda s: s.set_category(row.id, "")),
                )

        menu.addAction("Set tags…", lambda: self._set_tags(row))
        menu.addSeparator()
        menu.addAction("Remove", lambda: self._delete(row.id, row.title))
        menu.exec(anchor.mapToGlobal(pos))

    # ── Actions ───────────────────────────────────────────────────────────────

    def _set(self, fn) -> None:
        if self._context.db is None:
            return
        with self._context.db.session() as session:
            fn(SourceService(session))
        self.refresh()

    def _rename(self, row: _Row) -> None:
        title, ok = QInputDialog.getText(
            self, "Rename source", "Title:", text=row.title
        )
        if ok and title.strip():
            self._set(lambda s: s.rename(row.id, title.strip()))

    def _move_to_new_folder(self, row: _Row) -> None:
        name, ok = QInputDialog.getText(self, "New folder", "Folder name:")
        if ok and name.strip():
            self._set(lambda s: s.set_category(row.id, name.strip()))

    def _set_tags(self, row: _Row) -> None:
        text, ok = QInputDialog.getText(
            self, "Set tags", "Tags (comma-separated):", text=", ".join(row.tags)
        )
        if ok:
            names = [t.strip() for t in text.split(",") if t.strip()]
            self._set(lambda s: s.set_tags(row.id, names))

    def _import(self) -> None:
        if self._context.db is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import source",
            "",
            "PDF files (*.pdf);;Text files (*.txt);;Markdown files (*.md)",
        )
        if not path:
            return
        try:
            with self._context.db.session() as session:
                svc = SourceService(session)
                suffix = Path(path).suffix.lower()
                if suffix == ".pdf":
                    svc.import_pdf(path)
                elif suffix in {".txt", ".md"}:
                    svc.import_text(
                        path, kind="markdown" if suffix == ".md" else "text"
                    )
                else:
                    raise ValueError("Unsupported file type")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(
                self, "Import failed", f"Could not import that source:\n{exc}"
            )
        self.refresh()

    def _open(self, source_id: int) -> None:
        self._reader.open_source(source_id)
        self._right_stack.setCurrentWidget(self._reader)

    def _on_reader_finished(self) -> None:
        self._right_stack.setCurrentWidget(self._placeholder)
        self.refresh()

    def _delete(self, source_id: int, title: str) -> None:
        confirm = QMessageBox.question(
            self, "Remove source",
            f"Remove \"{title}\" from the library? The file stays on your disk.",
        )
        if confirm == QMessageBox.StandardButton.Yes and self._context.db is not None:
            with self._context.db.session() as session:
                SourceService(session).delete(source_id)
            self.refresh()

    def _build_placeholder(self) -> QWidget:
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        apply_page_margins(layout, self._context)
        layout.setSpacing(12)
        lbl = QLabel("Select a source from the left pane to open it.")
        lbl.setObjectName("PageSubtitle")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        layout.addStretch(1)
        return page

    def showEvent(self, event: QShowEvent) -> None:  # type: ignore[override]
        super().showEvent(event)
        self.refresh()
