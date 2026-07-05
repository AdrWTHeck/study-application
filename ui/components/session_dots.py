"""Review-session progress dots (clay redesign session header).

Purely decorative reinforcement of the mono "N of M" counter label that always
sits next to it — the dots are never the only progress indicator (VIS-03). At
large queue sizes the row would become noise, so beyond ``MAX_DOTS`` the
widget hides itself and the counter alone carries the information.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QSizePolicy, QWidget

MAX_DOTS = 30


class SessionDots(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current = 0
        self._total = 0
        self._done_color = QColor("#888888")
        self._current_color = QColor("#aaaaaa")
        self._dot = 7
        self._gap = 7
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(self._dot + 6)

    def set_colors(self, done: QColor, current: QColor) -> None:
        self._done_color = QColor(done)
        self._current_color = QColor(current)
        self.update()

    def set_progress(self, current: int, total: int) -> None:
        """*current* is 1-based (card being shown); *total* is queue length."""
        self._current = max(0, current)
        self._total = max(0, total)
        visible = 0 < self._total <= MAX_DOTS
        self.setVisible(visible)
        self.setAccessibleName(f"Progress: card {self._current} of {self._total}")
        if visible:
            self.setFixedWidth(self._total * self._dot + (self._total - 1) * self._gap + 4)
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        if not (0 < self._total <= MAX_DOTS):
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        remaining = QColor(self._done_color)
        remaining.setAlpha(60)
        y = (self.height() - self._dot) / 2
        for i in range(self._total):
            index = i + 1
            if index < self._current:
                painter.setBrush(self._done_color)
            elif index == self._current:
                painter.setBrush(self._current_color)
            else:
                painter.setBrush(remaining)
            x = 2 + i * (self._dot + self._gap)
            if index == self._current:
                painter.drawEllipse(int(x) - 1, int(y) - 1, self._dot + 2, self._dot + 2)
            else:
                painter.drawEllipse(int(x), int(y), self._dot, self._dot)
        painter.end()
