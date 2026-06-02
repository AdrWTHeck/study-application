"""Deck CRUD service — create, rename, delete, list."""
from __future__ import annotations

import logging

from models.base import get_session
from models.deck import Deck
from repositories.card_repository import CardRepository
from repositories.deck_repository import DeckRepository
from repositories.question_repository import QuestionRepository

logger = logging.getLogger(__name__)


class DeckService:
    """Thin service layer over DeckRepository.

    Enforces the invariants:
    - Deck names are unique within a deck_type.
    - Default decks cannot be deleted.
    - Deleting a deck reassigns its cards/questions to the default deck of
      the same type before removal.
    """

    def create(self, name: str, deck_type: str) -> Deck | None:
        db = get_session()
        try:
            repo = DeckRepository(db)
            if repo.name_exists(name, deck_type):
                logger.warning("Deck %r (%s) already exists.", name, deck_type)
                return None
            deck = Deck(name=name, deck_type=deck_type, is_default=False)
            repo.save(deck)
            db.commit()
            db.refresh(deck)
            return deck
        except Exception:
            db.rollback()
            logger.exception("Failed to create deck %r.", name)
            return None
        finally:
            db.close()

    def rename(self, deck_id: int, new_name: str) -> bool:
        db = get_session()
        try:
            repo = DeckRepository(db)
            deck = repo.get(deck_id)
            if deck is None:
                return False
            if repo.name_exists(new_name, deck.deck_type):
                logger.warning("Deck name %r already in use.", new_name)
                return False
            deck.name = new_name
            db.commit()
            return True
        except Exception:
            db.rollback()
            logger.exception("Failed to rename deck %d.", deck_id)
            return False
        finally:
            db.close()

    def delete(self, deck_id: int) -> bool:
        """Delete a non-default deck; reassigns its items to the default deck."""
        db = get_session()
        try:
            deck_repo = DeckRepository(db)
            deck = deck_repo.get(deck_id)
            if deck is None:
                return False
            if deck.is_default:
                logger.warning("Cannot delete the default deck (id=%d).", deck_id)
                return False
            default = deck_repo.get_default(deck.deck_type)
            if default is None:
                logger.error(
                    "No default deck of type %r — refusing to delete deck %d.",
                    deck.deck_type, deck_id,
                )
                return False

            if deck.deck_type == "card":
                CardRepository(db).reassign_deck(deck_id, default.id)
            else:
                QuestionRepository(db).reassign_deck(deck_id, default.id)

            deck_repo.delete(deck)
            db.commit()
            return True
        except Exception:
            db.rollback()
            logger.exception("Failed to delete deck %d.", deck_id)
            return False
        finally:
            db.close()

    def get_all(self, deck_type: str) -> list[Deck]:
        db = get_session()
        try:
            return DeckRepository(db).get_by_type(deck_type)
        finally:
            db.close()

    def get(self, deck_id: int) -> Deck | None:
        db = get_session()
        try:
            return DeckRepository(db).get(deck_id)
        finally:
            db.close()
