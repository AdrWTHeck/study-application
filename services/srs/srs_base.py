"""SRSBase Protocol and CardRating enum.

Card satisfies SRSBase structurally (duck typing) — models/ cannot import
from services/, so explicit ABC inheritance is not used.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Protocol, runtime_checkable


class CardRating(Enum):
    VERY_HARD = "very_hard"
    HARD = "hard"
    GOOD = "good"
    EASY = "easy"


@runtime_checkable
class SRSBase(Protocol):
    """Structural interface for SM-2 scheduling.

    Card satisfies this interface.  Question does NOT (CON-12 / NFR-15).
    """

    # Required attributes
    category: str           # "new" | "learning" | "review"
    learning_step: int      # index into step array
    ease_factor: float      # default 2.5; active in Review only
    interval: int           # days; active in Review only
    repetitions: int        # default 0; active in Review only
    next_review_date: date

    def get_id(self) -> int: ...
    def get_deck_type(self) -> str: ...
