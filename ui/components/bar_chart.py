"""A simple horizontal bar chart built from labeled QProgressBars.

Accessible by construction: each bar carries its label + value as text and an
accessible name, so it never relies on color alone (VIS-03).
"""
from __future__ import annotations

from PyQt6.QtWidgets import QProgressBar, QVBoxLayout, QWidget


class BarChart(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)

    def set_data(self, rows: list[tuple[str, float]]) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for label, value in rows:
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(int(round(value)))
            bar.setFormat(f"{label} — {value:.0f}%")
            bar.setTextVisible(True)
            bar.setAccessibleName(f"{label}: {value:.0f} percent")
            self._layout.addWidget(bar)
