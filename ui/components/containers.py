"""Reusable container widgets: themed scroll areas and card containers."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


def themed_scroll_area(
    *,
    object_name: str = "Page",
    margins: tuple[int, int, int, int] = (0, 0, 0, 0),
    spacing: int = 8,
    align_top: bool = True,
) -> tuple[QScrollArea, QWidget, QVBoxLayout]:
    """Create a standard scroll area with a themed body widget and layout.

    Returns (scroll, body_widget, body_layout) so callers can add widgets to
    body_layout without repeating the boilerplate.
    """
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setAutoFillBackground(False)
    scroll.viewport().setAutoFillBackground(False)

    body = QWidget()
    body.setObjectName(object_name)
    body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    layout = QVBoxLayout(body)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    if align_top:
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    scroll.setWidget(body)
    return scroll, body, layout


class ThemedCard(QWidget):
    """Rounded, themed card container.

    The *object_name* controls which QSS rule applies (e.g. 'DeckRow',
    'DashboardCard', 'DeadlinePriorityCard'). WA_StyledBackground is set
    automatically so border-radius and background render correctly.
    """

    def __init__(
        self,
        object_name: str = "Card",
        margins: tuple[int, int, int, int] = (16, 12, 16, 12),
        spacing: int = 8,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self._inner = QVBoxLayout(self)
        self._inner.setContentsMargins(*margins)
        self._inner.setSpacing(spacing)

    @property
    def inner_layout(self) -> QVBoxLayout:
        return self._inner

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self._inner.addWidget(widget, stretch)

    def add_layout(self, layout) -> None:
        self._inner.addLayout(layout)

    def add_spacing(self, px: int) -> None:
        self._inner.addSpacing(px)
