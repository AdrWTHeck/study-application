"""SRS engine interface + the decoupled card state it operates on.

``Rating`` values are 1–4 to line up with both our rating buttons and FSRS's
Rating enum (future-proofing). ``CardState`` is a superset that carries both
SM-2 fields and FSRS fields, so one schema serves either engine.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import IntEnum
from typing import Protocol, runtime_checkable

# Display / scheduling states.
NEW = "new"
LEARNING = "learning"
REVIEW = "review"
RELEARNING = "relearning"


class Rating(IntEnum):
    AGAIN = 1
    HARD = 2
    GOOD = 3
    EASY = 4


@dataclass
class CardState:
    state: str = NEW
    due: datetime | None = None            # naive UTC; None ⇒ due now (fresh card)
    last_review: datetime | None = None
    reps: int = 0
    lapses: int = 0
    learning_step: int = 0
    # SM-2
    ease_factor: float = 2.5
    interval_days: float = 0.0
    # FSRS (unused by SM-2; reserved so the schema/engine swap needs no migration)
    stability: float | None = None
    difficulty: float | None = None

    def copy(self) -> "CardState":
        return replace(self)


@runtime_checkable
class SrsEngine(Protocol):
    name: str

    def new_state(self, now: datetime) -> CardState: ...

    def review(self, state: CardState, rating: Rating, now: datetime) -> CardState: ...
