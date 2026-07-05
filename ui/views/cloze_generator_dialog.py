"""Generate a line-completion cloze deck from pasted text (poem / lyrics / speech).

Each line becomes a card whose cloze hides the next line. The cards go into a
chosen existing card deck, or a new deck created from the given name.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
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
from domain.decks.deck_service import DeckService
from domain.notes.cloze_generator import ClozeDeckBuilder


class ClozeGeneratorDialog(QDialog):
    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setWindowTitle("Generate cloze deck")
        self.setAccessibleName("Generate cloze deck")
        self.resize(560, 560)
        self.created_count = 0

        self._decks: list[tuple[int, str]] = []
        if context.db is not None:
            with context.db.session() as session:
                self._decks = [(d.id, d.name) for d in DeckService(session).decks.by_type("card")]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(8)

        intro = QLabel("Paste a poem, lyrics, or a speech. Each line becomes a card "
                       "whose blank is the next line.")
        intro.setObjectName("SettingsHint")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addWidget(self._label("Add to deck"))
        self.deck_combo = QComboBox()
        self.deck_combo.setAccessibleName("Target deck")
        self.deck_combo.addItems([name for _, name in self._decks])
        layout.addWidget(self.deck_combo)

        layout.addWidget(self._label("…or new deck name (optional)"))
        self.new_deck_name = QLineEdit()
        self.new_deck_name.setAccessibleName("New deck name")
        self.new_deck_name.setPlaceholderText("Leave blank to use the deck above")
        layout.addWidget(self.new_deck_name)

        layout.addWidget(self._label("Text"))
        self.text = QPlainTextEdit()
        self.text.setAccessibleName("Source text")
        layout.addWidget(self.text, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Generate")
        buttons.accepted.connect(self._generate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        return label

    def _generate(self) -> None:
        text = self.text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Generate cloze deck", "Please paste some text.")
            return
        # Each line's blank is the next line, so we need at least two lines.
        # Validate up front so an unusable paste never leaves an empty deck behind.
        if len([ln for ln in text.splitlines() if ln.strip()]) < 2:
            QMessageBox.warning(self, "Generate cloze deck", "Add at least two lines of text.")
            return
        new_name = self.new_deck_name.text().strip()
        if not new_name and not self._decks:
            QMessageBox.warning(self, "Generate cloze deck", "Create a deck first, or enter a new deck name.")
            return
        if self._context.db is None:
            return
        try:
            with self._context.db.session() as session:
                if new_name:
                    deck_id = DeckService(session).create(new_name).id
                else:
                    deck_id = self._decks[self.deck_combo.currentIndex()][0]
                self.created_count = ClozeDeckBuilder(session, self._context.engine).build(deck_id, text)
        except Exception:
            QMessageBox.warning(self, "Generate cloze deck", "Couldn't generate the deck. Please try again.")
            return
        if self.created_count == 0:
            QMessageBox.warning(self, "Generate cloze deck", "Add at least two lines of text.")
            return
        self.accept()
