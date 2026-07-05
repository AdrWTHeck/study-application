"""The Dashboard landing page: a calm, accessibility-first overview.

Composed of independent widgets (see ``ui/views/dashboard/``) laid out in a
two-column grid from a saved, per-mode board. Widgets are created once and
refreshed on data changes (via the event bus / show), so editable widgets like
the sticky note keep their state.
"""
from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QGridLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from app.events import AppEvent
from app.navigation import Destination
from ui.utils.layouts import _resolve_tokens, apply_page_margins, clear_layout
from ui.views.dashboard.base import DashboardWidget
from ui.views.dashboard.registry import WIDGETS, resolve_board


class DashboardView(QWidget):
    def __init__(
        self,
        context: AppContext,
        navigate: Callable[[Destination], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._navigate = navigate
        self.setObjectName("Page")
        self.setAccessibleName("Dashboard")

        self._widgets: dict[str, DashboardWidget] = {}
        self._current_board: list[str] = []

        scroll = QScrollArea(self)
        scroll.setObjectName("Page")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setAutoFillBackground(False)
        _vp = scroll.viewport()
        if _vp is not None:
            _vp.setObjectName("Page")
            _vp.setAutoFillBackground(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._body = QWidget()
        self._body.setObjectName("Page")
        self._body.setAutoFillBackground(False)
        self._body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        gap = _resolve_tokens(context).layout.gap
        self._layout = QVBoxLayout(self._body)
        apply_page_margins(self._layout, context)
        self._layout.setSpacing(gap)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._body)

        self._layout.addLayout(self._build_greeting_header())

        self._grid = QGridLayout()
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(gap)
        self._grid.setVerticalSpacing(gap)
        self._grid.setColumnStretch(0, 1)
        self._grid.setColumnStretch(1, 1)
        self._layout.addLayout(self._grid)
        self._layout.addStretch(1)

        # Stay current without polling: refresh on relevant domain events, but
        # only when visible (showEvent covers the hidden case).
        self._unsubscribers = [
            context.events.subscribe(event, self._on_bus_event)
            for event in (
                AppEvent.CARD_REVIEWED,
                AppEvent.QUIZ_COMPLETED,
                AppEvent.COMPANION_UPDATED,
                AppEvent.STUDY_SESSION_COMPLETED,
                AppEvent.DEADLINE_CHANGED,
                AppEvent.CARD_CREATED,
            )
        ]

        self._rebuild_board()

    # -- greeting header ------------------------------------------------------

    def _build_greeting_header(self):
        from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout

        header = QHBoxLayout()
        header.setSpacing(16)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self._greeting = QLabel(self._greeting_text())
        self._greeting.setObjectName("DashGreeting")
        self._greeting_sub = QLabel("")
        self._greeting_sub.setObjectName("DashGreetingSub")
        text_col.addWidget(self._greeting)
        text_col.addWidget(self._greeting_sub)
        header.addLayout(text_col, 1)

        add_note = QPushButton("Add note")
        add_note.setObjectName("GhostButton")
        add_note.setAccessibleName("Add a new note")
        add_note.clicked.connect(self._add_note)
        study_now = QPushButton("Study now")
        study_now.setObjectName("PrimaryButton")
        study_now.setAccessibleName("Study now")
        study_now.clicked.connect(lambda: self._go(Destination.CARDS))
        header.addWidget(add_note, 0, Qt.AlignmentFlag.AlignTop)
        header.addWidget(study_now, 0, Qt.AlignmentFlag.AlignTop)
        return header

    @staticmethod
    def _greeting_text() -> str:
        from datetime import datetime

        hour = datetime.now().hour
        if hour < 12:
            return "Good morning"
        if hour < 18:
            return "Good afternoon"
        return "Good evening"

    def _refresh_greeting(self) -> None:
        from datetime import datetime

        from domain.dashboard.stats_service import StatsService

        self._greeting.setText(self._greeting_text())
        date_str = datetime.now().strftime("%A, %B %d")
        with self._context.db.session() as s:
            stats = StatsService(s)
            waiting = stats.due_count() + stats.new_count()
        if waiting:
            sub = f"{date_str}  ·  {waiting} card{'s' if waiting != 1 else ''} waiting"
        else:
            sub = f"{date_str}  ·  all caught up"
        self._greeting_sub.setText(sub)
        self._greeting_sub.setAccessibleName(sub)

    def _add_note(self) -> None:
        from ui.views.note_form import AddNoteDialog

        AddNoteDialog(self._context, parent=self).exec()

    # -- board composition --------------------------------------------------

    def _resolve_board(self) -> list[str]:
        board = resolve_board(self._context.settings)
        # The companion widget only appears when the companion is enabled.
        if not self._context.settings.get("companion_enabled"):
            board = [k for k in board if k != "companion"]
        return board

    def _rebuild_board(self) -> None:
        """(Re)create the widget grid. Called when the board layout changes."""
        clear_layout(self._grid)
        self._widgets = {}
        board = self._resolve_board()
        self._current_board = list(board)

        row = col = 0
        for key in board:
            cls = WIDGETS.get(key)
            if cls is None:
                continue
            widget = cls(self._context, navigate=self._navigate)
            self._widgets[key] = widget
            if getattr(cls, "wide", False):
                if col != 0:                 # start a fresh row for a wide widget
                    row += 1
                    col = 0
                self._grid.addWidget(widget, row, 0, 1, 2)
                row += 1
                col = 0
            else:
                self._grid.addWidget(widget, row, col)
                col += 1
                if col > 1:
                    col = 0
                    row += 1

    def refresh(self) -> None:
        if self._context.db is None:
            return
        self._refresh_greeting()
        # If the saved board changed (mode switch, customization), rebuild it.
        if self._resolve_board() != self._current_board:
            self._rebuild_board()
            return
        for widget in self._widgets.values():
            widget.refresh()

    def _on_bus_event(self, _payload: object = None) -> None:
        if self.isVisible():
            self.refresh()

    def _go(self, dest: Destination) -> None:
        if self._navigate is not None:
            self._navigate(dest)

    def showEvent(self, event: QShowEvent) -> None:  # type: ignore[override]
        super().showEvent(event)
        self.refresh()
