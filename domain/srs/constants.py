"""SM-2 scheduling constants (ported). No magic numbers in the engine."""
from __future__ import annotations

# Learning / relearning step intervals, in minutes.
LEARNING_STEPS_MINUTES: list[int] = [1, 10]
RELEARNING_STEPS_MINUTES: list[int] = [10]

# Graduation intervals (days).
GRADUATING_INTERVAL_DAYS: int = 1       # Good graduates Learning → Review
EASY_GRADUATING_INTERVAL_DAYS: int = 4  # Easy graduates immediately

# Ease factor.
EASE_DEFAULT: float = 2.5
EASE_MIN: float = 1.3
EASE_HARD_DELTA: float = -0.15
EASE_EASY_DELTA: float = 0.15
EASE_LAPSE_DELTA: float = -0.20

# Review interval multipliers.
HARD_INTERVAL_MULTIPLIER: float = 1.2
EASY_BONUS_MULTIPLIER: float = 1.3
LAPSE_INTERVAL_MULTIPLIER: float = 0.0  # reset interval on lapse (floored to 1 day)

# Session.
NEW_CARDS_PER_SESSION_DEFAULT: int = 20
