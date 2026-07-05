from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from data.models import Card
from data.repositories.base_repository import BaseRepository
from domain.srs.srs_base import LEARNING, NEW, RELEARNING, REVIEW

# Map raw SRS states to the three UI buckets (New / Learning / Review).
_ACTIVE_LEARNING = (LEARNING, RELEARNING)


class CardRepository(BaseRepository[Card]):
    model = Card

    def for_deck(self, deck_id: int) -> list[Card]:
        return list(self.session.scalars(select(Card).where(Card.deck_id == deck_id)))

    def new_cards(self, deck_id: int, limit: int) -> list[Card]:
        return list(
            self.session.scalars(
                select(Card)
                .where(Card.deck_id == deck_id, Card.srs_state == NEW)
                .order_by(Card.created_at, Card.id)
                .limit(limit)
            )
        )

    def due_learning_review(self, deck_id: int, now: datetime) -> list[Card]:
        return list(
            self.session.scalars(
                select(Card)
                .where(
                    Card.deck_id == deck_id,
                    Card.srs_state.in_((LEARNING, RELEARNING, REVIEW)),
                    Card.due <= now,
                )
                .order_by(Card.due)
            )
        )

    def state_counts(self, deck_id: int) -> dict[str, int]:
        rows = self.session.execute(
            select(Card.srs_state, func.count())
            .where(Card.deck_id == deck_id)
            .group_by(Card.srs_state)
        )
        raw = {state: count for state, count in rows}
        return {
            "new": raw.get(NEW, 0),
            "learning": sum(raw.get(s, 0) for s in _ACTIVE_LEARNING),
            "review": raw.get(REVIEW, 0),
        }

    # ── Multi-deck variants (for parent-node/subtree review) ──────────────────

    def new_cards_multi(self, deck_ids: list[int], limit: int) -> list[Card]:
        if not deck_ids:
            return []
        return list(
            self.session.scalars(
                select(Card)
                .where(Card.deck_id.in_(deck_ids), Card.srs_state == NEW)
                .order_by(Card.created_at, Card.id)
                .limit(limit)
            )
        )

    def due_learning_review_multi(self, deck_ids: list[int], now: datetime) -> list[Card]:
        if not deck_ids:
            return []
        return list(
            self.session.scalars(
                select(Card)
                .where(
                    Card.deck_id.in_(deck_ids),
                    Card.srs_state.in_((LEARNING, RELEARNING, REVIEW)),
                    Card.due <= now,
                )
                .order_by(Card.due)
            )
        )

    def state_counts_multi(self, deck_ids: list[int]) -> dict[str, int]:
        if not deck_ids:
            return {"new": 0, "learning": 0, "review": 0}
        rows = self.session.execute(
            select(Card.srs_state, func.count())
            .where(Card.deck_id.in_(deck_ids))
            .group_by(Card.srs_state)
        )
        raw = {state: count for state, count in rows}
        return {
            "new": raw.get(NEW, 0),
            "learning": sum(raw.get(s, 0) for s in _ACTIVE_LEARNING),
            "review": raw.get(REVIEW, 0),
        }

    def all_cards_multi(self, deck_ids: list[int]) -> list[Card]:
        """All cards across multiple decks (for cram mode on a parent node)."""
        if not deck_ids:
            return []
        return list(
            self.session.scalars(
                select(Card)
                .where(Card.deck_id.in_(deck_ids))
                .options(
                    joinedload(Card.note),
                    joinedload(Card.template),
                )
                .order_by(Card.created_at, Card.id)
            )
        )
