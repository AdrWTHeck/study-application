"""A single-value circular progress ring with centered value text.

Distinct from :class:`ui.components.pie_chart.PieChart` (a categorical donut
with a legend): the ring shows one percentage as an arc with rounded caps and
the value in the middle, per the clay redesign's test-results snapshot.

The value never relies on colour alone (VIS-03): the centre labels carry the
percentage and detail text, and the widget exposes both via its accessible
name.
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ProgressRing(QWidget):
    def __init__(self, diameter: int = 200, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._diameter = diameter
        self._pct = 0.0
        self._arc_color = QColor("#888888")
        self._track_color = QColor("#444444")
        self.setFixedSize(diameter, diameter)

        # Centre labels are real QLabels so the QSS typography rules
        # (#RingValue mono, #RingCaption) style them like everything else.
        layout = QVBoxLayout(self)
        pad = max(12, diameter // 6)
        layout.setContentsMargins(pad, pad, pad, pad)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value_label = QLabel("—")
        self._value_label.setObjectName("RingValue")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value_label.setWordWrap(False)
        self._caption_label = QLabel("")
        self._caption_label.setObjectName("RingCaption")
        self._caption_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._caption_label.setWordWrap(True)
        layout.addWidget(self._value_label)
        layout.addWidget(self._caption_label)

    def set_value(
        self,
        pct: float,
        detail: str,
        color: QColor,
        track_color: QColor | None = None,
    ) -> None:
        """Show *pct* (0–100) with *detail* caption; arc drawn in *color*."""
        self._pct = max(0.0, min(float(pct), 100.0))
        self._arc_color = QColor(color)
        if track_color is not None:
            track = QColor(track_color)
        else:
            track = QColor(self._arc_color)
            track.setAlpha(50)
        self._track_color = track
        self._value_label.setText(f"{self._pct:.0f}%")
        self._caption_label.setText(detail)
        self.setAccessibleName(f"Score {self._pct:.0f} percent, {detail}")
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        pen_width = max(8, self._diameter // 18)
        inset = pen_width / 2 + 2
        rect = QRectF(inset, inset, self.width() - 2 * inset, self.height() - 2 * inset)
        if rect.width() <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        track_pen = QPen(self._track_color, pen_width)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(rect, 0, 360 * 16)

        if self._pct > 0:
            arc_pen = QPen(self._arc_color, pen_width)
            arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(arc_pen)
            span = -int(round(360 * 16 * self._pct / 100.0))
            painter.drawArc(rect, 90 * 16, span)
        painter.end()
