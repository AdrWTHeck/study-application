"""Spaced-repetition scheduling.

Engines operate on a decoupled :class:`CardState` behind the :class:`SrsEngine`
interface, so SM-2 (default) and a future FSRS engine are swappable without
touching the models or UI. See docs/FSRS_FEASIBILITY.md.
"""
from domain.srs.srs_base import LEARNING, NEW, RELEARNING, REVIEW, CardState, Rating, SrsEngine
from domain.srs.sm2_engine import Sm2Engine

__all__ = [
    "CardState", "Rating", "SrsEngine",
    "NEW", "LEARNING", "REVIEW", "RELEARNING",
    "Sm2Engine",
]
