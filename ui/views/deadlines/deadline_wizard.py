"""3-step deadline planning wizard and vacation dialog."""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from data.models.deadline import Deadline
from ui.views.deadlines.helpers import qdate, from_qdate


class DeadlinePlanWizard(QDialog):
    """3-step planning wizard for creating or editing a deadline."""

    _STEPS = ("1. About", "2. Plan", "3. Review")

    def __init__(
        self,
        context: AppContext,
        deadline: Deadline | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._deadline_id: int | None = deadline.id if deadline is not None else None
        self._editing = deadline is not None

        self.setWindowTitle("Edit deadline" if deadline else "Plan a deadline")
        self.setMinimumWidth(500)
        self.setMinimumHeight(480)
        self.setAccessibleName(self.windowTitle())

        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        indicator_bar = QWidget()
        indicator_bar.setObjectName("Page")
        indicator_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        ind_layout = QHBoxLayout(indicator_bar)
        ind_layout.setContentsMargins(24, 14, 24, 14)
        ind_layout.setSpacing(0)

        self._step_labels: list[QLabel] = []
        for i, text in enumerate(self._STEPS):
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._step_labels.append(lbl)
            ind_layout.addWidget(lbl, 1)
            if i < len(self._STEPS) - 1:
                sep = QLabel("──")
                sep.setObjectName("SettingsHint")
                sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
                ind_layout.addWidget(sep)
        root.addWidget(indicator_bar)

        self._pages = QStackedWidget()
        self._pages.addWidget(self._build_about_page())
        self._pages.addWidget(self._build_plan_page())
        self._pages.addWidget(self._build_review_page())
        root.addWidget(self._pages, 1)

        nav_bar = QWidget()
        nav_bar.setObjectName("Page")
        nav_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(24, 12, 24, 16)
        nav_layout.setSpacing(10)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setAccessibleName("Cancel — discard and close")
        self._cancel_btn.clicked.connect(self.reject)
        nav_layout.addWidget(self._cancel_btn)
        nav_layout.addStretch(1)

        self._back_btn = QPushButton("← Back")
        self._back_btn.setAccessibleName("Back to previous step")
        self._back_btn.clicked.connect(self._go_back)
        self._back_btn.setEnabled(False)
        nav_layout.addWidget(self._back_btn)

        self._next_btn = QPushButton("Next →")
        self._next_btn.setDefault(True)
        self._next_btn.setAccessibleName("Next step")
        self._next_btn.clicked.connect(self._go_next)
        nav_layout.addWidget(self._next_btn)
        root.addWidget(nav_bar)

        if deadline is not None:
            self._name_edit.setText(deadline.name)
            self._date_edit.setDate(qdate(deadline.target_date))
            self._focus_check.setChecked(deadline.focus)
            self._phase_edit.setText(deadline.phase or "")
            self._skip_weekends_check.setChecked(deadline.skip_weekends)
            if deadline.daily_cap:
                self._cap_spin.setValue(deadline.daily_cap)

        self._update_indicator(0)

    # ------------------------------------------------------------------
    # Page builders
    # ------------------------------------------------------------------

    def _build_about_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("Page")
        page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 16)
        layout.setSpacing(16)

        heading = QLabel("What are you preparing for?")
        heading.setObjectName("PageSubtitle")
        layout.addWidget(heading)

        form = QFormLayout()
        form.setSpacing(12)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Biology final exam")
        self._name_edit.setAccessibleName("Deadline name — required")
        form.addRow("Name *", self._name_edit)

        self._date_edit = QDateEdit()
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("ddd, MMM d yyyy")
        self._date_edit.setDate(QDate.currentDate().addDays(14))
        self._date_edit.setAccessibleName("Target date")
        if not self._editing:
            self._date_edit.setMinimumDate(QDate.currentDate())
        form.addRow("Target date", self._date_edit)

        self._focus_check = QCheckBox("Pin as focus deadline")
        self._focus_check.setAccessibleName(
            "Focus deadline — pinned to the top and shown on the dashboard"
        )
        form.addRow("", self._focus_check)
        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _build_plan_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("Page")
        page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 16)
        layout.setSpacing(16)

        heading = QLabel("Set up your study plan")
        heading.setObjectName("PageSubtitle")
        layout.addWidget(heading)

        form = QFormLayout()
        form.setSpacing(12)

        self._phase_edit = QLineEdit()
        self._phase_edit.setPlaceholderText("e.g. Chapter 3–7 (optional)")
        self._phase_edit.setAccessibleName("Current study phase")
        form.addRow("Current phase", self._phase_edit)

        self._skip_weekends_check = QCheckBox("Skip weekends (Sat & Sun) in daily target")
        self._skip_weekends_check.setAccessibleName(
            "Skip weekends — Saturday and Sunday excluded from days-left count"
        )
        form.addRow("", self._skip_weekends_check)

        cap_row = QHBoxLayout()
        self._cap_spin = QSpinBox()
        self._cap_spin.setRange(0, 9999)
        self._cap_spin.setValue(0)
        self._cap_spin.setSpecialValueText("No cap")
        self._cap_spin.setAccessibleName("Daily goal — cards to review per day")
        self._cap_spin.setSuffix("  cards/day")
        cap_row.addWidget(self._cap_spin)
        cap_row.addStretch(1)
        form.addRow("Daily goal", cap_row)

        cap_hint = QLabel(
            "Set a daily goal to limit your review sessions. "
            "The plan review will warn you if the goal means you won't finish in time."
        )
        cap_hint.setObjectName("SettingsHint")
        cap_hint.setWordWrap(True)
        layout.addLayout(form)
        layout.addWidget(cap_hint)

        deck_lbl = QLabel("Link decks")
        deck_lbl.setObjectName("FieldLabel")
        layout.addWidget(deck_lbl)

        deck_hint = QLabel("Linked deck card counts feed the daily target calculation.")
        deck_hint.setObjectName("SettingsHint")
        deck_hint.setWordWrap(True)
        layout.addWidget(deck_hint)

        deck_scroll = QScrollArea()
        deck_scroll.setWidgetResizable(True)
        deck_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        deck_scroll.setMinimumHeight(110)
        deck_scroll.setMaximumHeight(160)
        deck_scroll.setAccessibleName("Linked decks — check to include in deadline tracking")

        deck_container = QWidget()
        deck_container.setObjectName("Page")
        deck_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._deck_layout = QVBoxLayout(deck_container)
        self._deck_layout.setContentsMargins(4, 4, 4, 4)
        self._deck_layout.setSpacing(4)
        self._deck_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        deck_scroll.setWidget(deck_container)
        layout.addWidget(deck_scroll, 1)

        self._deck_checks: dict[int, QCheckBox] = {}
        self._populate_decks()
        return page

    def _build_review_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("Page")
        page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 16)
        layout.setSpacing(14)

        heading = QLabel("Your plan")
        heading.setObjectName("PageSubtitle")
        layout.addWidget(heading)

        self._rv_name = QLabel()
        self._rv_name.setObjectName("DeadlineTitle")
        layout.addWidget(self._rv_name)

        self._rv_date = QLabel()
        self._rv_date.setObjectName("SettingsHint")
        layout.addWidget(self._rv_date)

        self._rv_days = QLabel()
        self._rv_days.setObjectName("FieldLabel")
        layout.addWidget(self._rv_days)

        self._rv_cards = QLabel()
        self._rv_cards.setObjectName("FieldLabel")
        layout.addWidget(self._rv_cards)

        self._rv_pace = QLabel()
        self._rv_pace.setObjectName("FieldLabel")
        layout.addWidget(self._rv_pace)

        self._rv_feasibility = QLabel()
        self._rv_feasibility.setObjectName("SettingsHint")
        self._rv_feasibility.setWordWrap(True)
        layout.addWidget(self._rv_feasibility)

        self._rv_warning = QLabel()
        self._rv_warning.setObjectName("UrgentChip")
        self._rv_warning.setWordWrap(True)
        self._rv_warning.setVisible(False)
        layout.addWidget(self._rv_warning)

        layout.addStretch(1)
        return page

    # ------------------------------------------------------------------
    # Deck population
    # ------------------------------------------------------------------

    def _populate_decks(self) -> None:
        from ui.utils.layouts import clear_layout
        clear_layout(self._deck_layout)
        self._deck_checks.clear()

        if self._context.db is None:
            return

        from data.models import Deck
        from sqlalchemy import select

        with self._context.db.session() as session:
            decks = list(
                session.scalars(
                    select(Deck).where(Deck.deck_type == "card").order_by(Deck.name)
                )
            )
            linked_ids: set[int] = set()
            if self._deadline_id is not None:
                dl = session.get(Deadline, self._deadline_id)
                if dl is not None:
                    linked_ids = {d.id for d in dl.decks}

        for deck in decks:
            prefix = f"{deck.icon}  " if deck.icon else ""
            cb = QCheckBox(f"{prefix}{deck.name}")
            cb.setAccessibleName(f"Link deck: {deck.name}")
            cb.setChecked(deck.id in linked_ids)
            self._deck_checks[deck.id] = cb
            self._deck_layout.addWidget(cb)

    # ------------------------------------------------------------------
    # Review page
    # ------------------------------------------------------------------

    def _refresh_review(self) -> None:
        import math
        from datetime import timedelta

        target = from_qdate(self._date_edit.date())
        today = date.today()
        skip_weekends = self._skip_weekends_check.isChecked()
        cap = self._cap_spin.value() or None

        total_days = 0
        cursor = today + timedelta(days=1)
        while cursor <= target:
            if not (skip_weekends and cursor.weekday() >= 5):
                total_days += 1
            cursor += timedelta(days=1)

        deck_ids = self.selected_deck_ids()
        remaining = 0

        if deck_ids and self._context.db:
            from core.clock import now as _now
            from data.models import Card
            from domain.srs.srs_base import LEARNING, NEW, RELEARNING, REVIEW
            from sqlalchemy import func, select

            with self._context.db.session() as session:
                moment = _now()
                new_count = session.scalar(
                    select(func.count()).select_from(Card).where(
                        Card.deck_id.in_(deck_ids), Card.srs_state == NEW,
                    )
                ) or 0
                due_count = session.scalar(
                    select(func.count()).select_from(Card).where(
                        Card.deck_id.in_(deck_ids),
                        Card.srs_state.in_((LEARNING, RELEARNING, REVIEW)),
                        Card.due <= moment,
                    )
                ) or 0
                remaining = new_count + due_count

        required = math.ceil(remaining / total_days) if total_days > 0 else remaining
        date_str = f"{target.strftime('%a, %b')} {target.day}, {target.year}"
        days_text = f"in {(target - today).days} calendar days"
        if skip_weekends:
            days_text += f"  ·  {total_days} study days (weekends excluded)"
        else:
            days_text += f"  ·  {total_days} study days"

        is_past = target <= today
        self._rv_name.setText(self._name_edit.text().strip() or "(unnamed)")
        self._rv_date.setText(f"Target: {date_str}  ·  {days_text}")

        if is_past:
            self._rv_days.setText("⚠ Target date is in the past")
            self._rv_cards.setText("")
            self._rv_pace.setText("")
            self._rv_feasibility.setText("")
            self._rv_warning.setVisible(False)
            return

        self._rv_days.setText(
            f"Study days available: {total_days}"
            + (" (weekends skipped)" if skip_weekends else "")
        )

        if deck_ids:
            self._rv_cards.setText(
                f"Cards to review across {len(deck_ids)} linked "
                f"deck{'s' if len(deck_ids) != 1 else ''}: {remaining}"
            )
        else:
            self._rv_cards.setText("No decks linked — daily pace will be 0")

        if total_days == 0:
            self._rv_pace.setText("No study days left before the deadline")
            self._rv_feasibility.setText("Consider moving the target date.")
            self._rv_warning.setVisible(False)
            return

        self._rv_pace.setText(
            f"Required pace: {required} card{'s' if required != 1 else ''}/day"
        )

        if cap:
            if required <= cap:
                self._rv_feasibility.setText(
                    f"✓ Your cap of {cap} cards/day covers the required pace. You're on track."
                )
                self._rv_warning.setVisible(False)
            else:
                shortfall = required - cap
                self._rv_feasibility.setText(
                    f"Your cap of {cap}/day is {shortfall} "
                    f"card{'s' if shortfall != 1 else ''}/day below the required pace."
                )
                self._rv_warning.setText(
                    f"⚠ At {cap} cards/day you won't finish by the deadline. "
                    "Consider raising your cap or extending your target date."
                )
                self._rv_warning.setVisible(True)
        else:
            self._rv_feasibility.setText(
                "No daily cap set — you'll aim for the required pace each day."
            )
            self._rv_warning.setVisible(False)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _update_indicator(self, step: int) -> None:
        for i, lbl in enumerate(self._step_labels):
            if i == step:
                lbl.setObjectName("FieldLabel")
            elif i < step:
                lbl.setObjectName("StateBadgeReview")
            else:
                lbl.setObjectName("SettingsHint")
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)
        self._back_btn.setEnabled(step > 0)
        is_last = step == len(self._STEPS) - 1
        self._next_btn.setText(
            "Save" if (is_last and self._editing)
            else "Create" if is_last
            else "Next →"
        )

    def _go_next(self) -> None:
        step = self._pages.currentIndex()
        if step == 0:
            if not self._name_edit.text().strip():
                self._name_edit.setFocus()
                return
            if not self._editing:
                if from_qdate(self._date_edit.date()) < date.today():
                    self._date_edit.setFocus()
                    return
        if step == len(self._STEPS) - 1:
            self.accept()
            return
        next_step = step + 1
        if next_step == 2:
            self._refresh_review()
        self._pages.setCurrentIndex(next_step)
        self._update_indicator(next_step)

    def _go_back(self) -> None:
        step = self._pages.currentIndex()
        if step == 0:
            return
        self._pages.setCurrentIndex(step - 1)
        self._update_indicator(step - 1)

    # ------------------------------------------------------------------
    # Result accessors
    # ------------------------------------------------------------------

    def name(self) -> str:
        return self._name_edit.text().strip()

    def target_date(self) -> date:
        return from_qdate(self._date_edit.date())

    def focus(self) -> bool:
        return self._focus_check.isChecked()

    def phase(self) -> str:
        return self._phase_edit.text().strip()

    def skip_weekends(self) -> bool:
        return self._skip_weekends_check.isChecked()

    def daily_cap(self) -> int | None:
        value = self._cap_spin.value()
        return value if value > 0 else None

    def selected_deck_ids(self) -> list[int]:
        return [did for did, cb in self._deck_checks.items() if cb.isChecked()]


