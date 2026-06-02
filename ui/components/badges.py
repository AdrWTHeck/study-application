"""StateBadges — the New/Learning/Review count chips, shared by deck and note rows.

Centralizes the badge rendering so the colors/labels stay consistent everywhere
(VIS-03: each bucket carries its label text, never color alone).
"""
from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget


class StateBadges(QWidget):
    def __init__(self, new: int = 0, learning: int = 0, review: int = 0,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self._labels: dict[str, QLabel] = {}
        for kind in ("new", "learning", "review"):
            label = QLabel()
            label.setProperty("badge", kind)
            layout.addWidget(label)
            self._labels[kind] = label
        self.set_counts(new, learning, review)

    def set_counts(self, new: int, learning: int, review: int) -> None:
        self._labels["new"].setText(f"{new} new")
        self._labels["learning"].setText(f"{learning} learning")
        self._labels["review"].setText(f"{review} review")
