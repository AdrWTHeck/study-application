"""Card repository."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.card import Card
from repositories.base_repository import BaseRepository


class CardRepository(BaseRepository[Card]):
    model_class = Card

    # --- SRS queue queries ----------------------------------------------

    def get_by_deck(self, deck_id: int) -> list[Card]:
        return (
            self._session.query(Card)
            .filter(Card.deck_id == deck_id)
            .all()
        )

    def get_due_review(self, deck_id: int) -> list[Card]:
        """Review cards with next_review_date <= today, ordered ASC."""
        return (
            self._session.query(Card)
            .filter(
                Card.deck_id == deck_id,
                Card.category == "review",
                Card.next_review_date <= date.today(),
            )
            .order_by(Card.next_review_date.asc())
            .all()
        )

    def get_due_learning(self, deck_id: int) -> list[Card]:
        """Learning cards with next_review_date <= today, ordered ASC."""
        return (
            self._session.query(Card)
            .filter(
                Card.deck_id == deck_id,
                Card.category == "learning",
                Card.next_review_date <= date.today(),
            )
            .order_by(Card.next_review_date.asc())
            .all()
        )

    def get_new(self, deck_id: int, limit: int) -> list[Card]:
        """New cards ordered by created_at ASC, capped at limit."""
        return (
            self._session.query(Card)
            .filter(Card.deck_id == deck_id, Card.category == "new")
            .order_by(Card.created_at.asc())
            .limit(limit)
            .all()
        )

    # --- Orphan-audio cleanup ------------------------------------------

    def all_audio_paths(self) -> set[str]:
        """Return all non-null audio_path values stored in the DB."""
        rows = (
            self._session.query(Card.audio_path)
            .filter(Card.audio_path.isnot(None))
            .all()
        )
        return {row[0] for row in rows}

    # --- Deck management -----------------------------------------------

    def reassign_deck(self, old_deck_id: int, new_deck_id: int) -> None:
        """Bulk-update deck_id when the original deck is deleted."""
        self._session.query(Card).filter(
            Card.deck_id == old_deck_id
        ).update({Card.deck_id: new_deck_id})
        self._session.flush()
