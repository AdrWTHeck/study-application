"""SourceDocument and TextSegment repository — Phase 2."""
from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from models.source_document import SourceDocument, TextSegment
from repositories.base_repository import BaseRepository


class SourceRepository(BaseRepository[SourceDocument]):
    model_class = SourceDocument

    def get_with_decks(self, source_id: int) -> SourceDocument | None:
        return (
            self._session.query(SourceDocument)
            .options(joinedload(SourceDocument.decks))
            .filter(SourceDocument.id == source_id)
            .first()
        )

    def get_segments(
        self, source_id: int, page_number: int
    ) -> list[TextSegment]:
        return (
            self._session.query(TextSegment)
            .filter(
                TextSegment.source_document_id == source_id,
                TextSegment.page_number == page_number,
            )
            .order_by(TextSegment.segment_index.asc())
            .all()
        )

    def get_segment_count(self, source_id: int) -> int:
        return (
            self._session.query(TextSegment)
            .filter(TextSegment.source_document_id == source_id)
            .count()
        )

    def get_question_count(self, source_id: int) -> int:
        from models.question import Question
        segment_ids = [
            row[0]
            for row in self._session.query(TextSegment.id)
            .filter(TextSegment.source_document_id == source_id)
            .all()
        ]
        if not segment_ids:
            return 0
        return (
            self._session.query(Question)
            .filter(Question.source_segment_id.in_(segment_ids))
            .count()
        )
