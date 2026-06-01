"""Note dialog — create a new note or edit an existing one.

Adding a *note* is allowed in any mode; creating a new note *type* is the
Advanced-only action (NoteTypeEditor). In edit mode the deck/type are locked and
only field values change. Field inputs rebuild when the note type changes.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from data.repositories.deck_repository import DeckRepository
from data.repositories.note_repository import NoteRepository
from data.repositories.note_type_repository import NoteTypeRepository
from domain.notes.note_service import NoteService


class AddNoteDialog(QDialog):
    def __init__(
        self,
        context: AppContext,
        deck_id: int | None = None,
        note_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._note_id = note_id
        editing = note_id is not None
        self.setWindowTitle("Edit note" if editing else "Add note")
        self.setAccessibleName("Edit note" if editing else "Add note")
        self.resize(560, 560)

        self._types: list[tuple[int, str]] = []
        self._type_fields: dict[int, list[str]] = {}
        self._decks: list[tuple[int, str]] = []
        self._field_inputs: dict[str, QPlainTextEdit] = {}
        self._prefill: dict[str, str] = {}
        self._tags_prefill = ""
        edit_type_id: int | None = None
        edit_deck_id: int | None = deck_id

        with context.db.session() as session:
            for note_type in NoteTypeRepository(session).all_ordered():
                self._types.append((note_type.id, note_type.name))
                self._type_fields[note_type.id] = [f.name for f in note_type.fields]
            for deck in DeckRepository(session).by_type("card"):
                self._decks.append((deck.id, deck.name))
            if editing:
                note = NoteRepository(session).get(note_id)
                if note is not None:
                    edit_type_id = note.note_type_id
                    edit_deck_id = note.deck_id
                    self._prefill = note.values_by_field_name()
                    self._tags_prefill = ", ".join(t.name for t in note.tags)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(8)

        root.addWidget(self._label("Deck"))
        self.deck_combo = QComboBox()
        self.deck_combo.setAccessibleName("Deck")
        self.deck_combo.addItems([name for _, name in self._decks])
        self._select(self.deck_combo, self._decks, edit_deck_id)
        root.addWidget(self.deck_combo)

        root.addWidget(self._label("Note type"))
        self.type_combo = QComboBox()
        self.type_combo.setAccessibleName("Note type")
        self.type_combo.addItems([name for _, name in self._types])
        self.type_combo.currentIndexChanged.connect(self._rebuild_fields)
        root.addWidget(self.type_combo)

        self._fields_container = QWidget()
        self._fields_layout = QVBoxLayout(self._fields_container)
        self._fields_layout.setContentsMargins(0, 8, 0, 0)
        self._fields_layout.setSpacing(6)
        root.addWidget(self._fields_container)

        root.addWidget(self._label("Tags (comma-separated)"))
        self.tags_input = QLineEdit(self._tags_prefill)
        self.tags_input.setAccessibleName("Tags")
        root.addWidget(self.tags_input)

        root.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        if editing:
            self._select(self.type_combo, self._types, edit_type_id)
            self.type_combo.setEnabled(False)
            self.deck_combo.setEnabled(False)
        self._rebuild_fields()

    # -- helpers ------------------------------------------------------------

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        return label

    @staticmethod
    def _select(combo: QComboBox, pairs: list[tuple[int, str]], value: int | None) -> None:
        if value is None:
            return
        for i, (item_id, _) in enumerate(pairs):
            if item_id == value:
                combo.setCurrentIndex(i)
                return

    def _rebuild_fields(self) -> None:
        while self._fields_layout.count():
            item = self._fields_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._field_inputs = {}
        if not self._types:
            return
        type_id = self._types[self.type_combo.currentIndex()][0]
        for name in self._type_fields.get(type_id, []):
            self._fields_layout.addWidget(self._label(name))
            editor = QPlainTextEdit()
            editor.setFixedHeight(72)
            editor.setAccessibleName(name)
            editor.setPlainText(self._prefill.get(name, ""))
            self._fields_layout.addWidget(editor)
            self._field_inputs[name] = editor

    def _save(self) -> None:
        if not self._types or not self._decks:
            self.reject()
            return
        values = {name: editor.toPlainText() for name, editor in self._field_inputs.items()}
        tags = [t.strip() for t in self.tags_input.text().split(",") if t.strip()]
        with self._context.db.session() as session:
            service = NoteService(session, self._context.engine)
            if self._note_id is not None:
                note = NoteRepository(session).get(self._note_id)
                if note is not None:
                    service.update_values(note, values)
                    note.tags = [service._get_or_create_tag(t) for t in tags]
            else:
                type_id = self._types[self.type_combo.currentIndex()][0]
                deck_id = self._decks[self.deck_combo.currentIndex()][0]
                service.create_note(deck_id, type_id, values, tags)
        self.accept()
