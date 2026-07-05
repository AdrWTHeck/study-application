from __future__ import annotations

from sqlalchemy import func, select

from data.models import Question
from data.repositories.base_repository import BaseRepository


class QuestionRepository(BaseRepository[Question]):
    model = Question

    def for_deck(self, deck_id: int) -> list[Question]:
        return list(
            self.session.scalars(
                select(Question).where(Question.deck_id == deck_id).order_by(Question.id)
            )
        )

    def count_for_deck(self, deck_id: int) -> int:
        return self.session.scalar(
            select(func.count()).select_from(Question).where(Question.deck_id == deck_id)
        ) or 0
