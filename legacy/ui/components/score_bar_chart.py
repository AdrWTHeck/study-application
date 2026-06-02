"""ScoreBarChart — custom QWidget that paints per-deck score bars."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QWidget

from config.constants import SCORE_BAR_AMBER_THRESHOLD, SCORE_BAR_GREEN_THRESHOLD

_GREEN = QColor("#43A047")
_AMBER = QColor("#FB8C00")
_RED   = QColor("#E53935")


class ScoreBarChart(QWidget):
    """Vertical bar chart for per-deck scores in a comprehensive test.

    Call set_data({label: score_percent}) to update.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._data: dict[str, float] = {}
        self.setMinimumSize(200, 120)

    def set_data(self, data: dict[str, float]) -> None:
        self._data = dict(data)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if not self._data:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        margin_bottom = 30
        margin_top = 20
        n = len(self._data)
        gap = 6
        bar_w = max(20, (w - gap * (n + 1)) // n)
        y_max = h - margin_bottom

        small_font = QFont()
        small_font.setPointSize(max(8, small_font.pointSize() - 2))
        painter.setFont(small_font)

        for i, (label, score) in enumerate(self._data.items()):
            x = gap + i * (bar_w + gap)
            bar_h = int((y_max - margin_top) * max(0.0, score) / 100)
            y = y_max - bar_h

            color = (
                _GREEN if score >= SCORE_BAR_GREEN_THRESHOLD
                else _AMBER if score >= SCORE_BAR_AMBER_THRESHOLD
                else _RED
            )
            painter.fillRect(x, y, bar_w, bar_h, color)

            painter.setPen(Qt.GlobalColor.black)
            # Score label above bar
            painter.drawText(x, max(margin_top, y - 4), f"{score:.0f}%")
            # Deck label below bar
            truncated = (label[:8] + "…") if len(label) > 9 else label
            painter.drawText(x, h - 6, truncated)

        painter.end()
