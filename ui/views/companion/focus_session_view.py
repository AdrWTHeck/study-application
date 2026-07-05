"""Per-deck focus session page (§6.3).

A full in-app, theme-aligned page launched from a card deck. Runs:
  1. Before-confidence diagnostic (scoped to the deck's cards)
  2. Pomodoro focus block(s) with the companion alongside
  3. After-confidence diagnostic
  4. Session summary + XP award (flows to the global companion + today's growth)

Lives inside the Cards stack like the Review page, so it inherits the app
theme and keyboard navigation. Emits ``finished`` to return to the deck list.
"""
from __future__ import annotations

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from app.events import AppEvent
from data.models.companion import XP_PER_LEVEL
from domain.companion.companion_service import CompanionService
from domain.companion.encouragement_service import EncouragementService
from domain.study.pomodoro_service import PomodoroService, TimerState


class FocusSessionView(QWidget):
    """Themed Pomodoro + diagnostic session scoped to a single deck."""

    finished = pyqtSignal()

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setObjectName("Page")
        self.setAccessibleName("Focus session")

        self._deck_id: int | None = None
        self._deck_title = ""
        self._encouragement = EncouragementService()
        self._pomodoro = PomodoroService()
        self._before_avg: float | None = None
        self._session_key: str | None = None

        self._qtimer = QTimer(self)
        self._qtimer.setInterval(1000)
        self._qtimer.timeout.connect(self._tick)

        self._build_ui()

    # -- construction --------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 24, 40, 24)
        root.setSpacing(16)

        # ── Header row ──────────────────────────────────────────────────────
        header = QHBoxLayout()
        back = QPushButton("← Decks")
        back.setAccessibleName("Back to decks")
        back.clicked.connect(self._on_back)
        header.addWidget(back)
        header.addSpacing(8)
        self._title = QLabel("Focus session")
        self._title.setObjectName("TopTitle")
        self._title.setWordWrap(True)
        header.addWidget(self._title, 1)
        root.addLayout(header)

        # ── Companion card ──────────────────────────────────────────────────
        companion_card = QWidget()
        companion_card.setObjectName("FocusPanel")
        companion_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        companion_card_layout = QVBoxLayout(companion_card)
        companion_card_layout.setContentsMargins(16, 14, 16, 14)
        companion_card_layout.setSpacing(8)

        companion_row = QHBoxLayout()
        companion_row.setSpacing(14)
        self._glyph_lbl = QLabel("🌱")
        self._glyph_lbl.setStyleSheet("font-size: 40px;")
        self._glyph_lbl.setAccessibleName("")  # decorative
        companion_row.addWidget(self._glyph_lbl)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        self._companion_lbl = QLabel("Companion")
        self._companion_lbl.setObjectName("DashboardCardTitle")
        info_col.addWidget(self._companion_lbl)
        self._growth_lbl = QLabel("")
        self._growth_lbl.setObjectName("SettingsHint")
        info_col.addWidget(self._growth_lbl)
        companion_row.addLayout(info_col, 1)
        companion_card_layout.addLayout(companion_row)

        self._xp_bar = QProgressBar()
        self._xp_bar.setFixedHeight(8)
        self._xp_bar.setTextVisible(False)
        self._xp_bar.setAccessibleName("XP towards next level")
        companion_card_layout.addWidget(self._xp_bar)
        root.addWidget(companion_card)

        # ── Timer card ──────────────────────────────────────────────────────
        timer_card = QWidget()
        timer_card.setObjectName("FocusPanel")
        timer_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        timer_layout = QVBoxLayout(timer_card)
        timer_layout.setContentsMargins(24, 32, 24, 32)
        timer_layout.setSpacing(10)
        timer_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._timer_lbl = QLabel("25:00")
        self._timer_lbl.setObjectName("FocusTimerDisplay")
        self._timer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timer_lbl.setAccessibleName("Timer countdown")
        timer_layout.addWidget(self._timer_lbl)

        self._phase_lbl = QLabel("Ready to start")
        self._phase_lbl.setObjectName("PageSubtitle")
        self._phase_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        timer_layout.addWidget(self._phase_lbl)

        self._enc_lbl = QLabel("")
        self._enc_lbl.setObjectName("SettingsHint")
        self._enc_lbl.setWordWrap(True)
        self._enc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        timer_layout.addWidget(self._enc_lbl)
        root.addWidget(timer_card, 1)

        # ── Controls ────────────────────────────────────────────────────────
        controls = QHBoxLayout()
        controls.setSpacing(10)
        controls.addStretch(1)
        self._start_btn = QPushButton("Start session")
        self._start_btn.setAccessibleName("Start focus session")
        self._start_btn.clicked.connect(self._on_start)
        controls.addWidget(self._start_btn)

        self._pause_btn = QPushButton("Pause")
        self._pause_btn.setAccessibleName("Pause or resume")
        self._pause_btn.setEnabled(False)
        self._pause_btn.clicked.connect(self._on_pause)
        controls.addWidget(self._pause_btn)

        self._reset_btn = QPushButton("Reset")
        self._reset_btn.setAccessibleName("Reset timer")
        self._reset_btn.setEnabled(False)
        self._reset_btn.clicked.connect(self._on_reset)
        controls.addWidget(self._reset_btn)
        controls.addStretch(1)
        root.addLayout(controls)

    # -- public API ----------------------------------------------------------

    def start(self, deck_id: int, deck_title: str = "") -> None:
        """Open the session page for a deck (timer not yet running)."""
        self._deck_id = deck_id
        self._deck_title = deck_title
        self._title.setText(f"Focus session — {deck_title}" if deck_title else "Focus session")
        self._pomodoro = PomodoroService(
            focus_minutes=self._context.settings.get("pomodoro_focus_minutes") or 25,
            break_minutes=self._context.settings.get("pomodoro_break_minutes") or 5,
            long_break_minutes=self._context.settings.get("pomodoro_long_break_minutes") or 15,
            long_break_after=self._context.settings.get("pomodoro_long_break_after") or 4,
        )
        self._qtimer.stop()
        self._before_avg = None
        self._session_key = None
        self._enc_lbl.setText("")
        self._update_controls()
        self._update_timer_display()
        self._refresh_companion()

    # -- companion -----------------------------------------------------------

    def _refresh_companion(self) -> None:
        if self._context.db is None:
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
            xp_now = companion.xp_in_current_level
            xp_max = companion.level * XP_PER_LEVEL

        self._glyph_lbl.setText(glyph)
        self._companion_lbl.setText(f"{name}  ·  Level {level}  ·  {growth}")
        self._growth_lbl.setText(f"Grown today: +{today} XP")
        self._xp_bar.setRange(0, xp_max)
        self._xp_bar.setValue(xp_now)

    # -- timer controls ------------------------------------------------------

    def _on_start(self) -> None:
        if self._pomodoro.state is not TimerState.IDLE:
            return
        if self._context.db is not None:
            from ui.views.companion.diagnostic_dialog import DiagnosticDialog

            dlg = DiagnosticDialog(
                self._context, phase="before", deck_id=self._deck_id, parent=self
            )
            if dlg.exec():
                self._before_avg = dlg.avg_confidence()
                self._session_key = dlg.session_key
                self._save_diagnostic_items(dlg.collect_items())

        self._pomodoro.start_focus()
        self._qtimer.start()
        self._update_controls()
        self._update_timer_display()
        self._enc_lbl.setText(self._encouragement.pick("focus_start"))

    def _on_pause(self) -> None:
        if self._pomodoro.state is TimerState.PAUSED:
            self._pomodoro.resume()
            self._qtimer.start()
        else:
            self._pomodoro.pause()
            self._qtimer.stop()
        self._update_controls()
        self._update_timer_display()

    def _on_reset(self) -> None:
        self._qtimer.stop()
        self._pomodoro.reset()
        self._update_controls()
        self._update_timer_display()
        self._enc_lbl.setText("")

    def _on_back(self) -> None:
        self._qtimer.stop()
        self._pomodoro.reset()
        self.finished.emit()

    # -- tick ----------------------------------------------------------------

    def _tick(self) -> None:
        events = self._pomodoro.tick()
        self._update_timer_display()
        for event in events:
            if event.kind == "focus_done":
                self._award_focus_block()
                self._enc_lbl.setText(self._encouragement.pick("gentle_break"))
                if not self._qtimer.isActive():
                    self._qtimer.start()
            elif event.kind in ("break_done", "long_break_done"):
                self._qtimer.stop()
                self._finish_session()
        self._update_controls()

    # -- post-session --------------------------------------------------------

    def _award_focus_block(self) -> None:
        if self._context.db is None:
            return
        with self._context.db.session() as session:
            svc = CompanionService(session)
            companion = svc.get_or_create()
            svc.record_focus_block(companion)
        self._refresh_companion()
        self._context.events.publish(AppEvent.COMPANION_UPDATED)

    def _finish_session(self) -> None:
        after_avg: float | None = None
        if self._context.db is not None:
            from ui.views.companion.diagnostic_dialog import DiagnosticDialog

            dlg = DiagnosticDialog(
                self._context,
                phase="after",
                session_key=self._session_key,
                deck_id=self._deck_id,
                parent=self,
            )
            if dlg.exec():
                after_avg = dlg.avg_confidence()
                self._save_diagnostic_items(dlg.collect_items())

            improved = (
                after_avg is not None
                and self._before_avg is not None
                and after_avg > self._before_avg
            )
            with self._context.db.session() as session:
                svc = CompanionService(session)
                companion = svc.get_or_create()
                xp_before = companion.xp + (companion.level - 1) * XP_PER_LEVEL
                svc.record_diagnostic_complete(companion, improved=improved)
                if svc.is_returning_after_gap(companion):
                    svc.record_return_after_gap(companion)
                svc.record_fed(companion)
                xp_after = companion.xp + (companion.level - 1) * XP_PER_LEVEL
                xp_gained = max(0, xp_after - xp_before)

                if improved:
                    enc_category = "improved_confidence"
                elif after_avg is not None and after_avg < 1.5:
                    enc_category = "low_score_support"
                else:
                    enc_category = "session_complete"
                encouragement = self._encouragement.pick(enc_category)

                from ui.views.companion.session_summary_dialog import SessionSummaryDialog

                SessionSummaryDialog(
                    companion=companion,
                    xp_gained=xp_gained,
                    encouragement=encouragement,
                    before_avg=self._before_avg,
                    after_avg=after_avg,
                    parent=self,
                ).exec()

        self._pomodoro.reset()
        self._update_controls()
        self._update_timer_display()
        self._refresh_companion()
        self._phase_lbl.setText("Session complete — great work!")
        self._enc_lbl.setText(self._encouragement.pick("session_complete"))
        self._context.events.publish(AppEvent.COMPANION_UPDATED)
        self._context.events.publish(AppEvent.STUDY_SESSION_COMPLETED)

    def _save_diagnostic_items(self, items: list) -> None:
        if self._context.db is None or not items:
            return
        with self._context.db.session() as session:
            for item in items:
                session.add(item)

    # -- display -------------------------------------------------------------

    def _update_timer_display(self) -> None:
        state = self._pomodoro.state
        if state is TimerState.IDLE:
            focus_m = self._pomodoro.focus_minutes
            self._timer_lbl.setText(f"{focus_m:02d}:00")
            self._phase_lbl.setText("Ready to start")
        elif state is TimerState.PAUSED:
            self._timer_lbl.setText(self._pomodoro.display_time)
            self._phase_lbl.setText("Paused")
        else:
            self._timer_lbl.setText(self._pomodoro.display_time)
            phase_text = {
                TimerState.FOCUS: "Focus",
                TimerState.BREAK: "Short break",
                TimerState.LONG_BREAK: "Long break",
            }.get(state, "")
            if state is TimerState.FOCUS:
                self._phase_lbl.setText(
                    f"{phase_text}  —  session {self._pomodoro.completed_sessions + 1}"
                )
            else:
                self._phase_lbl.setText(phase_text)

    def _update_controls(self) -> None:
        state = self._pomodoro.state
        idle = state is TimerState.IDLE
        running = self._pomodoro.is_running
        paused = state is TimerState.PAUSED
        self._start_btn.setEnabled(idle)
        self._pause_btn.setEnabled(running or paused)
        self._reset_btn.setEnabled(not idle)
        self._pause_btn.setText("Resume" if paused else "Pause")
