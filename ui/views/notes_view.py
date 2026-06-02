"""Per-note browser for one deck: preview + card states, with right-click
Edit / Move / Delete and multi-select bulk actions.

Reads notes within a session and captures primitives (id, preview, state text)
so the rows stay valid after the session closes.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from data.repositories.deck_repository import DeckRepository
from data.repositories.note_repository import NoteRepository
from domain.notes.note_service import NoteService
from ui.views.note_form import AddNoteDialog

_STATE_LABEL = {"new": "New", "learning": "Learning", "relearning": "Learning", "review": "Review"}


class NotesView(QWidget):
    back = pyqtSignal()
    review_requested = pyqtSignal(int)

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setObjectName("Page")
        self.setAccessibleName("Notes")
        self._deck_id: int | None = None
        self._checks: dict[int, QCheckBox] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 24, 40, 24)
        root.setSpacing(12)

        header = QHBoxLayout()
        back_btn = QPushButton("← Decks")
        back_btn.setAccessibleName("Back to decks")
        back_btn.clicked.connect(self.back.emit)
        self._title = QLabel("")
        self._title.setObjectName("TopTitle")
        add_btn = QPushButton("Add note")
        add_btn.setAccessibleName("Add note")
        add_btn.clicked.connect(self._add_note)
        review_btn = QPushButton("Review")
        review_btn.setAccessibleName("Review this deck")
        review_btn.clicked.connect(lambda: self._deck_id and self.review_requested.emit(self._deck_id))
        header.addWidget(back_btn)
        header.addSpacing(8)
        header.addWidget(self._title)
        header.addStretch(1)
        header.addWidget(add_btn)
        header.addWidget(review_btn)
        root.addLayout(header)

        self._bulk_bar = QWidget()
        bulk = QHBoxLayout(self._bulk_bar)
        bulk.setContentsMargins(0, 0, 0, 0)
        self._sel_label = QLabel("")
        self._sel_label.setObjectName("SettingsHint")
        move_sel = QPushButton("Move selected…")
        move_sel.clicked.connect(self._move_selected)
        delete_sel = QPushButton("Delete selected")
        delete_sel.clicked.connect(self._delete_selected)
        bulk.addWidget(self._sel_label)
        bulk.addStretch(1)
        bulk.addWidget(move_sel)
        bulk.addWidget(delete_sel)
        root.addWidget(self._bulk_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._list_container = QWidget()
        self._list_container.setObjectName("Page")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setSpacing(8)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._list_container)
        root.addWidget(scroll, 1)

    # -- data ---------------------------------------------------------------

    def open_deck(self, deck_id: int, deck_name: str) -> None:
        self._deck_id = deck_id
        self._title.setText(deck_name)
        self.refresh()

    def refresh(self) -> None:
        self._checks = {}
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if self._context.db is None or self._deck_id is None:
            return

        rows: list[tuple[int, str, str]] = []
        with self._context.db.session() as session:
            for note in NoteRepository(session).for_deck(self._deck_id):
                values = note.values_by_field_name()
                preview = " · ".join(v.strip() for v in values.values() if v.strip())[:90] or "(empty)"
                counts: dict[str, int] = {}
                for card in note.cards:
                    label = _STATE_LABEL.get(card.srs_state, card.srs_state)
                    counts[label] = counts.get(label, 0) + 1
                state_text = " · ".join(f"{n} {k}" for k, n in counts.items()) or "no cards"
                rows.append((note.id, preview, state_text))

        if not rows:
            empty = QLabel("No notes in this deck yet. Add one to get started.")
            empty.setObjectName("PageSubtitle")
            self._list_layout.addWidget(empty)
        for note_id, preview, state_text in rows:
            self._list_layout.addWidget(self._note_row(note_id, preview, state_text))
        self._update_selection()

    def _note_row(self, note_id: int, preview: str, state_text: str) -> QWidget:
        row = QWidget()
        row.setObjectName("DeckRow")
        row.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        row.customContextMenuRequested.connect(
            lambda pos, nid=note_id, r=row: self._row_menu(nid, r, pos)
        )
        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        check = QCheckBox()
        check.setAccessibleName("Select note")
        check.toggled.connect(self._update_selection)
        self._checks[note_id] = check
        layout.addWidget(check)

        text = QLabel(preview)
        text.setObjectName("DeckName")
        text.setWordWrap(True)
        layout.addWidget(text, 1)

        state = QLabel(state_text)
        state.setObjectName("SettingsHint")
        layout.addWidget(state)

        edit_btn = QPushButton("Edit")
        edit_btn.setAccessibleName("Edit note")
        edit_btn.clicked.connect(lambda _=False, nid=note_id: self._edit(nid))
        layout.addWidget(edit_btn)
        return row

    def _row_menu(self, note_id: int, row: QWidget, pos) -> None:
        menu = QMenu(self)
        menu.addAction("Edit", lambda: self._edit(note_id))
        menu.addAction("Move to deck…", lambda: self._move([note_id]))
        menu.addSeparator()
        menu.addAction("Delete", lambda: self._delete([note_id]))
        menu.exec(row.mapToGlobal(pos))

    # -- selection / bulk ---------------------------------------------------

    def _selected_ids(self) -> list[int]:
        return [nid for nid, check in self._checks.items() if check.isChecked()]

    def _update_selection(self, *_args) -> None:
        count = len(self._selected_ids())
        self._sel_label.setText(f"{count} selected" if count else "")
        self._bulk_bar.setVisible(bool(self._checks))

    def _delete_selected(self) -> None:
        self._delete(self._selected_ids())

    def _move_selected(self) -> None:
        self._move(self._selected_ids())

    # -- actions ------------------------------------------------------------

    def _add_note(self) -> None:
        if AddNoteDialog(self._context, deck_id=self._deck_id, parent=self).exec():
            self.refresh()

    def _edit(self, note_id: int) -> None:
        if AddNoteDialog(self._context, note_id=note_id, parent=self).exec():
            self.refresh()

    def _delete(self, ids: list[int]) -> None:
        if not ids:
            return
        confirm = QMessageBox.question(
            self, "Delete notes",
            f"Delete {len(ids)} note(s)? Their cards are removed too.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        with self._context.db.session() as session:
            service = NoteService(session, self._context.engine)
            for note_id in ids:
                service.delete_note_by_id(note_id)
        self.refresh()

    def _move(self, ids: list[int]) -> None:
        if not ids:
            return
        target = self._pick_deck()
        if target is None:
            return
        with self._context.db.session() as session:
            service = NoteService(session, self._context.engine)
            repo = NoteRepository(session)
            for note_id in ids:
                note = repo.get(note_id)
                if note is not None:
                    service.move_to_deck(note, target)
        self.refresh()

    def _pick_deck(self) -> int | None:
        with self._context.db.session() as session:
            decks = [(d.id, d.name) for d in DeckRepository(session).by_type("card")]
        decks = [(did, name) for did, name in decks if did != self._deck_id]
        if not decks:
            QMessageBox.information(self, "Move", "There are no other decks to move to.")
            return None
        names = [name for _, name in decks]
        name, ok = QInputDialog.getItem(self, "Move to deck", "Deck:", names, 0, False)
        if ok and name:
            for did, deck_name in decks:
                if deck_name == name:
                    return did
        return None
