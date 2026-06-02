"""RatingButtons — four colour-coded SM-2 rating buttons."""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from services.srs.srs_base import CardRating

_BUTTONS: list[tuple[str, str, CardRating]] = [
    ("Very Hard", "veryHardBtn", CardRating.VERY_HARD),
    ("Hard",      "hardBtn",     CardRating.HARD),
    ("Good",      "goodBtn",     CardRating.GOOD),
    ("Easy",      "easyBtn",     CardRating.EASY),
]


class RatingButtons(QWidget):
    """Horizontal row of four rating buttons; emits rating_selected(CardRating)."""

    rating_selected = pyqtSignal(object)   # CardRating

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._buttons: dict[CardRating, QPushButton] = {}
        for label, obj_name, rating in _BUTTONS:
            btn = QPushButton(label)
            btn.setObjectName(obj_name)
            btn.setMinimumWidth(80)
            btn.clicked.connect(lambda _, r=rating: self.rating_selected.emit(r))
            layout.addWidget(btn)
            self._buttons[rating] = btn

    def set_enabled(self, enabled: bool) -> None:
        for btn in self._buttons.values():
            btn.setEnabled(enabled)
