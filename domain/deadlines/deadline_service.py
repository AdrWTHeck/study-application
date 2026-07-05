"""Deadline tracker service.

Manages deadlines, their attached decks, vacation ranges, and computes
daily study targets so learners know exactly how many cards to do each day.

Target formula:
  remaining = new cards + due cards across all attached decks
  days_left  = calendar days from today+1 to target_date (inclusive),
               minus vacation-day ranges
  daily_target = ceil(remaining / max(days_left, 1))
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from core.clock import now
from data.models import Card, Deck, ReviewLog
from data.models.deadline import Deadline, VacationDay, deadline_decks
from domain.search import indexer
from domain.srs.srs_base import LEARNING, NEW, RELEARNING, REVIEW


@dataclass
class DeadlineSummary:
    """All fields are plain Python values — safe to use after the session closes (C1)."""
    deadline_id: int
    name: str
    target_date: date
    created_at: date       # deadline creation date — timeline start
    focus: bool
    deck_names: list[str]
    deck_ids: list[int]    # parallel to deck_names — for click-through navigation
    deck_icons: list[str | None]  # parallel to deck_names — emoji icon or None
    days_left: int
    is_past: bool          # target_date < reference date (C7)
    total_remaining: int
    daily_target: int | None  # None when past-due — not a meaningful number (C8)
    total_cards: int       # all cards in linked decks (for progress bar)
    reviewed_today: int    # distinct cards reviewed today in linked decks
    phase: str | None      # current study phase label (e.g. "Chapter 3–5")
    is_rest_day: bool      # today falls within a vacation range
    status_badge: str      # ON TRACK · BEHIND · REST DAY · NOT STARTED · ALL DONE · OVERDUE
    smart_message: str     # computed single-line coaching hint
    daily_cap: int | None  # user's self-imposed max cards/day
    required_daily: int | None  # uncapped computed pace (before applying daily_cap)
    is_over_cap: bool      # required pace exceeds the user's cap — they won't finish in time
    skip_weekends: bool    # deadline was created with weekend exclusion


# ---------------------------------------------------------------------------
# Pure-function helpers for badge / message (no DB access)
# ---------------------------------------------------------------------------

def _compute_status_badge(remaining: int, daily: int | None, reviewed: int,
                           is_past: bool, is_rest: bool, total: int) -> str:
    if is_past:
        return "OVERDUE"
    if remaining == 0:
        return "ALL DONE"
    if is_rest:
        return "REST DAY"
    if total > 0 and remaining == total:
        return "NOT STARTED"
    if daily is None:
        return "NOT STARTED"
    if reviewed >= daily:
        return "ON TRACK"
    return "BEHIND"


def _compute_smart_message(badge: str, reviewed: int, daily: int | None,
                            remaining: int, days_left: int) -> str:
    if badge == "ALL DONE":
        return "All cards cleared — great work!"
    if badge == "OVERDUE":
        n = remaining
        return f"Deadline passed — {n} card{'s' if n != 1 else ''} not completed."
    if badge == "REST DAY":
        return "Rest day — enjoy your break!"
    if badge == "NOT STARTED":
        return "Start reviewing to build momentum."
    if badge == "ON TRACK":
        if daily and reviewed >= daily:
            return f"Done for today! {reviewed} card{'s' if reviewed != 1 else ''} reviewed."
        return "You're on track — keep it up!"
    if badge == "BEHIND":
        needed = (daily or 0) - reviewed
        if days_left <= 3:
            return (
                f"Only {days_left} day{'s' if days_left != 1 else ''} left — "
                f"{needed} more card{'s' if needed != 1 else ''} today!"
            )
        return f"{needed} more card{'s' if needed != 1 else ''} today to stay on track."
    return ""


class DeadlineService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # -- CRUD ---------------------------------------------------------------

    def create(self, name: str, target_date: date, focus: bool = False,
               color: str | None = None, phase: str | None = None,
               skip_weekends: bool = False,
               daily_cap: int | None = None) -> Deadline:
        dl = Deadline(name=name.strip(), target_date=target_date,
                      focus=focus, color=color, phase=phase,
                      skip_weekends=skip_weekends, daily_cap=daily_cap)
        self.session.add(dl)
        self.session.flush()
        indexer.reindex_deadline(self.session, dl)
        return dl

    def update(self, deadline_id: int, name: str | None = None,
               target_date: date | None = None, focus: bool | None = None,
               color: str | None = None, phase: str | None = None,
               skip_weekends: bool | None = None,
               daily_cap: int | None = None,
               clear_daily_cap: bool = False) -> Deadline | None:
        dl = self.session.get(Deadline, deadline_id)
        if dl is None:
            return None
        if name is not None:
            dl.name = name.strip()
        if target_date is not None:
            dl.target_date = target_date
        if focus is not None:
            dl.focus = focus
        if color is not None:
            dl.color = color
        if phase is not None:
            dl.phase = phase.strip() or None
        if skip_weekends is not None:
            dl.skip_weekends = skip_weekends
        if clear_daily_cap:
            dl.daily_cap = None
        elif daily_cap is not None:
            dl.daily_cap = daily_cap
        self.session.flush()
        indexer.reindex_deadline(self.session, dl)  # name may have changed
        return dl

    def delete(self, deadline_id: int) -> None:
        dl = self.session.get(Deadline, deadline_id)
        if dl is not None:
            self.session.delete(dl)
            self.session.flush()
            indexer.remove(self.session, "deadline", deadline_id)

    def list_all(self) -> list[Deadline]:
        return list(self.session.scalars(
            select(Deadline).order_by(Deadline.target_date, Deadline.id)
        ))

    def upcoming(self, reference: date | None = None) -> list[Deadline]:
        ref = reference or now().date()
        return list(self.session.scalars(
            select(Deadline)
            .where(Deadline.target_date >= ref)
            .order_by(Deadline.target_date, Deadline.id)
        ))

    def get(self, deadline_id: int) -> Deadline | None:
        return self.session.get(Deadline, deadline_id)

    # -- deck attachment ----------------------------------------------------

    def attach_deck(self, deadline_id: int, deck_id: int) -> None:
        dl = self.session.get(Deadline, deadline_id)
        deck = self.session.get(Deck, deck_id)
        if dl is None or deck is None:
            return
        if deck not in dl.decks:
            dl.decks.append(deck)
            self.session.flush()

    def detach_deck(self, deadline_id: int, deck_id: int) -> None:
        dl = self.session.get(Deadline, deadline_id)
        if dl is None:
            return
        dl.decks = [d for d in dl.decks if d.id != deck_id]
        self.session.flush()

    def set_decks(self, deadline_id: int, deck_ids: list[int]) -> None:
        dl = self.session.get(Deadline, deadline_id)
        if dl is None:
            return
        decks = [self.session.get(Deck, did) for did in deck_ids]
        dl.decks = [d for d in decks if d is not None]
        self.session.flush()

    # -- vacation ranges ----------------------------------------------------

    def add_vacation(self, deadline_id: int, start: date, end: date,
                     note: str | None = None) -> VacationDay | None:
        if self.session.get(Deadline, deadline_id) is None:
            return None
        if end < start:
            start, end = end, start
        vac = VacationDay(deadline_id=deadline_id, start_date=start, end_date=end, note=note)
        self.session.add(vac)
        self.session.flush()
        return vac

    def remove_vacation(self, vacation_id: int) -> None:
        vac = self.session.get(VacationDay, vacation_id)
        if vac is not None:
            self.session.delete(vac)
            self.session.flush()

    def list_vacations(self, deadline_id: int) -> list[VacationDay]:
        return list(self.session.scalars(
            select(VacationDay)
            .where(VacationDay.deadline_id == deadline_id)
            .order_by(VacationDay.start_date)
        ))

    # -- target computation -------------------------------------------------

    def _vacation_dates(self, deadline: Deadline) -> set[date]:
        blocked: set[date] = set()
        for vac in deadline.vacations:
            cursor = vac.start_date
            while cursor <= vac.end_date:
                blocked.add(cursor)
                cursor += timedelta(days=1)
        return blocked

    def days_left(self, deadline: Deadline, reference: date | None = None) -> int:
        ref = reference or now().date()
        if deadline.target_date <= ref:
            return 0
        blocked = self._vacation_dates(deadline)
        count = 0
        cursor = ref + timedelta(days=1)
        while cursor <= deadline.target_date:
            is_weekend = cursor.weekday() >= 5  # 5=Sat, 6=Sun
            if cursor not in blocked and not (deadline.skip_weekends and is_weekend):
                count += 1
            cursor += timedelta(days=1)
        return count

    def _is_rest_day(self, deadline: Deadline, reference: date | None = None) -> bool:
        ref = reference or now().date()
        return ref in self._vacation_dates(deadline)

    def _total_cards(self, deadline: Deadline) -> int:
        if not deadline.decks:
            return 0
        deck_ids = [d.id for d in deadline.decks]
        return self.session.scalar(
            select(func.count()).select_from(Card).where(Card.deck_id.in_(deck_ids))
        ) or 0

    def _reviewed_today(self, deadline: Deadline, reference: date | None = None) -> int:
        if not deadline.decks:
            return 0
        ref = reference or now().date()
        deck_ids = [d.id for d in deadline.decks]
        day_start = datetime(ref.year, ref.month, ref.day)
        return self.session.scalar(
            select(func.count(distinct(ReviewLog.card_id)))
            .join(Card, ReviewLog.card_id == Card.id)
            .where(Card.deck_id.in_(deck_ids), ReviewLog.reviewed_at >= day_start)
        ) or 0

    def _remaining_cards(self, deadline: Deadline) -> int:
        if not deadline.decks:
            return 0
        deck_ids = [d.id for d in deadline.decks]
        moment = now()
        new = self.session.scalar(
            select(func.count()).select_from(Card).where(
                Card.deck_id.in_(deck_ids), Card.srs_state == NEW
            )
        ) or 0
        due = self.session.scalar(
            select(func.count()).select_from(Card).where(
                Card.deck_id.in_(deck_ids),
                Card.srs_state.in_((LEARNING, RELEARNING, REVIEW)),
                Card.due <= moment,
            )
        ) or 0
        return new + due

    def daily_target(self, deadline: Deadline, reference: date | None = None) -> int | None:
        ref = reference or now().date()
        remaining = self._remaining_cards(deadline)
        if deadline.target_date < ref:
            return None  # past-due: no meaningful daily number (C8)
        left = self.days_left(deadline, ref)
        if left == 0:
            return remaining  # due today: do it all today
        return math.ceil(remaining / left)

    def summarize(self, deadline: Deadline, reference: date | None = None) -> DeadlineSummary:
        ref = reference or now().date()
        left = self.days_left(deadline, ref)
        remaining = self._remaining_cards(deadline)
        is_past = deadline.target_date < ref  # C7
        if is_past:
            required: int | None = None  # C8
        elif left == 0:
            required = remaining  # due today
        else:
            required = math.ceil(remaining / left)

        # Apply daily_cap: daily_target is capped; required_daily is the uncapped pace
        cap = deadline.daily_cap
        daily = min(required, cap) if (required is not None and cap) else required
        is_over_cap = bool(required and cap and required > cap)

        total = self._total_cards(deadline)
        reviewed = self._reviewed_today(deadline, ref)
        is_rest = self._is_rest_day(deadline, ref)
        badge = _compute_status_badge(remaining, daily, reviewed, is_past, is_rest, total)
        message = _compute_smart_message(badge, reviewed, daily, remaining, left)

        return DeadlineSummary(
            deadline_id=deadline.id,
            name=deadline.name,
            target_date=deadline.target_date,
            created_at=deadline.created_at.date(),
            focus=deadline.focus,
            deck_names=[d.name for d in deadline.decks],
            deck_ids=[d.id for d in deadline.decks],
            deck_icons=[d.icon for d in deadline.decks],
            days_left=left,
            is_past=is_past,
            total_remaining=remaining,
            daily_target=daily,
            total_cards=total,
            reviewed_today=reviewed,
            phase=deadline.phase,
            is_rest_day=is_rest,
            status_badge=badge,
            smart_message=message,
            daily_cap=deadline.daily_cap,
            required_daily=required,
            is_over_cap=is_over_cap,
            skip_weekends=deadline.skip_weekends,
        )

    def soonest(self, reference: date | None = None) -> DeadlineSummary | None:
        upcoming = self.upcoming(reference)
        if not upcoming:
            return None
        return self.summarize(upcoming[0], reference)

    def all_summaries(self, reference: date | None = None) -> list[DeadlineSummary]:
        return [self.summarize(dl, reference) for dl in self.upcoming(reference)]

    def deadline_for_deck(self, deck_id: int, reference: date | None = None) -> DeadlineSummary | None:
        """Soonest upcoming deadline that has this deck linked (F2)."""
        ref = reference or now().date()
        dl = self.session.scalar(
            select(Deadline)
            .join(deadline_decks, Deadline.id == deadline_decks.c.deadline_id)
            .where(deadline_decks.c.deck_id == deck_id)
            .where(Deadline.target_date >= ref)
            .order_by(Deadline.target_date, Deadline.id)
        )
        if dl is None:
            return None
        return self.summarize(dl, reference)

    def deadlines_for_decks(
        self,
        deck_ids: list[int],
        reference: date | None = None,
    ) -> dict[int, DeadlineSummary | None]:
        """Return the soonest upcoming deadline for each deck in one query (F2-batch).

        Replaces one deadline_for_deck() call per deck with a single JOIN query.
        Keys are every deck_id from the input; value is None when no deadline is linked.
        """
        if not deck_ids:
            return {}
        ref = reference or now().date()
        result: dict[int, DeadlineSummary | None] = dict.fromkeys(deck_ids, None)

        rows = list(self.session.execute(
            select(deadline_decks.c.deck_id, Deadline)
            .join(Deadline, Deadline.id == deadline_decks.c.deadline_id)
            .where(deadline_decks.c.deck_id.in_(deck_ids))
            .where(Deadline.target_date >= ref)
            .order_by(deadline_decks.c.deck_id, Deadline.target_date, Deadline.id)
        ))

        assigned: set[int] = set()
        for row in rows:
            deck_id, deadline_obj = row[0], row[1]
            if deck_id not in assigned:
                assigned.add(deck_id)
                result[deck_id] = self.summarize(deadline_obj, reference)

        return result

    def past_summaries(self, reference: date | None = None) -> list[DeadlineSummary]:
        ref = reference or now().date()
        past = list(self.session.scalars(
            select(Deadline)
            .where(Deadline.target_date < ref)
            .order_by(Deadline.target_date.desc(), Deadline.id)
        ))
        return [self.summarize(dl, reference) for dl in past]
