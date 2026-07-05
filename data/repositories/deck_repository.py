from __future__ import annotations

from sqlalchemy import select

from data.models import Deck
from data.repositories.base_repository import BaseRepository


class DeckRepository(BaseRepository[Deck]):
    model = Deck

    def by_type(self, deck_type: str = "card") -> list[Deck]:
        return list(
            self.session.scalars(
                select(Deck)
                .where(Deck.deck_type == deck_type)
                .order_by(Deck.is_favorite.desc(), Deck.name)
            )
        )

    def default(self, deck_type: str = "card") -> Deck | None:
        return self.session.scalar(
            select(Deck).where(Deck.deck_type == deck_type, Deck.is_default.is_(True))
        )

    def by_name_prefix(self, prefix: str, deck_type: str = "card") -> list[Deck]:
        """Return all decks whose name equals *prefix* or starts with *prefix*+'::'."""
        from domain.decks.hierarchy import SEP
        return list(
            self.session.scalars(
                select(Deck)
                .where(
                    Deck.deck_type == deck_type,
                    (Deck.name == prefix) | Deck.name.startswith(prefix + SEP),
                )
                .order_by(Deck.name)
            )
        )
