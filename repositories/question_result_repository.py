"""QuestionResult repository — Phase 3."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from models.question_result import QuestionResult
from repositories.base_repository import BaseRepository


class QuestionResultRepository(BaseRepository[QuestionResult]):
    model_class = QuestionResult

    def create(
        self,
        session_id: int,
        question_id: int,
        user_answer: str | None,
        correct: bool,
        similarity_score: float | None,
        time_taken_seconds: float,
        presented_at: datetime,
    ) -> QuestionResult:
        result = QuestionResult(
            session_id=session_id,
            question_id=question_id,
            user_answer=user_answer,
            correct=correct,
            similarity_score=similarity_score,
            time_taken_seconds=time_taken_seconds,
            presented_at=presented_at,
        )
        return self.save(result)

    def get_by_session(self, session_id: int) -> list[QuestionResult]:
        return (
            self._session.query(QuestionResult)
            .filter(QuestionResult.session_id == session_id)
            .all()
        )

    def get_wrong_by_session(self, session_id: int) -> list[QuestionResult]:
        return (
            self._session.query(QuestionResult)
            .filter(
                QuestionResult.session_id == session_id,
                QuestionResult.correct.is_(False),
            )
            .all()
        )

    def get_avg_time(self, session_id: int) -> float:
        from sqlalchemy import func
        result = (
            self._session.query(func.avg(QuestionResult.time_taken_seconds))
            .filter(QuestionResult.session_id == session_id)
            .scalar()
        )
        return float(result) if result is not None else 0.0

    def get_deck_score(self, session_id: int, deck_id: int) -> float:
        """Score percentage for one deck within a comprehensive session."""
        from models.question import Question
        total = (
            self._session.query(QuestionResult)
            .join(Question, QuestionResult.question_id == Question.id)
            .filter(
                QuestionResult.session_id == session_id,
                Question.deck_id == deck_id,
            )
            .count()
        )
        if total == 0:
            return 0.0
        correct = (
            self._session.query(QuestionResult)
            .join(Question, QuestionResult.question_id == Question.id)
            .filter(
                QuestionResult.session_id == session_id,
                Question.deck_id == deck_id,
                QuestionResult.correct.is_(True),
            )
            .count()
        )
        return (correct / total) * 100.0
