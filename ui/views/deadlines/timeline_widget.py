"""Horizontal deadline timeline widget with milestone dots."""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFontMetrics, QPaintEvent, QPainter, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

from ui.theme.tokens import Palette


class TimelineWidget(QWidget):
    """Draws a horizontal deadline timeline — start, today dot, end, optional phase label."""

    _LINE_Y = 18
    _DOT_R = 4
    _TODAY_R = 7
    _LBL_Y = 30

    def __init__(
        self,
        start_date: date,
        end_date: date,
        today: date,
        phase: str | None,
        palette: Palette,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._start = start_date
        self._end = end_date
        self._today = today
        self._phase = phase
        self._pal = palette

        self.setFixedHeight(48)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setAccessibleName(
            f"Timeline: started {start_date}, deadline {end_date}, today {today}"
        )

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        pal = self._pal
        pad = 12
        left = pad
        right = width - pad
        span = max(left + 1, right - left)

        total_days = max(1, (self._end - self._start).days)
        elapsed_days = (self._today - self._start).days
        progress = max(0.0, min(1.0, elapsed_days / total_days))

        def x_at(frac: float) -> int:
            return int(left + frac * span)

        today_x = x_at(progress)
        c_filled = QColor(pal.accent)
        c_empty = QColor(pal.border)
        c_today = QColor(pal.accent)
        c_text = QColor(pal.text_dim)
        c_phase = QColor(pal.text_secondary)
        c_bg = QColor(pal.bg_surface)

        painter.setPen(QPen(c_empty, 2))
        painter.drawLine(left, self._LINE_Y, right, self._LINE_Y)

        if today_x > left:
            painter.setPen(QPen(c_filled, 2))
            painter.drawLine(left, self._LINE_Y, today_x, self._LINE_Y)

        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            marker_x = x_at(frac)
            passed = frac < progress
            painter.setPen(QPen(c_filled if passed else c_empty, 1))
            painter.setBrush(QBrush(c_filled if passed else c_bg))
            r = self._DOT_R
            painter.drawEllipse(marker_x - r, self._LINE_Y - r, r * 2, r * 2)

        painter.setPen(QPen(c_today, 2))
        painter.setBrush(QBrush(c_today))
        r = self._TODAY_R
        painter.drawEllipse(today_x - r, self._LINE_Y - r, r * 2, r * 2)

        font = self.font()
        font.setPointSize(max(7, font.pointSize() - 2))
        painter.setFont(font)
        fm = QFontMetrics(font)
        asc = fm.ascent()

        painter.setPen(QPen(c_text, 1))
        start_str = f"{self._start.strftime('%b')} {self._start.day}"
        painter.drawText(left, self._LBL_Y + asc, start_str)

        end_str = f"{self._end.strftime('%b')} {self._end.day}"
        end_width = fm.horizontalAdvance(end_str)
        painter.drawText(right - end_width, self._LBL_Y + asc, end_str)

        if self._phase:
            painter.setPen(QPen(c_phase, 1))
            phase_w = fm.horizontalAdvance(self._phase)
            phase_x = max(left, min(today_x - phase_w // 2, right - phase_w))
            painter.drawText(phase_x, self._LINE_Y - self._TODAY_R - 3, self._phase)

        painter.end()
