"""Question repository — Phase 3."""
from __future__ import annotations

import random

from sqlalchemy.orm import Session

from models.question import Question
from repositories.base_repository import BaseRepository


class QuestionRepository(BaseRepository[Question]):
    model_class = Question

    def get_by_deck(self, deck_id: int) -> list[Question]:
        return (
            self._session.query(Question)
            .filter(Question.deck_id == deck_id)
            .all()
        )

    def get_by_source(self, source_id: int) -> list[Question]:
        return (
            self._session.query(Question)
            .filter(Question.source_segment_id == source_id)
            .all()
        )

    def get_by_scope(
        self, deck_id: int | None, source_id: int | None, scope_type: str
    ) -> list[Question]:
        q = self._session.query(Question)
        if scope_type == "deck" and deck_id is not None:
            q = q.filter(Question.deck_id == deck_id)
        elif scope_type == "document" and source_id is not None:
            from models.source_document import TextSegment
            segment_ids = [
                row[0]
                for row in self._session.query(TextSegment.id)
                .filter(TextSegment.source_document_id == source_id)
                .all()
            ]
            q = q.filter(Question.source_segment_id.in_(segment_ids))
        elif scope_type == "combined" and deck_id is not None and source_id is not None:
            from models.source_document import TextSegment
            segment_ids = [
                row[0]
                for row in self._session.query(TextSegment.id)
                .filter(TextSegment.source_document_id == source_id)
                .all()
            ]
            q = q.filter(
                (Question.deck_id == deck_id)
                | Question.source_segment_id.in_(segment_ids)
            )
        return q.all()

    def get_random_sample(self, deck_id: int, count: int) -> list[Question]:
        all_questions = self.get_by_deck(deck_id)
        return random.sample(all_questions, min(count, len(all_questions)))

    def reassign_deck(self, old_deck_id: int, new_deck_id: int) -> None:
        self._session.query(Question).filter(
            Question.deck_id == old_deck_id
        ).update({Question.deck_id: new_deck_id})
        self._session.flush()
