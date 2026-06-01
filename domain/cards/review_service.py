"""Build the review queue and apply ratings (engine + persist + log).

Queue = due learning/relearning/review cards first, then up to ``new_limit`` new
cards. Applying a rating runs the active SRS engine, writes the new state back to
the card, and appends a ReviewLog row (stats + future FSRS optimizer).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from core.clock import now
from data.models import Card, ReviewLog
from data.repositories.card_repository import CardRepository
from domain.srs.constants import NEW_CARDS_PER_SESSION_DEFAULT
from domain.srs.mapping import apply_state, card_to_state
from domain.srs.srs_base import Rating, SrsEngine


class ReviewService:
    def __init__(self, session: Session, engine: SrsEngine,
                 new_limit: int = NEW_CARDS_PER_SESSION_DEFAULT) -> None:
        self.session = session
        self.engine = engine
        self.new_limit = new_limit
        self.cards = CardRepository(session)

    def build_queue(self, deck_id: int, at: datetime | None = None) -> list[Card]:
        moment = at or now()
        due = self.cards.due_learning_review(deck_id, moment)
        new = self.cards.new_cards(deck_id, self.new_limit)
        return due + new

    def answer(self, card: Card, rating: Rating,
               at: datetime | None = None, elapsed_ms: int | None = None) -> Card:
        moment = at or now()
        prev = card_to_state(card)
        new = self.engine.review(prev, rating, moment)
        apply_state(card, new)
        self.session.add(
            ReviewLog(
                card_id=card.id,
                rating=int(rating),
                prev_state=prev.state,
                new_state=new.state,
                prev_interval=prev.interval_days,
                new_interval=new.interval_days,
                prev_ease=prev.ease_factor,
                new_ease=new.ease_factor,
                elapsed_ms=elapsed_ms,
            )
        )
        self.session.flush()
        return card
