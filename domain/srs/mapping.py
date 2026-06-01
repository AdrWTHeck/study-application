"""Adapt between the Card ORM model and the engine's CardState.

Lives in the domain layer (which may depend on data), keeping the engine itself
free of any ORM import.
"""
from __future__ import annotations

from data.models import Card
from domain.srs.srs_base import CardState


def card_to_state(card: Card) -> CardState:
    return CardState(
        state=card.srs_state,
        due=card.due,
        last_review=card.last_review,
        reps=card.reps,
        lapses=card.lapses,
        learning_step=card.learning_step,
        ease_factor=card.ease_factor,
        interval_days=card.interval_days,
        stability=card.stability,
        difficulty=card.difficulty,
    )


def apply_state(card: Card, state: CardState) -> None:
    card.srs_state = state.state
    card.due = state.due
    card.last_review = state.last_review
    card.reps = state.reps
    card.lapses = state.lapses
    card.learning_step = state.learning_step
    card.ease_factor = state.ease_factor
    card.interval_days = state.interval_days
    card.stability = state.stability
    card.difficulty = state.difficulty
