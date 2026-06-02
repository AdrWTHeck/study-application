"""Card session controller — SM-2 queue with time-based re-queue."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime

from config.constants import NEW_CARDS_PER_SESSION
from models.base import get_session
from models.card import Card
from models.quiz_session import QuizSession
from repositories.card_repository import CardRepository
from repositories.quiz_session_repository import QuizSessionRepository
from services.srs import sm2_engine
from services.srs.srs_base import CardRating

logger = logging.getLogger(__name__)


@dataclass
class _SessionState:
    """In-memory state for one active card session."""
    consecutive_good: dict[int, int] = field(default_factory=dict)
    # (available_after monotonic timestamp, card_id)
    requeued: list[tuple[float, int]] = field(default_factory=list)


class CardSessionController:
    """Manages the full lifecycle of a card (flashcard) QuizSession.

    Queue order on start:
        1. Due review cards   (category="review",   next_review_date <= today)
        2. Due learning cards (category="learning", next_review_date <= today)
        3. New cards          (up to NEW_CARDS_PER_SESSION)

    Re-queue mechanic:
        Very Hard ratings append the card to an in-memory re-queue with a
        monotonic timestamp.  get_next_card() prefers cards whose wait has
        elapsed before drawing from the main queue.  If the user closes the
        app mid-session the in-memory state is lost; that is acceptable
        because the SM-2 engine already reset those cards to "new".

    A single controller instance may manage multiple simultaneous sessions
    (state is keyed by session_id).
    """

    def __init__(self) -> None:
        self._states: dict[int, _SessionState] = {}

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def start(self, deck_id: int) -> QuizSession | None:
        """Build and return a new in-progress card session.

        CON-14: if an in-progress card session already exists for this deck,
        that session is returned instead of creating a duplicate.
        Returns None when no cards are due and no new cards exist.
        """
        db = get_session()
        try:
            qs_repo = QuizSessionRepository(db)

            existing = qs_repo.get_in_progress_for_deck(deck_id)
            if existing and existing.session_type == "card":
                self._states.setdefault(existing.id, _SessionState())
                logger.info(
                    "Resuming existing card session %d for deck %d.",
                    existing.id, deck_id,
                )
                return existing

            card_repo = CardRepository(db)
            queue: list[int] = [
                c.id for c in card_repo.get_due_review(deck_id)
            ] + [
                c.id for c in card_repo.get_due_learning(deck_id)
            ] + [
                c.id for c in card_repo.get_new(deck_id, NEW_CARDS_PER_SESSION)
            ]

            if not queue:
                logger.info("No cards due for deck %d.", deck_id)
                return None

            quiz = QuizSession(
                deck_id=deck_id,
                source_document_id=None,
                scope_type="deck",
                session_type="card",
                status="in_progress",
                remaining_item_ids=queue,
                total_items=len(queue),
                items_reviewed=0,
            )
            qs_repo.save(quiz)
            db.commit()
            db.refresh(quiz)
            self._states[quiz.id] = _SessionState()
            return quiz
        except Exception:
            db.rollback()
            logger.exception("Failed to start card session for deck %d.", deck_id)
            return None
        finally:
            db.close()

    def resume(self, session_id: int) -> QuizSession | None:
        """Return the session if it exists and is still in_progress."""
        db = get_session()
        try:
            quiz = QuizSessionRepository(db).get(session_id)
            if quiz is None or quiz.status != "in_progress" or quiz.session_type != "card":
                return None
            self._states.setdefault(session_id, _SessionState())
            return quiz
        finally:
            db.close()

    def discard(self, session_id: int) -> None:
        """Mark the session as abandoned and drop its in-memory state."""
        db = get_session()
        try:
            quiz = QuizSessionRepository(db).get(session_id)
            if quiz and quiz.status == "in_progress":
                quiz.status = "abandoned"
                db.commit()
            self._states.pop(session_id, None)
        except Exception:
            db.rollback()
            logger.exception("Failed to discard card session %d.", session_id)
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Session flow
    # ------------------------------------------------------------------

    def get_next_card(self, session_id: int) -> Card | None:
        """Return the next Card to present without removing it from the queue.

        Re-queued cards whose wait time has elapsed are preferred; if none
        are ready, the front of remaining_item_ids is used.  Returns None
        when the session is complete (both queues empty).
        """
        db = get_session()
        try:
            quiz = QuizSessionRepository(db).get(session_id)
            if quiz is None or quiz.status != "in_progress":
                return None

            state = self._states.get(session_id, _SessionState())
            card_repo = CardRepository(db)
            now = time.monotonic()

            # Prefer a ready re-queued card
            ready = sorted(
                (t, cid) for t, cid in state.requeued if t <= now
            )
            if ready:
                return card_repo.get(ready[0][1])

            if quiz.remaining_item_ids:
                return card_repo.get(quiz.remaining_item_ids[0])

            # Main queue empty — return soonest re-queued card regardless of wait
            if state.requeued:
                state.requeued.sort()
                return card_repo.get(state.requeued[0][1])

            return None  # session truly complete
        finally:
            db.close()

    def submit_rating(
        self,
        session_id: int,
        card_id: int,
        rating: CardRating,
    ) -> bool:
        """Apply a CardRating to a card, persist the SM-2 update, and checkpoint.

        Returns False if the session or card cannot be found.
        Finalizes the session (status="complete") when both queues drain.
        """
        db = get_session()
        try:
            qs_repo = QuizSessionRepository(db)
            quiz = qs_repo.get(session_id)
            card = CardRepository(db).get(card_id)
            if quiz is None or card is None:
                return False

            state = self._states.setdefault(session_id, _SessionState())

            # Track consecutive Good count per card
            if rating == CardRating.GOOD:
                state.consecutive_good[card_id] = (
                    state.consecutive_good.get(card_id, 0) + 1
                )
            else:
                state.consecutive_good[card_id] = 0
            consec = state.consecutive_good[card_id]

            result = sm2_engine.update(card, rating, consec)
            db.flush()  # persist SRS field changes

            # Determine whether this card came from the re-queue
            requeue_entry = next(
                ((t, cid) for t, cid in state.requeued if cid == card_id),
                None,
            )
            now = time.monotonic()

            if requeue_entry is not None:
                state.requeued.remove(requeue_entry)
                items_reviewed = quiz.items_reviewed  # already counted before
                remaining = list(quiz.remaining_item_ids)
            else:
                remaining = [qid for qid in quiz.remaining_item_ids if qid != card_id]
                items_reviewed = quiz.items_reviewed + 1

            if result.should_requeue:
                available_at = now + result.requeue_minutes * 60
                state.requeued.append((available_at, card_id))
                state.consecutive_good[card_id] = 0

            qs_repo.write_checkpoint(session_id, remaining, items_reviewed)

            if not remaining and not state.requeued:
                quiz.status = "complete"
                quiz.completed_at = datetime.now()
                self._states.pop(session_id, None)
                logger.info("Card session %d complete (%d items reviewed).",
                            session_id, items_reviewed)

            db.commit()
            return True
        except Exception:
            db.rollback()
            logger.exception(
                "Failed to submit rating for session %d card %d.", session_id, card_id
            )
            return False
        finally:
            db.close()
