"""Deck repository."""
from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from models.deck import Deck
from repositories.base_repository import BaseRepository


class DeckRepository(BaseRepository[Deck]):
    model_class = Deck

    def get_by_type(self, deck_type: str) -> list[Deck]:
        return (
            self._session.query(Deck)
            .filter(Deck.deck_type == deck_type)
            .all()
        )

    def get_default(self, deck_type: str) -> Deck | None:
        return (
            self._session.query(Deck)
            .filter(Deck.deck_type == deck_type, Deck.is_default.is_(True))
            .first()
        )

    def get_with_sources(self, deck_id: int) -> Deck | None:
        return (
            self._session.query(Deck)
            .options(joinedload(Deck.source_documents))
            .filter(Deck.id == deck_id)
            .first()
        )

    def name_exists(self, name: str, deck_type: str) -> bool:
        return (
            self._session.query(Deck)
            .filter(Deck.name == name, Deck.deck_type == deck_type)
            .count()
            > 0
        )
