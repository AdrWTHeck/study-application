"""Test session state machine — FR-5-07 through FR-5-10."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from rapidfuzz import fuzz

from config.constants import FUZZY_ACCEPT_THRESHOLD, COMPREHENSIVE_TEST_MAX_QUESTIONS
from models.base import get_session
from models.question import Question
from models.quiz_session import QuizSession
from repositories.question_repository import QuestionRepository
from repositories.question_result_repository import QuestionResultRepository
from repositories.quiz_session_repository import QuizSessionRepository
from services.quiz.quiz_builder import QuizBuilder

logger = logging.getLogger(__name__)


@dataclass
class AnswerResult:
    correct: bool
    similarity_score: float | None   # None for MCQ; 0–100 for fuzzy types
    is_complete: bool                # True when session has no remaining questions


class TestSessionController:
    """Manages the full lifecycle of a test QuizSession.

    DB sessions are opened per method call and always closed in finally.
    The caller identifies sessions and questions by integer ID; ORM objects
    are never returned as live sessions (they become detached on close).
    """

    def __init__(self) -> None:
        self._builder = QuizBuilder()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def start(
        self,
        deck_ids: list[int],
        total_count: int,
        scope_type: str,
    ) -> QuizSession | None:
        """Create and return a new in-progress QuizSession.

        CON-14: if a single-deck session is requested and one already exists
        in_progress for that deck, the existing session is returned.
        """
        db = get_session()
        try:
            qs_repo = QuizSessionRepository(db)

            if len(deck_ids) == 1 and scope_type != "comprehensive":
                existing = qs_repo.get_in_progress_for_deck(deck_ids[0])
                if existing:
                    logger.info(
                        "Returning existing in-progress session %d for deck %d.",
                        existing.id, deck_ids[0],
                    )
                    return existing

            capped = min(total_count, COMPREHENSIVE_TEST_MAX_QUESTIONS)

            if scope_type == "comprehensive":
                quiz = self._builder.build_comprehensive(db, deck_ids, capped)
            else:
                deck_id = deck_ids[0] if deck_ids else None
                quiz = self._builder.build(db, scope_type, deck_id, None, capped)

            db.commit()
            db.refresh(quiz)
            return quiz
        except ValueError as exc:
            db.rollback()
            logger.warning("Cannot start session: %s", exc)
            return None
        except Exception:
            db.rollback()
            logger.exception("Failed to start test session.")
            return None
        finally:
            db.close()

    def resume(self, session_id: int) -> QuizSession | None:
        """Return the QuizSession if it exists and is still in_progress."""
        db = get_session()
        try:
            quiz = QuizSessionRepository(db).get(session_id)
            if quiz is None or quiz.status != "in_progress":
                return None
            return quiz
        finally:
            db.close()

    def discard(self, session_id: int) -> None:
        """Mark a session as abandoned."""
        db = get_session()
        try:
            quiz = QuizSessionRepository(db).get(session_id)
            if quiz and quiz.status == "in_progress":
                quiz.status = "abandoned"
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to discard session %d.", session_id)
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Session flow
    # ------------------------------------------------------------------

    def get_next_question(self, session_id: int) -> Question | None:
        """Return the next Question without removing it from remaining_item_ids.

        The caller presents this question; the ID is later passed to
        submit_answer which removes it and checkpoints.
        """
        db = get_session()
        try:
            quiz = QuizSessionRepository(db).get(session_id)
            if quiz is None or quiz.status != "in_progress":
                return None
            if not quiz.remaining_item_ids:
                return None
            return QuestionRepository(db).get(quiz.remaining_item_ids[0])
        finally:
            db.close()

    def submit_answer(
        self,
        session_id: int,
        question_id: int,
        user_answer: str,
        presented_at: datetime,
    ) -> AnswerResult | None:
        """Evaluate answer, persist QuestionResult, checkpoint the session.

        Finalizes (status="complete", analytics) when no questions remain.
        """
        db = get_session()
        try:
            qs_repo = QuizSessionRepository(db)
            q_repo = QuestionRepository(db)
            result_repo = QuestionResultRepository(db)

            quiz = qs_repo.get(session_id)
            question = q_repo.get(question_id)
            if quiz is None or question is None:
                return None

            correct, similarity = self._evaluate(question, user_answer)
            time_taken = max(0.0, (datetime.now() - presented_at).total_seconds())

            result_repo.create(
                session_id=session_id,
                question_id=question_id,
                user_answer=user_answer,
                correct=correct,
                similarity_score=similarity,
                time_taken_seconds=time_taken,
                presented_at=presented_at,
            )

            remaining = [qid for qid in quiz.remaining_item_ids
                         if qid != question_id]
            items_reviewed = quiz.items_reviewed + 1
            qs_repo.write_checkpoint(session_id, remaining, items_reviewed)

            is_complete = len(remaining) == 0
            if is_complete:
                self._finalize(db, quiz, session_id, result_repo)

            db.commit()
            return AnswerResult(
                correct=correct,
                similarity_score=similarity,
                is_complete=is_complete,
            )
        except Exception:
            db.rollback()
            logger.exception(
                "Failed to submit answer for session %d question %d.",
                session_id, question_id,
            )
            return None
        finally:
            db.close()

    def get_results(self, session_id: int) -> dict | None:
        """Return a summary dict for a completed session."""
        db = get_session()
        try:
            quiz = QuizSessionRepository(db).get(session_id)
            if quiz is None:
                return None
            result_repo = QuestionResultRepository(db)
            results = result_repo.get_by_session(session_id)
            return {
                "session_id": session_id,
                "scope_type": quiz.scope_type,
                "score": quiz.score,
                "total_items": quiz.total_items,
                "items_reviewed": quiz.items_reviewed,
                "total_time_seconds": quiz.total_time_seconds,
                "avg_time_per_question": quiz.avg_time_per_question,
                "wrong_question_ids": quiz.wrong_question_ids or [],
                "deck_scores": quiz.deck_scores,
                "results": results,
            }
        finally:
            db.close()

    def start_drill_down(self, session_id: int) -> QuizSession | None:
        """Create a new session from the wrong answers of a completed session."""
        db = get_session()
        try:
            qs_repo = QuizSessionRepository(db)
            source = qs_repo.get(session_id)
            if source is None or not source.wrong_question_ids:
                return None

            wrong_ids = list(source.wrong_question_ids)
            drill = QuizSession(
                deck_id=source.deck_id,
                source_document_id=source.source_document_id,
                scope_type=source.scope_type,
                session_type="test",
                status="in_progress",
                remaining_item_ids=wrong_ids,
                total_items=len(wrong_ids),
                items_reviewed=0,
            )
            qs_repo.save(drill)
            db.commit()
            db.refresh(drill)
            return drill
        except Exception:
            db.rollback()
            logger.exception(
                "Failed to start drill-down from session %d.", session_id
            )
            return None
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Answer evaluation
    # ------------------------------------------------------------------

    @staticmethod
    def _evaluate(question: Question, user_answer: str) -> tuple[bool, float | None]:
        if not question.answer:
            return False, None
        if question.type == "mcq":
            correct = (
                user_answer.strip().lower() == question.answer.strip().lower()
            )
            return correct, None
        # fill_blank and short_answer — fuzzy match
        score = fuzz.WRatio(user_answer.strip(), question.answer.strip())
        return score >= FUZZY_ACCEPT_THRESHOLD, float(score)

    # ------------------------------------------------------------------
    # Session finalization
    # ------------------------------------------------------------------

    @staticmethod
    def _finalize(
        db,
        quiz: QuizSession,
        session_id: int,
        result_repo: QuestionResultRepository,
    ) -> None:
        results = result_repo.get_by_session(session_id)
        total = quiz.total_items or 1
        correct_count = sum(1 for r in results if r.correct)
        total_time = sum(r.time_taken_seconds for r in results)
        avg_time = total_time / len(results) if results else 0.0
        wrong_ids = [r.question_id for r in results if not r.correct]

        deck_scores: dict | None = None
        if quiz.scope_type == "comprehensive":
            deck_map: dict[int, list] = {}
            for r in results:
                q = db.get(Question, r.question_id)
                if q:
                    deck_map.setdefault(q.deck_id, []).append(r)
            deck_scores = {
                str(did): round(
                    sum(1 for r in rs if r.correct) / len(rs) * 100, 1
                )
                for did, rs in deck_map.items() if rs
            }

        quiz.status = "complete"
        quiz.completed_at = datetime.now()
        quiz.score = round(correct_count / total * 100, 1)
        quiz.total_time_seconds = round(total_time, 2)
        quiz.avg_time_per_question = round(avg_time, 2)
        quiz.wrong_question_ids = wrong_ids
        quiz.deck_scores = deck_scores
