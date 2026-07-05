"""Build a temporary cram queue that does not persist scheduling changes."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from data.models import Card, Note


class CramService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def build_queue(self, deck_id: int) -> list[Card]:
        return self.session.scalars(
            select(Card)
            .where(Card.deck_id == deck_id)
            .options(
                joinedload(Card.note).joinedload(Note.field_values),
                joinedload(Card.note).joinedload(Note.note_type),
                joinedload(Card.template),
            )
            .order_by(Card.created_at, Card.id)
        ).unique().all()

    def build_queue_multi(self, deck_ids: list[int]) -> list[Card]:
        """Cram queue spanning multiple decks (e.g. reviewing a parent folder)."""
        if not deck_ids:
            return []
        if len(deck_ids) == 1:
            return self.build_queue(deck_ids[0])
        return self.session.scalars(
            select(Card)
            .where(Card.deck_id.in_(deck_ids))
            .options(
                joinedload(Card.note).joinedload(Note.field_values),
                joinedload(Card.note).joinedload(Note.note_type),
                joinedload(Card.template),
            )
            .order_by(Card.created_at, Card.id)
        ).unique().all()
