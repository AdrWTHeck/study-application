"""ElapsedTimer — a QLabel that counts seconds since start()."""
from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QLabel


class ElapsedTimer(QLabel):
    """Displays elapsed time as M:SS.  Call start() to reset and begin ticking."""

    def __init__(self, parent=None) -> None:
        super().__init__("0:00", parent)
        self._seconds = 0
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._seconds = 0
        self.setText("0:00")
        self._timer.start()

    def stop(self) -> float:
        """Stop ticking and return elapsed seconds."""
        self._timer.stop()
        return float(self._seconds)

    def elapsed(self) -> float:
        return float(self._seconds)

    def _tick(self) -> None:
        self._seconds += 1
        m, s = divmod(self._seconds, 60)
        self.setText(f"{m}:{s:02d}")
