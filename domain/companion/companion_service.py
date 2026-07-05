"""Companion XP, level management, and state persistence (§6.3)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from core.clock import now
from data.models.companion import XP_PER_LEVEL, CompanionState

# XP granted for each study event.
XP_FOCUS_BLOCK = 20
XP_DIAGNOSTIC_COMPLETE = 10
XP_CONFIDENCE_IMPROVED = 15
XP_REVIEWED_CARDS = 5
XP_RETURN_AFTER_GAP = 25

# A full day's growth, for the dashboard "grown today" bar.
DAILY_GROWTH_GOAL = 60


def _today_str() -> str:
    return now().strftime("%Y-%m-%d")


class CompanionService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # -- read ----------------------------------------------------------------

    def get_or_create(self, kind: str = "tree") -> CompanionState:
        companion = self._session.query(CompanionState).first()
        if companion is None:
            companion = CompanionState(kind=kind)
            self._session.add(companion)
            self._session.flush()
        return companion

    # -- XP / levelling ------------------------------------------------------

    def award_xp(self, companion: CompanionState, amount: int) -> int:
        """Add XP, handle level-ups, track today's growth, return new total XP."""
        companion.xp += amount

        # Daily growth bookkeeping: reset the counter on a date rollover so the
        # dashboard widget shows only what was grown *today*.
        today = _today_str()
        if companion.xp_today_date != today:
            companion.xp_today = 0
            companion.xp_today_date = today
        companion.xp_today += amount

        # Level up while enough XP accumulated (multi-level possible).
        threshold = companion.level * XP_PER_LEVEL
        while companion.xp >= threshold:
            companion.xp -= threshold
            companion.level += 1
            threshold = companion.level * XP_PER_LEVEL
        companion.updated_at = now()
        return companion.xp

    def growth_today(self, companion: CompanionState) -> int:
        """XP grown today (0 if the stored figure is from a previous day)."""
        if companion.xp_today_date != _today_str():
            return 0
        return companion.xp_today

    def record_focus_block(self, companion: CompanionState) -> int:
        return self.award_xp(companion, XP_FOCUS_BLOCK)

    def record_diagnostic_complete(
        self, companion: CompanionState, improved: bool = False
    ) -> int:
        xp = XP_DIAGNOSTIC_COMPLETE + (XP_CONFIDENCE_IMPROVED if improved else 0)
        return self.award_xp(companion, xp)

    def record_cards_reviewed(self, companion: CompanionState) -> int:
        return self.award_xp(companion, XP_REVIEWED_CARDS)

    def record_return_after_gap(self, companion: CompanionState) -> int:
        return self.award_xp(companion, XP_RETURN_AFTER_GAP)

    def record_fed(self, companion: CompanionState) -> None:
        companion.last_fed_at = now()
        companion.updated_at = now()

    # -- gap detection -------------------------------------------------------

    def is_returning_after_gap(self, companion: CompanionState) -> bool:
        """True if the companion has not been fed in more than 24 hours."""
        if companion.last_fed_at is None:
            return True
        delta = datetime.now(timezone.utc) - companion.last_fed_at.replace(
            tzinfo=timezone.utc
        )
        return delta.total_seconds() > 86_400
