"""Category-aware SM-2 engine.

Routes to one of three private updaters based on card.category and returns
a CardUpdateResult.  All scheduling constants come from config/constants.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from config.constants import (
    AGAIN_REQUEUE_MINUTES,
    EASE_FACTOR_DEFAULT,
    EASE_FACTOR_EASY_DELTA,
    EASE_FACTOR_HARD_DELTA,
    EASE_FACTOR_MIN,
    EASY_BONUS_MULTIPLIER,
    EASY_GRADUATION_INTERVAL_DAYS,
    GRADUATING_INTERVAL_DAYS,
    HARD_INTERVAL_MULTIPLIER,
    LEARNING_STEPS_MINUTES,
    NEW_STEPS_MINUTES,
)
from services.srs.srs_base import CardRating, SRSBase


@dataclass
class CardUpdateResult:
    card: SRSBase
    should_requeue: bool    # True when Very Hard → card goes to re-queue
    requeue_minutes: int    # 0 if not requeuing


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def update(
    card: SRSBase,
    rating: CardRating,
    consecutive_good: int,
) -> CardUpdateResult:
    """Apply a rating to *card* and return the update result.

    *consecutive_good* is the number of consecutive Good ratings the card
    has received in the current session (tracked in-memory by the controller).
    The engine itself does not persist this value.
    """
    if card.category == "new":
        return _update_new(card, rating, consecutive_good)
    if card.category == "learning":
        return _update_learning(card, rating, consecutive_good)
    return _update_review(card, rating)


# ---------------------------------------------------------------------------
# Per-category updaters
# ---------------------------------------------------------------------------

def _update_new(
    card: SRSBase, rating: CardRating, consecutive_good: int
) -> CardUpdateResult:
    today = date.today()

    if rating == CardRating.VERY_HARD:
        # Reset to step 0; re-queue after NEW_STEPS[0] minutes.
        card.category = "new"
        card.learning_step = 0
        card.next_review_date = today
        return CardUpdateResult(
            card=card,
            should_requeue=True,
            requeue_minutes=NEW_STEPS_MINUTES[0],
        )

    if rating == CardRating.HARD:
        # Stay at current step; next appearance still today.
        card.next_review_date = today
        return CardUpdateResult(card=card, should_requeue=False, requeue_minutes=0)

    if rating == CardRating.GOOD:
        if consecutive_good >= 2:
            # Graduate to Learning.
            card.category = "learning"
            card.learning_step = 0
            card.next_review_date = _learning_date(0)
        else:
            # Advance step if not at the last one.
            next_step = card.learning_step + 1
            if next_step < len(NEW_STEPS_MINUTES):
                card.learning_step = next_step
            card.next_review_date = today
        return CardUpdateResult(card=card, should_requeue=False, requeue_minutes=0)

    # EASY — immediate graduation to Learning.
    card.category = "learning"
    card.learning_step = 0
    card.next_review_date = _learning_date(0)
    return CardUpdateResult(card=card, should_requeue=False, requeue_minutes=0)


def _update_learning(
    card: SRSBase, rating: CardRating, consecutive_good: int
) -> CardUpdateResult:
    today = date.today()

    if rating == CardRating.VERY_HARD:
        # Reset all the way to New; re-queue.
        card.category = "new"
        card.learning_step = 0
        card.ease_factor = EASE_FACTOR_DEFAULT
        card.interval = 1
        card.repetitions = 0
        card.next_review_date = today
        return CardUpdateResult(
            card=card,
            should_requeue=True,
            requeue_minutes=AGAIN_REQUEUE_MINUTES,
        )

    if rating == CardRating.HARD:
        # Stay at current step.
        card.next_review_date = _learning_date(card.learning_step)
        return CardUpdateResult(card=card, should_requeue=False, requeue_minutes=0)

    if rating == CardRating.GOOD:
        if consecutive_good >= 2:
            # Graduate to Review.
            card.category = "review"
            card.interval = GRADUATING_INTERVAL_DAYS
            card.next_review_date = today + timedelta(days=GRADUATING_INTERVAL_DAYS)
        else:
            # Advance step if possible.
            next_step = card.learning_step + 1
            if next_step < len(LEARNING_STEPS_MINUTES):
                card.learning_step = next_step
                card.next_review_date = _learning_date(card.learning_step)
            else:
                # Already at last step; stay put until next session.
                card.next_review_date = _learning_date(card.learning_step)
        return CardUpdateResult(card=card, should_requeue=False, requeue_minutes=0)

    # EASY — immediate graduation to Review with longer interval.
    card.category = "review"
    card.interval = EASY_GRADUATION_INTERVAL_DAYS
    card.next_review_date = today + timedelta(days=EASY_GRADUATION_INTERVAL_DAYS)
    return CardUpdateResult(card=card, should_requeue=False, requeue_minutes=0)


def _update_review(card: SRSBase, rating: CardRating) -> CardUpdateResult:
    today = date.today()

    if rating == CardRating.VERY_HARD:
        # Full reset back to New.
        card.category = "new"
        card.learning_step = 0
        card.ease_factor = EASE_FACTOR_DEFAULT
        card.interval = 1
        card.repetitions = 0
        card.next_review_date = today
        return CardUpdateResult(
            card=card,
            should_requeue=True,
            requeue_minutes=AGAIN_REQUEUE_MINUTES,
        )

    if rating == CardRating.HARD:
        card.ease_factor = max(
            EASE_FACTOR_MIN, card.ease_factor + EASE_FACTOR_HARD_DELTA
        )
        card.interval = max(card.interval + 1, round(card.interval * HARD_INTERVAL_MULTIPLIER))
        card.next_review_date = today + timedelta(days=card.interval)
        card.repetitions += 1
        return CardUpdateResult(card=card, should_requeue=False, requeue_minutes=0)

    if rating == CardRating.GOOD:
        # Standard SM-2: new_interval = interval × ease_factor.
        card.interval = max(1, round(card.interval * card.ease_factor))
        card.next_review_date = today + timedelta(days=card.interval)
        card.repetitions += 1
        return CardUpdateResult(card=card, should_requeue=False, requeue_minutes=0)

    # EASY — apply bonus multiplier and positive ease adjustment.
    card.ease_factor = card.ease_factor + EASE_FACTOR_EASY_DELTA
    card.interval = max(1, round(card.interval * card.ease_factor * EASY_BONUS_MULTIPLIER))
    card.next_review_date = today + timedelta(days=card.interval)
    card.repetitions += 1
    return CardUpdateResult(card=card, should_requeue=False, requeue_minutes=0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _learning_date(step: int) -> date:
    """Convert a Learning step index to a next_review Date."""
    minutes = LEARNING_STEPS_MINUTES[step] if step < len(LEARNING_STEPS_MINUTES) else LEARNING_STEPS_MINUTES[-1]
    days = minutes // 1440  # 1440 minutes per day
    return date.today() + timedelta(days=max(1, days))
