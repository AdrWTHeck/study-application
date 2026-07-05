"""Preview the next-review interval for each rating without scheduling anything.

The review screen shows a hint under each rating button ("<1m", "6m", "1d",
"4d") so the learner can see the consequence of each choice before making it
(learner-autonomy: informed choice, AUT). The preview runs the engine on a
detached :class:`CardState` copy — the card, the session, and the review log
are never touched.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from core.clock import now as clock_now
from data.models import Card
from domain.srs.mapping import card_to_state
from domain.srs.srs_base import Rating, SrsEngine

_MINUTE = 60
_HOUR = 3600
_DAY = 86400


def format_interval(delta: timedelta) -> str:
    """Compact human interval: "<1m", "6m", "2h", "1d", "4d", "3mo", "1y"."""
    seconds = delta.total_seconds()
    if seconds < _MINUTE:
        return "<1m"
    if seconds < _HOUR:
        return f"{round(seconds / _MINUTE)}m"
    if seconds < _DAY:
        return f"{round(seconds / _HOUR)}h"
    days = seconds / _DAY
    if days < 30:
        return f"{round(days)}d"
    if days < 365:
        return f"{round(days / 30)}mo"
    return f"{round(days / 365)}y"


def preview_intervals(
    engine: SrsEngine, card: Card, at: datetime | None = None
) -> dict[Rating, str]:
    """Return {rating: formatted interval} for all four ratings of *card*.

    Pure preview: ``engine.review`` operates on a fresh ``CardState`` built
    from the card (engines copy the state internally), so neither the card nor
    its scheduling is modified.
    """
    moment = at or clock_now()
    out: dict[Rating, str] = {}
    for rating in Rating:
        state = card_to_state(card)
        new_state = engine.review(state, rating, moment)
        due = new_state.due or moment
        out[rating] = format_interval(due - moment)
    return out
