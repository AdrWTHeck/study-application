"""SM-2 scheduling engine (ported), operating on the decoupled CardState.

States: new → learning (stepped) → review; a lapse in review drops to relearning
then back to review. Engines are pure: ``review`` returns a *new* CardState and
never touches the DB. Due times are datetimes so sub-day learning steps work.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from domain.srs import constants as C
from domain.srs.srs_base import (
    LEARNING,
    NEW,
    RELEARNING,
    REVIEW,
    CardState,
    Rating,
)


class Sm2Engine:
    name = "sm2"

    def new_state(self, now: datetime) -> CardState:
        return CardState(state=NEW, due=now, ease_factor=C.EASE_DEFAULT)

    def review(self, state: CardState, rating: Rating, now: datetime) -> CardState:
        s = state.copy()
        s.last_review = now
        if s.state in (NEW, LEARNING):
            return self._step(s, rating, now, C.LEARNING_STEPS_MINUTES, LEARNING)
        if s.state == RELEARNING:
            return self._step(s, rating, now, C.RELEARNING_STEPS_MINUTES, RELEARNING)
        return self._review(s, rating, now)

    # -- learning / relearning --------------------------------------------

    def _step(self, s: CardState, rating: Rating, now: datetime,
              steps: list[int], phase: str) -> CardState:
        if rating == Rating.AGAIN:
            s.state = phase
            s.learning_step = 0
            s.due = now + timedelta(minutes=steps[0])
            return s
        if rating == Rating.HARD:
            s.state = phase
            step = min(s.learning_step, len(steps) - 1)
            s.learning_step = step
            s.due = now + timedelta(minutes=steps[step])
            return s
        if rating == Rating.GOOD:
            nxt = s.learning_step + 1
            if nxt < len(steps):
                s.state = phase
                s.learning_step = nxt
                s.due = now + timedelta(minutes=steps[nxt])
                return s
            return self._graduate(s, now, C.GRADUATING_INTERVAL_DAYS)
        # EASY
        return self._graduate(s, now, C.EASY_GRADUATING_INTERVAL_DAYS)

    def _graduate(self, s: CardState, now: datetime, interval_days: int) -> CardState:
        s.state = REVIEW
        s.learning_step = 0
        s.interval_days = float(interval_days)
        s.reps += 1
        if s.ease_factor < C.EASE_MIN:
            s.ease_factor = C.EASE_DEFAULT
        s.due = now + timedelta(days=interval_days)
        return s

    # -- review ------------------------------------------------------------

    def _review(self, s: CardState, rating: Rating, now: datetime) -> CardState:
        if rating == Rating.AGAIN:
            s.lapses += 1
            s.ease_factor = max(C.EASE_MIN, s.ease_factor + C.EASE_LAPSE_DELTA)
            s.state = RELEARNING
            s.learning_step = 0
            s.interval_days = max(1.0, s.interval_days * C.LAPSE_INTERVAL_MULTIPLIER)
            s.due = now + timedelta(minutes=C.RELEARNING_STEPS_MINUTES[0])
            return s
        if rating == Rating.HARD:
            s.ease_factor = max(C.EASE_MIN, s.ease_factor + C.EASE_HARD_DELTA)
            s.interval_days = max(s.interval_days + 1, s.interval_days * C.HARD_INTERVAL_MULTIPLIER)
            s.reps += 1
            s.due = now + timedelta(days=round(s.interval_days))
            return s
        if rating == Rating.GOOD:
            s.interval_days = max(1.0, s.interval_days * s.ease_factor)
            s.reps += 1
            s.due = now + timedelta(days=round(s.interval_days))
            return s
        # EASY
        s.ease_factor = s.ease_factor + C.EASE_EASY_DELTA
        s.interval_days = max(1.0, s.interval_days * s.ease_factor * C.EASY_BONUS_MULTIPLIER)
        s.reps += 1
        s.due = now + timedelta(days=round(s.interval_days))
        return s
