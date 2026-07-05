"""A full-width, word-wrapping answer button for quizzes.

The whole option is the button (no separate "Choose" control), with a number
badge for quick keyboard selection. Long answers wrap instead of being clipped.
The inner labels are transparent to the mouse so clicks always reach the button,
and an accessible name carries the full "Answer N: …" text for screen readers.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget


class AnswerOptionButton(QPushButton):
    def __init__(self, number: int, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.option_text = text
        self.setObjectName("AnswerOption")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(f"Answer {number}: {text}")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        badge = QLabel(str(number))
        badge.setObjectName("AnswerNumber")
        badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)

        label = QLabel(text or "")
        label.setObjectName("AnswerText")
        label.setWordWrap(True)
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        layout.addWidget(label, 1)
