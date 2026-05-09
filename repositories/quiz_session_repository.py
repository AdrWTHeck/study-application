"""QuizSession repository."""
from __future__ import annotations

from sqlalchemy.orm import Session

from models.quiz_session import QuizSession
from repositories.base_repository import BaseRepository


class QuizSessionRepository(BaseRepository[QuizSession]):
    model_class = QuizSession

    def get_in_progress(self) -> list[QuizSession]:
        """Return all sessions with status='in_progress'; called at launch."""
        return (
            self._session.query(QuizSession)
            .filter(QuizSession.status == "in_progress")
            .all()
        )

    def get_in_progress_for_deck(self, deck_id: int) -> QuizSession | None:
        """One-session-per-deck guard (CON-14)."""
        return (
            self._session.query(QuizSession)
            .filter(
                QuizSession.deck_id == deck_id,
                QuizSession.status == "in_progress",
            )
            .first()
        )

    def write_checkpoint(
        self,
        session_id: int,
        remaining_ids: list[int],
        items_reviewed: int,
    ) -> None:
        """Atomic checkpoint write after each rated item (FR-INF-05)."""
        self._session.query(QuizSession).filter(
            QuizSession.id == session_id
        ).update(
            {
                QuizSession.remaining_item_ids: remaining_ids,
                QuizSession.items_reviewed: items_reviewed,
            }
        )
        self._session.flush()
