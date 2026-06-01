"""The Cards page: deck browser → per-note browser → guided review.

Deck rows show live New/Learning/Review counts, open into their notes, and offer
a right-click context menu (favorite / rename / category / color / delete).
"New note type" appears only in Advanced mode.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QShowEvent
from PyQt6.QtWidgets import (
    QColorDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from domain.decks.deck_service import DeckService, DeckSummary
from ui.components.badges import StateBadges
from ui.views.note_form import AddNoteDialog
from ui.views.note_type_editor import NoteTypeEditor
from ui.views.notes_view import NotesView
from ui.views.review_view import ReviewView

_DECKS_PAGE = 0
_NOTES_PAGE = 1
_REVIEW_PAGE = 2


class CardsView(QWidget):
    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setObjectName("Page")
        self.setAccessibleName("Cards")
        self._review_return = _DECKS_PAGE

        self._stack = QStackedWidget()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._stack)

        self._browser = self._build_browser()
        self._notes = NotesView(context)
        self._notes.back.connect(self._show_decks)
        self._notes.review_requested.connect(lambda did: self._start_review(did, _NOTES_PAGE))
        self._review = ReviewView(context)
        self._review.finished.connect(self._on_review_finished)

        self._stack.addWidget(self._browser)  # 0
        self._stack.addWidget(self._notes)    # 1
        self._stack.addWidget(self._review)   # 2

        self.refresh()

    # -- deck browser -------------------------------------------------------

    def _build_browser(self) -> QWidget:
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 24, 40, 24)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Decks")
        title.setObjectName("TopTitle")
        self._new_type_btn = QPushButton("New note type")
        self._new_type_btn.setAccessibleName("New note type")
        self._new_type_btn.clicked.connect(self._new_note_type)
        add_note = QPushButton("Add note")
        add_note.setAccessibleName("Add note")
        add_note.clicked.connect(self._add_note)
        new_deck = QPushButton("New deck")
        new_deck.setAccessibleName("New deck")
        new_deck.clicked.connect(self._new_deck)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self._new_type_btn)
        header.addWidget(add_note)
        header.addWidget(new_deck)
        layout.addLayout(header)

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

    def refresh(self) -> None:
        self._new_type_btn.setVisible(self._context.settings.get("mode") == "advanced")
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if self._context.db is None:
            self._list_layout.addWidget(QLabel("No database available."))
            return

        with self._context.db.session() as session:
            summaries = DeckService(session).list_summaries("card")

        if not summaries:
            empty = QLabel("No decks yet. Create one to get started.")
            empty.setObjectName("PageSubtitle")
            self._list_layout.addWidget(empty)
            return
        for summary in summaries:
            self._list_layout.addWidget(self._deck_row(summary))

    def _deck_row(self, summary: DeckSummary) -> QWidget:
        deck = summary.deck
        row = QWidget()
        row.setObjectName("DeckRow")
        row.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        row.customContextMenuRequested.connect(
            lambda pos, d=deck.id, n=deck.name, fav=deck.is_favorite, dft=deck.is_default, r=row:
            self._deck_menu(d, n, fav, dft, r, pos)
        )
        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        if deck.color:
            swatch = QLabel()
            swatch.setFixedSize(12, 12)
            swatch.setStyleSheet(f"background-color: {deck.color}; border-radius: 3px;")
            layout.addWidget(swatch)

        name = QLabel(deck.name + (" ⭐" if deck.is_favorite else ""))
        name.setObjectName("DeckName")
        layout.addWidget(name, 1)
        layout.addWidget(StateBadges(summary.new, summary.learning, summary.review))

        open_btn = QPushButton("Open")
        open_btn.setAccessibleName(f"Open {deck.name}")
        open_btn.clicked.connect(lambda _=False, d=deck.id, n=deck.name: self._open_deck(d, n))
        layout.addWidget(open_btn)

        review_btn = QPushButton("Review")
        review_btn.setAccessibleName(f"Review {deck.name}")
        review_btn.setEnabled(summary.total > 0)
        review_btn.clicked.connect(lambda _=False, d=deck.id: self._start_review(d, _DECKS_PAGE))
        layout.addWidget(review_btn)
        return row

    def _deck_menu(self, deck_id, name, is_favorite, is_default, row, pos) -> None:
        menu = QMenu(self)
        menu.addAction("Unfavorite" if is_favorite else "Favorite",
                       lambda: self._set_favorite(deck_id, not is_favorite))
        menu.addAction("Rename…", lambda: self._rename(deck_id, name))
        menu.addAction("Set category…", lambda: self._set_category(deck_id))
        menu.addAction("Set color…", lambda: self._set_color(deck_id))
        if not is_default:
            menu.addSeparator()
            menu.addAction("Delete", lambda: self._delete_deck(deck_id, name))
        menu.exec(row.mapToGlobal(pos))

    # -- deck actions -------------------------------------------------------

    def _with_decks(self, fn) -> None:
        with self._context.db.session() as session:
            fn(DeckService(session))
        self.refresh()

    def _new_deck(self) -> None:
        if self._context.db is None:
            return
        name, ok = QInputDialog.getText(self, "New deck", "Deck name:")
        if ok and name.strip():
            self._with_decks(lambda svc: svc.create(name.strip()))

    def _set_favorite(self, deck_id, favorite) -> None:
        self._with_decks(lambda svc: svc.set_favorite(deck_id, favorite))

    def _rename(self, deck_id, current) -> None:
        name, ok = QInputDialog.getText(self, "Rename deck", "New name:", text=current)
        if ok and name.strip():
            self._with_decks(lambda svc: svc.rename(deck_id, name.strip()))

    def _set_category(self, deck_id) -> None:
        category, ok = QInputDialog.getText(self, "Set category", "Category (blank to clear):")
        if ok:
            self._with_decks(lambda svc: svc.set_category(deck_id, category.strip() or None))

    def _set_color(self, deck_id) -> None:
        color = QColorDialog.getColor(QColor("#5c7cfa"), self, "Deck color")
        if color.isValid():
            self._with_decks(lambda svc: svc.set_color(deck_id, color.name()))

    def _delete_deck(self, deck_id, name) -> None:
        confirm = QMessageBox.question(
            self, "Delete deck",
            f"Delete “{name}” and all its notes and cards?",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self._with_decks(lambda svc: svc.delete(deck_id))

    def _add_note(self) -> None:
        if self._context.db is None:
            return
        if AddNoteDialog(self._context, parent=self).exec():
            self.refresh()

    def _new_note_type(self) -> None:
        if self._context.db is None:
            return
        NoteTypeEditor(self._context, parent=self).exec()

    # -- navigation ---------------------------------------------------------

    def _open_deck(self, deck_id, name) -> None:
        self._notes.open_deck(deck_id, name)
        self._stack.setCurrentIndex(_NOTES_PAGE)

    def _show_decks(self) -> None:
        self._stack.setCurrentIndex(_DECKS_PAGE)
        self.refresh()

    def _start_review(self, deck_id, return_page) -> None:
        self._review_return = return_page
        self._review.start(deck_id)
        self._stack.setCurrentIndex(_REVIEW_PAGE)

    def _on_review_finished(self) -> None:
        self._stack.setCurrentIndex(self._review_return)
        if self._review_return == _NOTES_PAGE:
            self._notes.refresh()
        else:
            self.refresh()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._stack.currentIndex() == _DECKS_PAGE:
            self.refresh()
