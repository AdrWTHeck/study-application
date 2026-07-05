"""A small, theme-aware donut chart with an accessible text summary.

Charts must never rely on colour alone (VIS-03), so the widget renders both the
donut and a legend line with the label, value, and percentage for each slice,
and exposes the same information via its accessible name.
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget


class _Donut(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._slices: list[tuple[str, float, str]] = []  # (label, value, color)
        self.setMinimumSize(120, 120)

    def set_slices(self, slices: list[tuple[str, float, str]]) -> None:
        self._slices = slices
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        total = sum(v for _l, v, _c in self._slices)
        side = min(self.width(), self.height()) - 8
        if side <= 0:
            return
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)

        if total <= 0:
            painter.setBrush(QColor("#888888"))
            painter.drawEllipse(rect)
        else:
            start = 90 * 16  # start at top, go clockwise
            for _label, value, color in self._slices:
                span = -int(round(360 * 16 * value / total))
                painter.setBrush(QColor(color))
                painter.drawPie(rect, start, span)
                start += span

        # Punch out the centre to make a donut (uses the page background).
        hole = rect.adjusted(side * 0.28, side * 0.28, -side * 0.28, -side * 0.28)
        bg = self.palette().window().color()
        painter.setBrush(bg)
        painter.setPen(QPen(bg))
        painter.drawEllipse(hole)
        painter.end()


class PieChart(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._donut = _Donut()
        layout.addWidget(self._donut, 0)

        self._legend = QVBoxLayout()
        self._legend.setSpacing(4)
        self._legend.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        legend_host = QWidget()
        legend_host.setLayout(self._legend)
        layout.addWidget(legend_host, 1)

    def set_data(self, slices: list[tuple[str, float, str]]) -> None:
        """slices: list of (label, value, color)."""
        self._donut.set_slices(slices)
        while self._legend.count():
            item = self._legend.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        total = sum(v for _l, v, _c in slices) or 1
        summary_parts = []
        for label, value, color in slices:
            pct = 100.0 * value / total
            row = QLabel(f"●  {label}: {int(value)} ({pct:.0f}%)")
            row.setStyleSheet(f"color: {color};")
            row.setObjectName("PieLegendItem")
            self._legend.addWidget(row)
            summary_parts.append(f"{label} {int(value)} ({pct:.0f}%)")
        self.setAccessibleName("; ".join(summary_parts))
