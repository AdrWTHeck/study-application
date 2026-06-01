"""Card CRUD, promote-to-question, and SRS queue helpers."""
from __future__ import annotations

import logging

from config.constants import NEW_CARDS_PER_SESSION
from models.base import get_session
from models.card import Card
from models.question import Question
from repositories.card_repository import CardRepository
from repositories.deck_repository import DeckRepository
from repositories.question_repository import QuestionRepository

logger = logging.getLogger(__name__)

_EDITABLE_FIELDS = frozenset({"front_text", "back_text", "audio_path"})


class CardService:
    """All card mutations open their own DB session and commit/rollback atomically."""

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(
        self,
        front: str,
        back: str,
        deck_id: int,
        audio_path: str | None = None,
    ) -> Card | None:
        db = get_session()
        try:
            card = Card(
                deck_id=deck_id,
                front_text=front,
                back_text=back,
                audio_path=audio_path,
            )
            CardRepository(db).save(card)
            db.commit()
            db.refresh(card)
            return card
        except Exception:
            db.rollback()
            logger.exception("Failed to create card in deck %d.", deck_id)
            return None
        finally:
            db.close()

    def edit(self, card_id: int, **fields) -> bool:
        db = get_session()
        try:
            card = CardRepository(db).get(card_id)
            if card is None:
                return False
            for key, val in fields.items():
                if key in _EDITABLE_FIELDS:
                    setattr(card, key, val)
            db.commit()
            return True
        except Exception:
            db.rollback()
            logger.exception("Failed to edit card %d.", card_id)
            return False
        finally:
            db.close()

    def delete(self, card_id: int) -> bool:
        db = get_session()
        try:
            repo = CardRepository(db)
            card = repo.get(card_id)
            if card is None:
                return False
            repo.delete(card)
            db.commit()
            return True
        except Exception:
            db.rollback()
            logger.exception("Failed to delete card %d.", card_id)
            return False
        finally:
            db.close()

    def move(self, card_id: int, target_deck_id: int) -> bool:
        db = get_session()
        try:
            card = CardRepository(db).get(card_id)
            if card is None:
                return False
            card.deck_id = target_deck_id
            db.commit()
            return True
        except Exception:
            db.rollback()
            logger.exception(
                "Failed to move card %d to deck %d.", card_id, target_deck_id
            )
            return False
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Promote card → question
    # ------------------------------------------------------------------

    def promote_to_question(self, card_id: int) -> Question | None:
        """Create a short-answer Question from a Card's front/back text.

        The question is placed in the default test deck.  Returns None if
        the card is missing, has no content, or no default test deck exists.
        """
        db = get_session()
        try:
            card = CardRepository(db).get(card_id)
            if card is None or not card.front_text or not card.back_text:
                logger.warning(
                    "Card %d cannot be promoted: missing or empty content.", card_id
                )
                return None

            test_deck = DeckRepository(db).get_default("test")
            if test_deck is None:
                logger.error("No default test deck found; cannot promote card %d.", card_id)
                return None

            q = Question(
                deck_id=test_deck.id,
                source_segment_id=None,
                question_text=card.front_text,
                answer=card.back_text,
                type="short_answer",
                generator_type="manual",
                distractors=None,
            )
            QuestionRepository(db).save(q)
            db.commit()
            db.refresh(q)
            return q
        except Exception:
            db.rollback()
            logger.exception("Failed to promote card %d to question.", card_id)
            return None
        finally:
            db.close()

    # ------------------------------------------------------------------
    # SRS queue queries
    # ------------------------------------------------------------------

    def get_due_review(self, deck_id: int) -> list[Card]:
        db = get_session()
        try:
            return CardRepository(db).get_due_review(deck_id)
        finally:
            db.close()

    def get_due_learning(self, deck_id: int) -> list[Card]:
        db = get_session()
        try:
            return CardRepository(db).get_due_learning(deck_id)
        finally:
            db.close()

    def get_new(self, deck_id: int, limit: int = NEW_CARDS_PER_SESSION) -> list[Card]:
        db = get_session()
        try:
            return CardRepository(db).get_new(deck_id, limit)
        finally:
            db.close()
