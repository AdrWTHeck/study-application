"""FSRS-6 scheduling engine wrapping py-fsrs, behind the SrsEngine protocol.

FSRS is the only scheduler. It operates on the decoupled :class:`CardState`, so
the rest of the app (queue building, persistence, review log, stats) never depends
on the engine.

Boundary concerns handled here:
  * **Datetimes** — our app uses *naive UTC* (``core.clock.now``); FSRS uses
    *tz-aware UTC*. We convert in/out at this boundary only.
  * **State model** — FSRS has Learning/Review/Relearning. A never-studied card is
    our ``NEW`` → a fresh FSRS Learning card (step 0, no memory state yet).
  * **Migration (safe-init)** — a card carried over from SM-2 is in a reviewed
    state but has no ``stability``/``difficulty``. FSRS asserts those exist for
    Review/Relearning, so we seed them from the card's current interval before the
    first FSRS review. Existing progress (due date, reps, lapses) is preserved.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fsrs import Card as FsrsCard
from fsrs import Rating as FsrsRating
from fsrs import Scheduler
from fsrs import State as FsrsState

from domain.srs.srs_base import (
    LEARNING,
    NEW,
    RELEARNING,
    REVIEW,
    CardState,
    Rating,
)

# Default difficulty (FSRS range 1–10) for a card migrated from SM-2 that has no
# difficulty yet. Mid-range is a neutral starting point.
_MIGRATION_DIFFICULTY = 5.0

_FSRS_STATE_TO_OURS = {
    FsrsState.Learning: LEARNING,
    FsrsState.Review: REVIEW,
    FsrsState.Relearning: RELEARNING,
}
_OURS_TO_FSRS_STATE = {
    LEARNING: FsrsState.Learning,
    REVIEW: FsrsState.Review,
    RELEARNING: FsrsState.Relearning,
}


def _to_aware(dt: datetime | None) -> datetime | None:
    """Naive-UTC (or aware) → tz-aware UTC for FSRS."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _to_naive(dt: datetime | None) -> datetime | None:
    """FSRS tz-aware UTC → naive UTC for our storage."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class FsrsEngine:
    name = "fsrs"

    def __init__(self, scheduler: Scheduler | None = None) -> None:
        # Default FSRS-6 weights — no training needed, schedules offline.
        self._scheduler = scheduler or Scheduler()

    def new_state(self, now: datetime) -> CardState:
        # A fresh card carries no memory state yet; FSRS seeds it on first review.
        return CardState(state=NEW, due=now, stability=None, difficulty=None)

    def review(self, state: CardState, rating: Rating, now: datetime) -> CardState:
        fsrs_card = self._to_fsrs_card(state, now)
        new_card, _log = self._scheduler.review_card(
            fsrs_card, FsrsRating(int(rating)), review_datetime=_to_aware(now)
        )

        s = state.copy()
        s.state = _FSRS_STATE_TO_OURS.get(new_card.state, REVIEW)
        s.learning_step = new_card.step or 0
        s.stability = new_card.stability
        s.difficulty = new_card.difficulty
        s.due = _to_naive(new_card.due)
        s.last_review = _to_naive(new_card.last_review) or now
        s.reps = state.reps + 1
        # A lapse = a Review-state card answered Again (drops to relearning).
        if state.state == REVIEW and rating == Rating.AGAIN:
            s.lapses = state.lapses + 1
        # Keep interval_days populated for stats/UI continuity (days to next due).
        if s.due is not None and s.last_review is not None:
            s.interval_days = max(0.0, (s.due - s.last_review).total_seconds() / 86400.0)
        return s

    # -- internals ----------------------------------------------------------

    def _to_fsrs_card(self, state: CardState, now: datetime) -> FsrsCard:
        if state.state == NEW:
            return FsrsCard(
                state=FsrsState.Learning,
                step=0,
                stability=None,
                difficulty=None,
                due=_to_aware(now),
                last_review=None,
            )

        fsrs_state = _OURS_TO_FSRS_STATE.get(state.state, FsrsState.Review)
        stability, difficulty = self._memory_or_seed(state, fsrs_state)
        # FSRS uses `step` only while (re)learning; Review cards carry step=None.
        step = None if fsrs_state is FsrsState.Review else (state.learning_step or 0)
        return FsrsCard(
            state=fsrs_state,
            step=step,
            stability=stability,
            difficulty=difficulty,
            due=_to_aware(state.due) if state.due is not None else _to_aware(now),
            last_review=_to_aware(state.last_review),
        )

    @staticmethod
    def _memory_or_seed(
        state: CardState, fsrs_state: FsrsState
    ) -> tuple[float | None, float | None]:
        """Return (stability, difficulty), safe-initializing migrated SM-2 cards.

        FSRS asserts that Review/Relearning cards have real memory values. A card
        carried over from SM-2 has none, so seed stability from its current
        interval (a reasonable proxy) and difficulty to a neutral mid-range value.
        Learning-state cards may keep ``None`` — FSRS seeds them on review.
        """
        if state.stability is not None and state.difficulty is not None:
            return state.stability, state.difficulty
        if fsrs_state is FsrsState.Learning:
            return state.stability, state.difficulty  # FSRS handles None here
        seed_stability = state.stability
        if seed_stability is None:
            seed_stability = max(float(state.interval_days or 0.0), 0.5)
        seed_difficulty = state.difficulty if state.difficulty is not None else _MIGRATION_DIFFICULTY
        return seed_stability, seed_difficulty
