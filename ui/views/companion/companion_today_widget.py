"""Compact companion widget for the Dashboard (§6.3).

Shows the global companion's current state and *today's* growth — not a timer
console. Full focus sessions are launched per-deck from the Cards page; this
widget surfaces the companion and offers a shortcut to go start one.
"""
from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from domain.companion.companion_service import DAILY_GROWTH_GOAL, CompanionService


class CompanionTodayWidget(QWidget):
    """Glyph + level + today's growth bar + 'start a session' shortcut."""

    def __init__(
        self,
        context: AppContext,
        on_start: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._on_start = on_start
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(12)

        self._glyph_lbl = QLabel("🌱")
        self._glyph_lbl.setObjectName("CompanionGlyph")
        self._glyph_lbl.setAccessibleName("")  # decorative
        top.addWidget(self._glyph_lbl)

        info = QVBoxLayout()
        info.setSpacing(2)
        self._name_lbl = QLabel("Companion")
        self._name_lbl.setObjectName("DashboardCardTitle")
        info.addWidget(self._name_lbl)
        self._growth_lbl = QLabel("")
        self._growth_lbl.setObjectName("SettingsHint")
        self._growth_lbl.setWordWrap(True)
        info.addWidget(self._growth_lbl)
        top.addLayout(info, 1)
        root.addLayout(top)

        # Today's growth bar.
        self._growth_bar = QProgressBar()
        self._growth_bar.setFixedHeight(10)
        self._growth_bar.setTextVisible(False)
        self._growth_bar.setAccessibleName("Today's growth progress")
        root.addWidget(self._growth_bar)

        # Shortcut to start a focus session (deck is chosen on the Cards page).
        self._start_btn = QPushButton("Start a focus session")
        self._start_btn.setAccessibleName("Go to Cards to start a focus session")
        self._start_btn.clicked.connect(self._handle_start)
        root.addWidget(self._start_btn, alignment=Qt.AlignmentFlag.AlignLeft)

    def _handle_start(self) -> None:
        if self._on_start is not None:
            self._on_start()

    def refresh(self) -> None:
        if self._context.db is None:
            self._growth_lbl.setText("No database available.")
            return
        with self._context.db.session() as session:
            svc = CompanionService(session)
            companion = svc.get_or_create(
                kind=self._context.settings.get("companion_kind") or "tree"
            )
            glyph = companion.glyph
            name = companion.name or (
                "Your tree" if companion.kind == "tree" else "Your companion"
            )
            level = companion.level
            growth = companion.growth_state.title()
            today = svc.growth_today(companion)

        self._glyph_lbl.setText(glyph)
        self._name_lbl.setText(f"{name}  ·  Level {level}")
        if today > 0:
            self._growth_lbl.setText(f"{growth} — grown +{today} XP today 🌱")
        else:
            self._growth_lbl.setText(
                f"{growth} — start a session to help it grow today"
            )
        self._growth_bar.setRange(0, DAILY_GROWTH_GOAL)
        self._growth_bar.setValue(min(today, DAILY_GROWTH_GOAL))

    def showEvent(self, event: QShowEvent) -> None:  # type: ignore[override]
        super().showEvent(event)
        self.refresh()
