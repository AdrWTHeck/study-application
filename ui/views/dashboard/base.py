"""Base class for dashboard widgets.

Every widget is a self-contained themed card with a title and a body it fills.
The framework instantiates widgets once and calls :meth:`refresh` when data
changes, so a widget that holds editable state (e.g. the sticky note) can simply
not reload on refresh.
"""
from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.context import AppContext
from app.navigation import Destination
from ui.utils.layouts import _resolve_tokens, clear_layout


class DashboardWidget(QWidget):
    """A themed dashboard card. Subclasses set ``key``/``title`` and fill ``body``."""

    key: str = ""
    title: str = ""
    #: Whether the widget should span both grid columns.
    wide: bool = False

    def __init__(
        self,
        context: AppContext,
        navigate: Callable[[Destination], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._navigate = navigate
        self.setObjectName("DashboardCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(False)
        self.setMinimumHeight(132)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        d = _resolve_tokens(context).density
        outer = QVBoxLayout(self)
        outer.setContentsMargins(d.space(2.5), d.space(2), d.space(2.5), d.space(2))
        outer.setSpacing(d.space(1))
        outer.setAlignment(Qt.AlignmentFlag.AlignTop)

        heading = QLabel(self.title)
        heading.setObjectName("DashboardCardTitle")
        heading.setAutoFillBackground(False)
        outer.addWidget(heading)
        # Kept so subclasses can restyle it (e.g. the hero turns it into an eyebrow).
        self._heading = heading

        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        self.body.setAlignment(Qt.AlignmentFlag.AlignTop)
        outer.addLayout(self.body)

        self.build()
        self.refresh()

    # -- overridable --------------------------------------------------------

    def build(self) -> None:
        """One-time construction of persistent child widgets (optional)."""

    def refresh(self) -> None:
        """Update the widget's data. Default: no-op."""

    # -- helpers ------------------------------------------------------------

    def _clear_body(self) -> None:
        clear_layout(self.body)

    def _label(self, text: str, object_name: str, *, word_wrap: bool = False) -> QLabel:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setAutoFillBackground(False)
        label.setWordWrap(word_wrap)
        return label

    def _go(self, dest: Destination) -> None:
        if self._navigate is not None:
            self._navigate(dest)
