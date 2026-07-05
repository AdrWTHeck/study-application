"""Per-note browser for one deck: preview + card states, with right-click
Edit / Move / Delete and multi-select bulk actions.

Reads notes within a session and captures primitives (id, preview, state text)
so the rows stay valid after the session closes.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
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
from ui.a11y.contrast import contrast_ratio
from ui.components.badges import StateBadges
from ui.utils.layouts import apply_page_margins, clear_layout
from ui.views.note_form import AddNoteDialog


def _chip_text_color(hex_bg: str) -> str:
    """Return white or near-black — whichever gives better contrast on hex_bg."""
    try:
        white = contrast_ratio("#ffffff", hex_bg)
        black = contrast_ratio("#1a1b1e", hex_bg)
        return "#ffffff" if white >= black else "#1a1b1e"
    except Exception:
        return "#ffffff"

# In-deck filters: label → set of srs_states that match (None = all).
_NOTE_FILTERS: list[tuple[str, set[str] | None]] = [
    ("All cards", None),
    ("New", {"new"}),
    ("Learning", {"learning", "relearning"}),
    ("Review", {"review"}),
]


class NotesView(QWidget):
    back = pyqtSignal()
    review_requested = pyqtSignal(int)

    def __init__(
        self,
        context: AppContext,
        embedded: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._embedded = embedded
        self.setObjectName("Page")
        self.setAccessibleName("Notes")
        self._deck_id: int | None = None
        self._checks: dict[int, QCheckBox] = {}

        root = QVBoxLayout(self)
        if embedded:
            # Hosted inside the deck-detail pane, which owns the page margins,
            # the deck title, and the Add note / Review actions.
            root.setContentsMargins(0, 0, 0, 0)
        else:
            apply_page_margins(root, self._context)
        root.setSpacing(12)

        self._header_host = QWidget()
        header = QHBoxLayout(self._header_host)
        header.setContentsMargins(0, 0, 0, 0)
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
        self._header_host.setVisible(not embedded)
        root.addWidget(self._header_host)

        # In-deck search + state filter.
        tools = QHBoxLayout()
        tools.setSpacing(8)
        self._search = QLineEdit()
        self._search.setObjectName("DeckSearch")
        self._search.setPlaceholderText("Search cards in this deck…")
        self._search.setAccessibleName("Search cards in this deck")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self.refresh)
        tools.addWidget(self._search, 1)
        self._filter = QComboBox()
        self._filter.setAccessibleName("Filter cards by state")
        for label, _states in _NOTE_FILTERS:
            self._filter.addItem(label)
        self._filter.currentIndexChanged.connect(self.refresh)
        tools.addWidget(self._filter)
        root.addLayout(tools)

        summary_row = QHBoxLayout()
        summary_row.setContentsMargins(0, 0, 0, 0)
        self._count_label = QLabel("")
        self._count_label.setObjectName("SettingsHint")
        self._state_summary = StateBadges()
        self._state_summary.setAccessibleName("Card counts by state for this deck")
        summary_row.addWidget(self._count_label)
        summary_row.addStretch(1)
        summary_row.addWidget(self._state_summary)
        root.addLayout(summary_row)

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

        if embedded:
            # Mono column-header row (clay redesign notes table).
            table_header = QWidget()
            table_header.setObjectName("NotesTableHeader")
            table_header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            th = QHBoxLayout(table_header)
            th.setContentsMargins(16, 4, 16, 4)
            col_card = QLabel("CARD")
            col_card.setAccessibleName("Card column")
            col_state = QLabel("STATE · FLAGS · ACTIONS")
            col_state.setAccessibleName("State, flags and actions column")
            th.addWidget(col_card, 1)
            th.addWidget(col_state, 0, Qt.AlignmentFlag.AlignRight)
            root.addWidget(table_header)

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
        clear_layout(self._list_layout)
        if self._context.db is None or self._deck_id is None:
            return

        query = self._search.text().strip().lower() if hasattr(self, "_search") else ""
        wanted_states = (
            _NOTE_FILTERS[self._filter.currentIndex()][1] if hasattr(self, "_filter") else None
        )

        rows: list[tuple[int, str, tuple[int, int, int], list]] = []
        total = 0
        deck_new = deck_learning = deck_review = 0
        with self._context.db.session() as session:
            for note in NoteRepository(session).for_deck(self._deck_id):
                total += 1
                values = note.values_by_field_name()
                full_text = " ".join(v.strip() for v in values.values() if v.strip())
                preview = (" · ".join(v.strip() for v in values.values() if v.strip())[:90]
                           or "(empty)")
                states = {card.srs_state for card in note.cards}
                n_new = n_learning = n_review = 0
                for card in note.cards:
                    st = card.srs_state
                    if st in ("learning", "relearning"):
                        n_learning += 1
                    elif st == "review":
                        n_review += 1
                    else:
                        n_new += 1
                deck_new += n_new
                deck_learning += n_learning
                deck_review += n_review
                flags = [(f.name, f.color) for f in note.flags]

                if query and query not in full_text.lower():
                    continue
                if wanted_states is not None and not (states & wanted_states):
                    continue
                rows.append((note.id, preview, (n_new, n_learning, n_review), flags))

        if hasattr(self, "_count_label"):
            if query or wanted_states is not None:
                self._count_label.setText(f"Showing {len(rows)} of {total} cards")
            else:
                self._count_label.setText(f"{total} card{'s' if total != 1 else ''}")
        if hasattr(self, "_state_summary"):
            self._state_summary.set_counts(deck_new, deck_learning, deck_review)

        if not rows:
            msg = ("No cards match your search." if (query or wanted_states is not None)
                   else "No notes in this deck yet. Add one to get started.")
            empty = QLabel(msg)
            empty.setObjectName("PageSubtitle")
            self._list_layout.addWidget(empty)
        for note_id, preview, counts, flags in rows:
            self._list_layout.addWidget(self._note_row(note_id, preview, counts, flags))
        self._update_selection()

    def _note_row(self, note_id: int, preview: str, counts: tuple[int, int, int], flags: list) -> QWidget:
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

        state = StateBadges(*counts)
        layout.addWidget(state)

        for name, color in flags[:3]:
            chip = QLabel(name)
            chip.setAccessibleName(f"Flag: {name}")
            chip.setStyleSheet(
                f"background-color: {color}; color: {_chip_text_color(color)};"
                " border-radius: 6px; padding: 1px 7px;"
            )
            layout.addWidget(chip)

        edit_btn = QPushButton("Edit")
        edit_btn.setAccessibleName("Edit note")
        edit_btn.clicked.connect(lambda _=False, nid=note_id: self._edit(nid))
        layout.addWidget(edit_btn)
        return row

    def _row_menu(self, note_id: int, row: QWidget, pos) -> None:
        menu = QMenu(self)
        menu.addAction("Edit", lambda: self._edit(note_id))
        menu.addAction("Move to deck…", lambda: self._move([note_id]))
        menu.addAction("Set flags…", lambda: self._set_flags(note_id))
        menu.addSeparator()
        menu.addAction("Delete", lambda: self._delete([note_id]))
        menu.exec(row.mapToGlobal(pos))

    def _set_flags(self, note_id: int) -> None:
        from ui.views.flag_editor import FlagAssignDialog

        if FlagAssignDialog(self._context, note_id, parent=self).exec():
            self.refresh()

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
