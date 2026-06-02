"""Deck CRUD + the per-deck New/Learning/Review counts the browser/dashboard show."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.clock import now
from data.models import Deck, Tag
from data.repositories.card_repository import CardRepository
from data.repositories.deck_repository import DeckRepository


@dataclass
class DeckSummary:
    deck: Deck
    new: int
    learning: int
    review: int

    @property
    def total(self) -> int:
        return self.new + self.learning + self.review


class DeckService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.decks = DeckRepository(session)
        self.cards = CardRepository(session)

    def create(self, name: str, deck_type: str = "card",
               category: str | None = None, color: str | None = None) -> Deck:
        deck = Deck(name=name.strip(), deck_type=deck_type, category=category, color=color)
        return self.decks.add(deck)

    def rename(self, deck_id: int, name: str) -> Deck | None:
        deck = self.decks.get(deck_id)
        if deck is not None:
            deck.name = name.strip()
            deck.modified_at = now()
            self.session.flush()
        return deck

    def set_favorite(self, deck_id: int, favorite: bool) -> Deck | None:
        deck = self.decks.get(deck_id)
        if deck is not None:
            deck.is_favorite = favorite
            self.session.flush()
        return deck

    def set_category(self, deck_id: int, category: str | None) -> Deck | None:
        deck = self.decks.get(deck_id)
        if deck is not None:
            deck.category = category
            self.session.flush()
        return deck

    def set_color(self, deck_id: int, color: str | None) -> Deck | None:
        deck = self.decks.get(deck_id)
        if deck is not None:
            deck.color = color
            self.session.flush()
        return deck

    def set_tags(self, deck_id: int, names: list[str]) -> Deck | None:
        deck = self.decks.get(deck_id)
        if deck is not None:
            deck.tags = [self._get_or_create_tag(name) for name in names]
            self.session.flush()
        return deck

    def delete(self, deck_id: int) -> None:
        deck = self.decks.get(deck_id)
        if deck is not None:
            self.decks.delete(deck)

    def _get_or_create_tag(self, name: str) -> Tag:
        tag = self.session.scalar(select(Tag).where(Tag.name == name))
        if tag is None:
            tag = Tag(name=name)
            self.session.add(tag)
            self.session.flush()
        return tag

    def list_summaries(self, deck_type: str = "card") -> list[DeckSummary]:
        summaries = []
        for deck in self.decks.by_type(deck_type):
            counts = self.cards.state_counts(deck.id)
            summaries.append(
                DeckSummary(deck=deck, new=counts["new"],
                            learning=counts["learning"], review=counts["review"])
            )
        return summaries
