"""Create a custom note type (Advanced mode): name, fields, and one card template.

Multi-template editing is deferred; a single front/back template covers custom
basic-style and cloze types. Gated to Advanced mode by the caller.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from data.repositories.note_type_repository import NoteTypeRepository
from domain.notes.note_type_service import NoteTypeService


class NoteTypeEditor(QDialog):
    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setWindowTitle("New note type")
        self.setAccessibleName("New note type")
        self.resize(600, 640)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(8)

        root.addWidget(self._label("Name"))
        self.name_input = QLineEdit()
        self.name_input.setAccessibleName("Note type name")
        root.addWidget(self.name_input)

        root.addWidget(self._label("Fields (one per line)"))
        self.fields_input = QPlainTextEdit("Front\nBack")
        self.fields_input.setFixedHeight(110)
        self.fields_input.setAccessibleName("Fields")
        root.addWidget(self.fields_input)

        self.cloze_check = QCheckBox("Cloze type — use {{cloze:Field}} with {{c1::answer}} markup")
        self.cloze_check.setAccessibleName("Cloze type")
        root.addWidget(self.cloze_check)

        root.addWidget(self._label("Card front (HTML — use {{FieldName}})"))
        self.front_input = QPlainTextEdit("{{Front}}")
        self.front_input.setFixedHeight(90)
        self.front_input.setAccessibleName("Card front template")
        root.addWidget(self.front_input)

        root.addWidget(self._label("Card back (HTML)"))
        self.back_input = QPlainTextEdit("{{Front}}<hr>{{Back}}")
        self.back_input.setFixedHeight(90)
        self.back_input.setAccessibleName("Card back template")
        root.addWidget(self.back_input)

        root.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        return label

    def _save(self) -> None:
        name = self.name_input.text().strip()
        fields = [line.strip() for line in self.fields_input.toPlainText().splitlines() if line.strip()]
        if not name:
            QMessageBox.warning(self, "New note type", "Please enter a name.")
            return
        if not fields:
            QMessageBox.warning(self, "New note type", "Please add at least one field.")
            return
        if self._context.db is None:
            return
        try:
            with self._context.db.session() as session:
                if NoteTypeRepository(session).by_name(name) is not None:
                    QMessageBox.warning(self, "New note type", f"A note type named “{name}” already exists.")
                    return
                NoteTypeService(session).create_type(
                    name,
                    fields,
                    [("Card 1", self.front_input.toPlainText(), self.back_input.toPlainText())],
                    is_cloze=self.cloze_check.isChecked(),
                )
        except Exception:
            QMessageBox.warning(self, "New note type", "Couldn't create the note type. Please try again.")
            return
        self.accept()
