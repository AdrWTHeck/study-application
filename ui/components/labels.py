"""Reusable label components."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QSizePolicy, QWidget


class ElidedLabel(QLabel):
    """QLabel that elides overflowing text and shows the full text as a tooltip.

    Uses Ignored horizontal size policy so the label can shrink without forcing
    its container to expand — important for flex-width card layouts.
    """

    def __init__(
        self,
        text: str = "",
        parent: QWidget | None = None,
        mode: Qt.TextElideMode = Qt.TextElideMode.ElideRight,
    ) -> None:
        super().__init__(parent)
        self._full_text = text
        self._mode = mode
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(False)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setToolTip(text)
        self._update_elided_text()

    def set_full_text(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        self._update_elided_text()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self) -> None:
        text = self.fontMetrics().elidedText(
            self._full_text,
            self._mode,
            self.contentsRect().width(),
        )
        super().setText(text)