class VacationDialog(QDialog):
    """Add a vacation/skip-day range to a deadline."""

    def __init__(self, deadline_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Add skip days — {deadline_name}")
        self.setAccessibleName(self.windowTitle())
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        info = QLabel(
            "Skip days are excluded from daily-target calculations. "
            "Use these for vacations, illness, or any days you won't study."
        )
        info.setObjectName("SettingsHint")
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        form.setSpacing(8)

        self._start_edit = QDateEdit()
        self._start_edit.setCalendarPopup(True)
        self._start_edit.setDisplayFormat("ddd, MMM d yyyy")
        self._start_edit.setDate(QDate.currentDate())
        self._start_edit.setAccessibleName("Skip range start date")
        form.addRow("Start", self._start_edit)

        self._end_edit = QDateEdit()
        self._end_edit.setCalendarPopup(True)
        self._end_edit.setDisplayFormat("ddd, MMM d yyyy")
        self._end_edit.setDate(QDate.currentDate().addDays(6))
        self._end_edit.setAccessibleName("Skip range end date")
        form.addRow("End", self._end_edit)

        self._note_edit = QLineEdit()
        self._note_edit.setPlaceholderText("Optional label, e.g. Spring break")
        self._note_edit.setAccessibleName("Skip range label")
        form.addRow("Label", self._note_edit)

        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        if self._end_edit.date() < self._start_edit.date():
            QMessageBox.warning(self, "Invalid dates",
                                "End date must be on or after the start date.")
            self._end_edit.setFocus()
            return
        super().accept()

    def start_date(self) -> date:
        return from_qdate(self._start_edit.date())

    def end_date(self) -> date:
        return from_qdate(self._end_edit.date())

    def note(self) -> str | None:
        text = self._note_edit.text().strip()
        return text if text else None
