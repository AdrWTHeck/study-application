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
        # Rounded state pills (clay redesign); each carries its label text,
        # never colour alone (VIS-03). The [badge] property is kept for any
        # remaining flat-text QSS rules.
        pill_names = {"new": "StatePillNew", "learning": "StatePillLearning",
                      "review": "StatePillReview"}
        for kind in ("new", "learning", "review"):
            label = QLabel()
            label.setObjectName(pill_names[kind])
            label.setProperty("badge", kind)
            layout.addWidget(label)
            self._labels[kind] = label
        self.set_counts(new, learning, review)

    def set_counts(self, new: int, learning: int, review: int) -> None:
        # Only show buckets that have cards, so a typical single-card note reads
        # "1 new" rather than "1 new · 0 learning · 0 review".
        for kind, value in (("new", new), ("learning", learning), ("review", review)):
            label = self._labels[kind]
            label.setText(f"{value} {kind}")
            label.setVisible(value > 0)
