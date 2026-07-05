"""Spaced-repetition scheduling.

FSRS is the only scheduler. It operates on a decoupled :class:`CardState` behind
the :class:`SrsEngine` interface, so the models and UI never depend on a specific
engine. See docs/FSRS_FEASIBILITY.md.
"""
from domain.srs.srs_base import LEARNING, NEW, RELEARNING, REVIEW, CardState, Rating, SrsEngine
from domain.srs.fsrs_engine import FsrsEngine

# Engine registry keyed by the value stored in settings["scheduler"].
ENGINES = {"fsrs": FsrsEngine}
DEFAULT_SCHEDULER = "fsrs"


def make_engine(name: str | None = None) -> SrsEngine:
    """Construct the SRS engine for the given settings value.

    FSRS is the only engine; an unknown/legacy value (e.g. a stale ``"sm2"`` in a
    user's settings.json) falls back to FSRS rather than crashing.
    """
    return ENGINES.get(name or DEFAULT_SCHEDULER, FsrsEngine)()


__all__ = [
    "CardState", "Rating", "SrsEngine",
    "NEW", "LEARNING", "REVIEW", "RELEARNING",
    "FsrsEngine",
    "ENGINES", "DEFAULT_SCHEDULER", "make_engine",
]
