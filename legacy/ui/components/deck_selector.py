"""DeckSelector — QComboBox populated from DeckService."""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget

from services.cards.deck_service import DeckService


class DeckSelector(QWidget):
    """Labelled combo box that lists decks of a given type.

    Emits deck_changed(deck_id) whenever the selection changes.
    Call refresh() to reload the list from the database.
    """

    deck_changed = pyqtSignal(int)   # deck_id; -1 when nothing selected

    def __init__(self, deck_type: str, label: str = "Deck:", parent=None) -> None:
        super().__init__(parent)
        self._deck_type = deck_type
        self._svc = DeckService()
        self._ids: list[int] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(label))
        self._combo = QComboBox()
        self._combo.setMinimumWidth(180)
        self._combo.currentIndexChanged.connect(self._on_changed)
        layout.addWidget(self._combo)

        self.refresh()

    def refresh(self) -> None:
        self._combo.blockSignals(True)
        prev_id = self.current_deck_id()
        self._combo.clear()
        self._ids = []
        for deck in self._svc.get_all(self._deck_type):
            self._combo.addItem(deck.name)
            self._ids.append(deck.id)
        # Restore previous selection if still present
        if prev_id in self._ids:
            self._combo.setCurrentIndex(self._ids.index(prev_id))
        self._combo.blockSignals(False)
        self._on_changed(self._combo.currentIndex())

    def current_deck_id(self) -> int:
        idx = self._combo.currentIndex()
        return self._ids[idx] if 0 <= idx < len(self._ids) else -1

    def _on_changed(self, idx: int) -> None:
        if 0 <= idx < len(self._ids):
            self.deck_changed.emit(self._ids[idx])
