"""Achievement evaluation and unlocked-state persistence.

Definitions live in :mod:`domain.achievements.definitions`. The service gathers a
single metrics snapshot, unlocks any newly satisfied achievements, and exposes a
rich per-achievement state (symbol, category, hidden, rarity, progress) for the
tile grid.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from data.models import Achievement, Deck, Note, Question, ReviewLog
from data.models.companion import CompanionState
from data.models.source import Bookmark, SourceDocument
from data.models.testing import QuestionResult, QuizSession
from domain.achievements.definitions import (
    DEFINITIONS,
    AchievementMetrics,
)
from domain.dashboard.stats_service import StatsService


@dataclass
class AchievementState:
    code: str
    title: str
    symbol: str
    description: str
    category: str
    rarity: str
    hidden: bool
    unlocked_at: datetime | None
    progress: str | None = None
    fraction: float = 0.0

    @property
    def is_unlocked(self) -> bool:
        return self.unlocked_at is not None

    @property
    def is_hidden_locked(self) -> bool:
        """A hidden achievement that hasn't been earned → show a mystery box."""
        return self.hidden and self.unlocked_at is None


class AchievementService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def gather_metrics(self) -> AchievementMetrics:
        companion = self.session.scalar(select(CompanionState))
        return AchievementMetrics(
            review_count=self._count(ReviewLog),
            deck_count=self.session.scalar(
                select(func.count()).select_from(Deck).where(Deck.deck_type == "card")
            ) or 0,
            note_count=self._count(Note),
            source_count=self._count(SourceDocument),
            highlight_count=0,  # annotations now live in PDF; counted separately
            bookmark_count=self._count(Bookmark),
            question_count=self._count(Question),
            quiz_count=self.session.scalar(
                select(func.count()).select_from(QuizSession)
                .where(QuizSession.status == "complete")
            ) or 0,
            perfect_quizzes=self._perfect_quizzes(),
            study_days=self._study_days(),
            streak=StatsService(self.session).streak(),
            companion_level=companion.level if companion is not None else 1,
        )

    def _perfect_quizzes(self) -> int:
        """Complete sessions where every answered question was correct (and >0)."""
        rows = self.session.execute(
            select(
                QuestionResult.session_id,
                func.count().label("total"),
                func.sum(QuestionResult.is_correct).label("correct"),
            ).group_by(QuestionResult.session_id)
        ).all()
        perfect = 0
        for _sid, total, correct in rows:
            if total and (correct or 0) == total:
                perfect += 1
        return perfect

    def _study_days(self) -> int:
        days: set = set()
        for (reviewed_at,) in self.session.execute(select(ReviewLog.reviewed_at)).all():
            if reviewed_at:
                days.add(reviewed_at.date())
        for (started_at,) in self.session.execute(select(QuizSession.started_at)).all():
            if started_at:
                days.add(started_at.date())
        return len(days)

    def list_achievements(self) -> list[AchievementState]:
        metrics = self.gather_metrics()
        unlocked = {
            a.code: a.unlocked_at for a in self.session.scalars(select(Achievement)).all()
        }
        states: list[AchievementState] = []
        for d in DEFINITIONS:
            at = unlocked.get(d.code)
            states.append(AchievementState(
                code=d.code, title=d.title, symbol=d.symbol, description=d.description,
                category=d.category, rarity=d.rarity, hidden=d.hidden, unlocked_at=at,
                progress=None if at is not None else d.progress_text(metrics),
                fraction=1.0 if at is not None else d.fraction(metrics),
            ))
        return states

    def evaluate(self) -> list[str]:
        """Unlock any newly satisfied achievements. Returns the codes unlocked now."""
        metrics = self.gather_metrics()
        already = {a.code for a in self.session.scalars(select(Achievement)).all()}
        newly: list[str] = []
        for d in DEFINITIONS:
            if d.code not in already and d.is_unlocked(metrics):
                self._unlock(d.code)
                newly.append(d.code)
        return newly

    # -- internal ----------------------------------------------------------

    def _count(self, model) -> int:
        return self.session.scalar(select(func.count()).select_from(model)) or 0

    def _unlock(self, code: str) -> Achievement:
        achievement = self.session.scalar(select(Achievement).where(Achievement.code == code))
        if achievement is None:
            achievement = Achievement(code=code)
            self.session.add(achievement)
            self.session.flush()
        return achievement
