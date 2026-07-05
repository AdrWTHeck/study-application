"""Deadline Forecast page — page-level orchestration only.

Layout:
  Header (title + Add button)
  ├── Left  — DeadlineForecastPanel (word, signal, load bars, calendar)
  └── Right — DeadlinePriorityPanel (grouped compact cards)

Stacked over the two-column view: VacationPanel (skip-day manager).
"""
from __future__ import annotations

from datetime import date
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from data.models.deadline import Deadline
from domain.deadlines.deadline_service import DeadlineService
from ui.views.deadlines.forecast_builder import build_forecast
from ui.views.deadlines.forecast_panel import DeadlineForecastPanel
from ui.views.deadlines.priority_panel import DeadlinePriorityPanel
from ui.views.deadlines.deadline_wizard import DeadlinePlanWizard
from ui.views.deadlines.vacation_panel import VacationPanel


class DeadlineView(QWidget):
    """Deadline Forecast page."""

    def __init__(
        self,
        context: AppContext,
        navigate: Callable | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._navigate = navigate

        self.setObjectName("Page")
        self.setAccessibleName("Deadlines")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._stack = QStackedWidget()
        self._stack.setObjectName("Page")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._stack)

        # ---- Page 0: two-column forecast layout ----
        self._list_page = QWidget()
        self._list_page.setObjectName("Page")
        self._list_page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        list_layout = QVBoxLayout(self._list_page)
        list_layout.setContentsMargins(32, 24, 32, 0)
        list_layout.setSpacing(8)

        title_row = QHBoxLayout()
        title_row.setSpacing(12)
        page_title = QLabel("Deadlines")
        page_title.setObjectName("PageTitle")
        title_row.addWidget(page_title)
        title_row.addStretch(1)
        add_btn = QPushButton("+ Add deadline")
        add_btn.setAccessibleName("Add new deadline")
        add_btn.clicked.connect(self._add_deadline)
        title_row.addWidget(add_btn)
        list_layout.addLayout(title_row)

        hint = QLabel("Plan today's workload from your active deadline targets.")
        hint.setObjectName("SettingsHint")
        hint.setWordWrap(True)
        list_layout.addWidget(hint)

        # Two-column split
        split = QWidget()
        split.setObjectName("Page")
        split.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        split_layout = QHBoxLayout(split)
        split_layout.setContentsMargins(0, 8, 0, 0)
        split_layout.setSpacing(0)

        # Left: forecast scroll
        self._forecast_scroll = QScrollArea()
        self._forecast_scroll.setWidgetResizable(True)
        self._forecast_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._forecast_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._forecast_scroll.setAutoFillBackground(False)
        self._forecast_scroll.viewport().setAutoFillBackground(False)
        self._forecast_panel = DeadlineForecastPanel()
        self._forecast_scroll.setWidget(self._forecast_panel)
        split_layout.addWidget(self._forecast_scroll, 3)

        # Divider
        divider = QWidget()
        divider.setObjectName("ForecastDivider")
        divider.setFixedWidth(1)
        divider.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        split_layout.addWidget(divider)

        # Right: priority scroll
        self._priority_scroll = QScrollArea()
        self._priority_scroll.setWidgetResizable(True)
        self._priority_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._priority_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._priority_scroll.setAutoFillBackground(False)
        self._priority_scroll.viewport().setAutoFillBackground(False)
        self._priority_panel = DeadlinePriorityPanel()
        self._priority_panel.set_callbacks(
            on_edit=self._edit_deadline,
            on_delete=self._delete_deadline,
            on_vacations=self._open_vacations,
        )
        self._priority_scroll.setWidget(self._priority_panel)
        split_layout.addWidget(self._priority_scroll, 2)

        list_layout.addWidget(split, 1)

        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("SettingsHint")
        self._status_lbl.setAccessibleName("Status")
        self._status_lbl.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        list_layout.addWidget(self._status_lbl)

        self._stack.addWidget(self._list_page)

        # ---- Page 1: vacation/skip-day panel ----
        self._vac_panel = VacationPanel()
        self._stack.addWidget(self._vac_panel)

        self._stack.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _announce(self, message: str) -> None:
        self._status_lbl.setText(message)
        self._status_lbl.setFocus()

    def showEvent(self, event: QShowEvent) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._refresh_list()

    def _refresh_list(self) -> None:
        if self._context.db is None:
            return
        with self._context.db.session() as session:
            svc = DeadlineService(session)
            upcoming = svc.all_summaries()
            past = svc.past_summaries()

        all_summaries = upcoming + past
        forecast = build_forecast(all_summaries, date.today(), self._resolve_word_pool())
        self._forecast_panel.refresh(forecast, self._context.palette)
        self._priority_panel.refresh(all_summaries, forecast.work_items)

    def _resolve_word_pool(self):
        """Resolve the word-of-day pool from user settings (or None to disable)."""
        from domain.deadlines.word_pool import resolve_pool

        settings = self._context.settings
        if not settings.get("word_of_day_enabled"):
            return []  # empty pool ⇒ no word shown
        custom = settings.get("word_of_day_pool") or []
        categories = settings.get("word_of_day_categories") or None
        return resolve_pool(custom, categories)

    # ------------------------------------------------------------------
    # CRUD actions
    # ------------------------------------------------------------------

    def _add_deadline(self) -> None:
        if self._context.db is None:
            return
        dialog = DeadlinePlanWizard(self._context, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        with self._context.db.session() as session:
            svc = DeadlineService(session)
            deadline = svc.create(
                dialog.name(), dialog.target_date(), dialog.focus(),
                phase=dialog.phase() or None,
                skip_weekends=dialog.skip_weekends(),
                daily_cap=dialog.daily_cap(),
            )
            svc.set_decks(deadline.id, dialog.selected_deck_ids())
        self._refresh_list()
        self._announce(f"Deadline '{dialog.name()}' created.")

    def _edit_deadline(self, deadline_id: int) -> None:
        if self._context.db is None:
            return
        with self._context.db.session() as session:
            deadline = session.get(Deadline, deadline_id)
            if deadline is None:
                return
            session.expunge(deadline)
        dialog = DeadlinePlanWizard(self._context, deadline=deadline, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        with self._context.db.session() as session:
            svc = DeadlineService(session)
            svc.update(
                deadline_id, name=dialog.name(), target_date=dialog.target_date(),
                focus=dialog.focus(), phase=dialog.phase(),
                skip_weekends=dialog.skip_weekends(), daily_cap=dialog.daily_cap(),
                clear_daily_cap=dialog.daily_cap() is None,
            )
            svc.set_decks(deadline_id, dialog.selected_deck_ids())
        self._refresh_list()
        self._announce(f"Deadline '{dialog.name()}' updated.")

    def _delete_deadline(self, deadline_id: int, deadline_name: str) -> None:
        if self._context.db is None:
            return
        reply = QMessageBox.question(
            self, "Delete deadline",
            f"Delete '{deadline_name}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        with self._context.db.session() as session:
            DeadlineService(session).delete(deadline_id)
        self._refresh_list()
        self._announce(f"Deadline '{deadline_name}' deleted.")

    def _open_vacations(self, deadline_id: int, deadline_name: str) -> None:
        if self._context.db is None:
            return
        self._vac_panel.load(
            self._context, deadline_id, deadline_name, self._back_to_list
        )
        self._stack.setCurrentIndex(1)

    def _back_to_list(self) -> None:
        self._stack.setCurrentIndex(0)
        self._refresh_list()
