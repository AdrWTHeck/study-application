"""Concrete dashboard widgets. Each reads its own data and renders a themed card.

Charts always carry a text alternative (VIS/accessibility): a screen-reader user
gets the same information as the bar graph conveys visually.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from app.navigation import Destination
from domain.dashboard.stats_service import StatsService
from domain.deadlines.deadline_service import DeadlineService, DeadlineSummary
from domain.srs.srs_base import LEARNING, NEW, RELEARNING, REVIEW
from ui.views.companion.companion_today_widget import CompanionTodayWidget
from ui.views.dashboard.base import DashboardWidget

_STATE_LABELS = {NEW: "New", LEARNING: "Learning", REVIEW: "Review", RELEARNING: "Relearning"}


class HeroWidget(DashboardWidget):
    """The clay-redesign hero: today's queue at a glance plus the two main actions.

    Both buttons deep-link to the Cards page — there is no global quick-pass
    entry point; the learner picks the deck there (one decision at a time).
    """

    key = "hero"
    title = "Today's queue"
    wide = True

    def build(self) -> None:
        self.setObjectName("HeroCard")
        self._heading.setObjectName("Eyebrow")
        self._heading.setText("TODAY'S QUEUE")

        stats_row = QHBoxLayout()
        stats_row.setSpacing(24)
        self._due_value, due_block = self._stat_block("Due", accent=False)
        self._new_value, new_block = self._stat_block("New", accent=True)
        self._streak_value, streak_block = self._stat_block("Day streak", accent=False)
        stats_row.addLayout(due_block)
        stats_row.addWidget(self._divider())
        stats_row.addLayout(new_block)
        stats_row.addWidget(self._divider())
        stats_row.addLayout(streak_block)
        stats_row.addStretch(1)
        self.body.addLayout(stats_row)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        start = QPushButton("Start studying")
        start.setObjectName("PrimaryButton")
        start.setAccessibleName("Start studying")
        start.clicked.connect(lambda: self._go(Destination.CARDS))
        quick = QPushButton("Quick pass")
        quick.setObjectName("QuickPassButton")
        quick.setAccessibleName("Quick pass: fast yes/no run through due cards")
        quick.clicked.connect(lambda: self._go(Destination.CARDS))
        buttons.addWidget(start)
        buttons.addWidget(quick)
        buttons.addStretch(1)
        self.body.addLayout(buttons)

    def _stat_block(self, caption: str, *, accent: bool) -> tuple[QLabel, QVBoxLayout]:
        value = QLabel("0")
        value.setObjectName("HeroStatValue")
        if accent:
            value.setProperty("accent", "true")
        cap = QLabel(caption)
        cap.setObjectName("HeroStatCaption")
        block = QVBoxLayout()
        block.setSpacing(0)
        block.addWidget(value)
        block.addWidget(cap)
        return value, block

    def _divider(self) -> QFrame:
        line = QFrame()
        line.setObjectName("HeroDivider")
        line.setFixedWidth(1)
        return line

    def refresh(self) -> None:
        if self._context.db is None:
            return
        with self._context.db.session() as s:
            stats = StatsService(s)
            due, new, streak = stats.due_count(), stats.new_count(), stats.streak()
        self._due_value.setText(str(due))
        self._due_value.setAccessibleName(f"{due} cards due")
        self._new_value.setText(str(new))
        self._new_value.setAccessibleName(f"{new} new cards")
        self._streak_value.setText(str(streak))
        self._streak_value.setAccessibleName(f"{streak} day streak")


class StudyWidget(DashboardWidget):
    key = "study"
    title = "Study"

    def refresh(self) -> None:
        self._clear_body()
        if self._context.db is None:
            return
        with self._context.db.session() as s:
            stats = StatsService(s)
            due, new = stats.due_count(), stats.new_count()
        self.body.addWidget(self._label(
            f"{due} card{'s' if due != 1 else ''} due  ·  {new} new",
            "FieldLabel", word_wrap=True,
        ))
        btn = QPushButton("Start studying")
        btn.setAccessibleName("Start studying")
        btn.clicked.connect(lambda: self._go(Destination.CARDS))
        self.body.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)


class RetentionWidget(DashboardWidget):
    key = "retention"
    title = "Retention"

    def refresh(self) -> None:
        self._clear_body()
        if self._context.db is None:
            return
        with self._context.db.session() as s:
            rate, sample = StatsService(s).retention_rate()
        if rate is None:
            self.body.addWidget(self._label(
                "No card reviews yet — your recall rate will appear here.",
                "SettingsHint", word_wrap=True,
            ))
            return
        value = self._label(f"{rate:.0f}%", "StatCardValue")
        value.setAccessibleName(f"Retention {rate:.0f} percent")
        self.body.addWidget(value)
        self.body.addWidget(self._label(
            f"recall over your last {sample} review{'s' if sample != 1 else ''}",
            "StatCardCaption", word_wrap=True,
        ))


class CardStatesWidget(DashboardWidget):
    key = "card_states"
    title = "Cards by state"

    def build(self) -> None:
        # One thin labelled bar per state (clay redesign) — the label + count
        # text carries the information, colour is reinforcement only (VIS-03).
        self._bars: dict[str, QProgressBar] = {}
        self._counts: dict[str, QLabel] = {}
        for state in (NEW, LEARNING, REVIEW, RELEARNING):
            row = QHBoxLayout()
            row.setSpacing(8)
            name = self._label(_STATE_LABELS[state], "SettingsHint")
            name.setMinimumWidth(80)
            bar = QProgressBar()
            bar.setObjectName("StateProgress")
            bar.setProperty("state", state)
            bar.setTextVisible(False)
            count = self._label("0", "MonoScore")
            self._bars[state] = bar
            self._counts[state] = count
            row.addWidget(name)
            row.addWidget(bar, 1)
            row.addWidget(count)
            self.body.addLayout(row)
        self._summary = self._label("", "SettingsHint", word_wrap=True)
        self.body.addWidget(self._summary)

    def refresh(self) -> None:
        if self._context.db is None:
            return
        with self._context.db.session() as s:
            dist = StatsService(s).card_state_distribution()
        total = sum(dist.values())
        for state, bar in self._bars.items():
            count = dist.get(state, 0)
            bar.setMaximum(max(total, 1))
            bar.setValue(count)
            bar.setAccessibleName(f"{count} {_STATE_LABELS[state].lower()} cards")
            self._counts[state].setText(str(count))
        # Text alternative for screen readers / non-visual access.
        parts = ", ".join(f"{dist.get(k, 0)} {_STATE_LABELS[k].lower()}" for k in (NEW, LEARNING, REVIEW, RELEARNING))
        self._summary.setText(f"{total} cards total: {parts}.")
        self._summary.setAccessibleName(f"{total} cards total: {parts}")


class RecentTestsWidget(DashboardWidget):
    key = "recent_tests"
    title = "Recent tests"

    def refresh(self) -> None:
        self._clear_body()
        if self._context.db is None:
            return
        with self._context.db.session() as s:
            tests = StatsService(s).test_summaries()
        if not tests:
            self.body.addWidget(self._label("No test attempts yet.", "SettingsHint", word_wrap=True))
            return
        for t in tests[:4]:
            row = QHBoxLayout()
            row.setSpacing(8)
            name = self._label(
                f"{t.deck} — {t.attempts} attempt{'s' if t.attempts != 1 else ''}",
                "SettingsHint", word_wrap=True,
            )
            score = self._label(f"{t.best:.0f}%", "MonoScore")
            score.setAccessibleName(f"{t.deck} best score {t.best:.0f} percent")
            row.addWidget(name, 1)
            row.addWidget(score, 0, Qt.AlignmentFlag.AlignRight)
            self.body.addLayout(row)


class DeadlineWidget(DashboardWidget):
    key = "deadline"
    title = "Upcoming deadline"

    def refresh(self) -> None:
        self._clear_body()
        if self._context.db is None:
            return
        with self._context.db.session() as s:
            soonest: DeadlineSummary | None = DeadlineService(s).soonest()
        if soonest is None:
            self.body.addWidget(self._label("No upcoming deadlines.", "SettingsHint", word_wrap=True))
        else:
            self._fill(soonest)
        btn = QPushButton("Manage deadlines")
        btn.setAccessibleName("Go to Deadlines page")
        btn.clicked.connect(lambda: self._go(Destination.DEADLINES))
        self.body.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)

    def _fill(self, soonest: DeadlineSummary) -> None:
        if not soonest.is_past and soonest.days_left <= 7:
            urg = ("⚠ Due today" if soonest.days_left == 0
                   else f"⚠ Urgent — {soonest.days_left} day{'s' if soonest.days_left != 1 else ''} remaining")
            lbl = self._label(urg, "UrgentChip", word_wrap=True)
            lbl.setAccessibleName(f"Urgent: deadline within {soonest.days_left} days")
            self.body.addWidget(lbl)
        d = soonest.target_date
        date_str = f"{d.strftime('%a')}, {d.strftime('%b')} {d.day}, {d.year}"
        if soonest.is_past:
            days_text = "Past"
        elif soonest.days_left == 0:
            days_text = "Due today"
        else:
            days_text = f"{soonest.days_left} day{'s' if soonest.days_left != 1 else ''} left"
        self.body.addWidget(self._label(
            f"{soonest.name}  —  {date_str}  ({days_text})", "FieldLabel", word_wrap=True,
        ))
        if soonest.total_remaining > 0 and soonest.daily_target is not None:
            n = soonest.daily_target
            self.body.addWidget(self._label(
                f"{n} card{'s' if n != 1 else ''}/day to stay on track  ·  "
                f"{soonest.total_remaining} remaining", "SettingsHint", word_wrap=True,
            ))


class StreakWidget(DashboardWidget):
    key = "streak"
    title = "Study streak"

    def refresh(self) -> None:
        self._clear_body()
        if self._context.db is None:
            return
        with self._context.db.session() as s:
            streak = StatsService(s).streak()
        if not streak:
            self.body.addWidget(self._label(
                "No active streak — study today to start one!", "SettingsHint", word_wrap=True,
            ))
            return
        value = self._label(f"🔥 {streak}", "StatCardValue")
        value.setAccessibleName(f"{streak} day streak")
        self.body.addWidget(value)
        self.body.addWidget(self._label(
            f"day{'s' if streak != 1 else ''} in a row", "StatCardCaption",
        ))


class CompanionWidget(DashboardWidget):
    key = "companion"
    title = "Study companion"

    def build(self) -> None:
        self._inner = CompanionTodayWidget(
            self._context, on_start=lambda: self._go(Destination.CARDS)
        )
        self.body.addWidget(self._inner)

    def refresh(self) -> None:
        self._inner.refresh()


class StickyNoteWidget(DashboardWidget):
    key = "sticky_note"
    title = "Sticky note"

    def build(self) -> None:
        self._editor = QPlainTextEdit()
        self._editor.setObjectName("StickyNote")
        self._editor.setAccessibleName("Sticky note")
        self._editor.setPlaceholderText("Jot a quick reminder…")
        self._editor.setPlainText(self._context.settings.get("dashboard_sticky_note") or "")
        self._editor.setMinimumHeight(80)
        self.body.addWidget(self._editor)
        # Debounced save so we aren't writing settings on every keystroke.
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(600)
        self._save_timer.timeout.connect(self._save)
        self._editor.textChanged.connect(self._save_timer.start)

    def _save(self) -> None:
        self._context.settings.set("dashboard_sticky_note", self._editor.toPlainText())

    def refresh(self) -> None:
        # No-op: holds editable state; reloading would clobber in-progress edits.
        pass


class QuickActionsWidget(DashboardWidget):
    key = "quick_actions"
    title = "Quick actions"
    wide = True

    def refresh(self) -> None:
        self._clear_body()
        row = QHBoxLayout()
        row.setSpacing(8)
        for label, dest in (
            ("Take a test", Destination.TESTS),
            ("Open library", Destination.LIBRARY),
            ("View achievements", Destination.ACHIEVEMENTS),
            ("Search", Destination.SEARCH),
        ):
            btn = QPushButton(label)
            btn.setAccessibleName(label)
            btn.clicked.connect(lambda _=False, d=dest: self._go(d))
            row.addWidget(btn)
        row.addStretch(1)
        self.body.addLayout(row)
