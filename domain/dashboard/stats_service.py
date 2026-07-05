"""Dashboard statistics.

Retention = SRS recall rate over *review-state* card reviews (Good/Easy counted
as recalled) — a cards-only signal. Tests are summarized separately by best
score + trend (mastery/improvement), never folded into retention.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.clock import now
from data.models import Card, Deck, ReviewLog, QuizSession, SourceDocument
from data.repositories.deck_repository import DeckRepository
from domain.srs.srs_base import LEARNING, NEW, RELEARNING, REVIEW
from domain.testing.quiz_service import QuizService

_RECALLED = 3  # rating >= 3 (Good/Easy) counts as a successful recall
_RETENTION_STATES = (REVIEW, RELEARNING)


@dataclass
class TestSummary:
    deck: str
    best: float
    last: float
    attempts: int
    trend: list[float] = field(default_factory=list)


class StatsService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # -- cards --------------------------------------------------------------

    def due_count(self, at: datetime | None = None) -> int:
        moment = at or now()
        return self.session.scalar(
            select(func.count()).select_from(Card).where(
                Card.srs_state.in_((LEARNING, RELEARNING, REVIEW)), Card.due <= moment
            )
        ) or 0

    def new_count(self) -> int:
        return self.session.scalar(
            select(func.count()).select_from(Card).where(Card.srs_state == NEW)
        ) or 0

    def card_state_distribution(self) -> dict[str, int]:
        """Count of cards per SRS state across all decks (New/Learning/Review)."""
        rows = self.session.execute(
            select(Card.srs_state, func.count()).group_by(Card.srs_state)
        ).all()
        counts = {NEW: 0, LEARNING: 0, REVIEW: 0, RELEARNING: 0}
        for state, count in rows:
            counts[state] = counts.get(state, 0) + count
        return counts

    def retention_rate(self) -> tuple[float | None, int]:
        """(% recalled, sample size) over review-state reviews. None if no data."""
        rows = self.session.execute(
            select(ReviewLog.rating).where(ReviewLog.prev_state.in_(_RETENTION_STATES))
        ).all()
        if not rows:
            return None, 0
        recalled = sum(1 for (rating,) in rows if rating >= _RECALLED)
        return round(100.0 * recalled / len(rows), 1), len(rows)

    # -- streak -------------------------------------------------------------

    def streak(self) -> int:
        days: set[date] = set()
        for (reviewed_at,) in self.session.execute(select(ReviewLog.reviewed_at)).all():
            if reviewed_at:
                days.add(reviewed_at.date())
        for (started_at,) in self.session.execute(select(QuizSession.started_at)).all():
            if started_at:
                days.add(started_at.date())
        if not days:
            return 0
        today = now().date()
        if today in days:
            cursor = today
        elif (today - timedelta(days=1)) in days:
            cursor = today - timedelta(days=1)
        else:
            return 0  # most recent activity is older than yesterday → streak broken
        count = 0
        while cursor in days:
            count += 1
            cursor -= timedelta(days=1)
        return count

    # -- tests --------------------------------------------------------------

    def test_summaries(self) -> list[TestSummary]:
        quiz = QuizService(self.session)
        summaries: list[TestSummary] = []
        for deck in DeckRepository(self.session).by_type("test"):
            history = quiz.history(deck.id)
            if not history:
                continue
            scores = [score for _sid, _finished, score in history]
            summaries.append(
                TestSummary(deck=deck.name, best=max(scores), last=scores[-1],
                            attempts=len(scores), trend=scores[-6:])
            )
        return summaries

    # -- quick actions ------------------------------------------------------

    def last_source(self) -> SourceDocument | None:
        return self.session.scalar(
            select(SourceDocument)
            .where(SourceDocument.last_opened_at.is_not(None))
            .order_by(SourceDocument.last_opened_at.desc())
        )
