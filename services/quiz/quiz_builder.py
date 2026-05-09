"""Quiz session assembly — selects questions and creates a QuizSession row."""
from __future__ import annotations

import logging
import random

from config.constants import COMPREHENSIVE_TEST_MAX_QUESTIONS
from models.quiz_session import QuizSession
from repositories.question_repository import QuestionRepository
from repositories.quiz_session_repository import QuizSessionRepository

logger = logging.getLogger(__name__)


class QuizBuilder:
    """Assembles QuizSessions from available Question rows.

    Callers pass an open SQLAlchemy session; QuizBuilder does not open or
    close sessions itself.
    """

    def build(
        self,
        db_session,
        scope_type: str,
        deck_id: int | None,
        source_id: int | None,
        total_count: int,
        distribution: dict[str, float] | None = None,
    ) -> QuizSession:
        """Build a scoped test session.

        scope_type: "deck" | "document" | "combined"
        distribution: optional {type: fraction} e.g. {"fill_blank": 0.5, "mcq": 0.3, ...}
        Raises ValueError if no questions are available.
        """
        q_repo = QuestionRepository(db_session)
        qs_repo = QuizSessionRepository(db_session)

        candidates = q_repo.get_by_scope(deck_id, source_id, scope_type)
        if not candidates:
            raise ValueError(
                f"No questions available for scope_type={scope_type!r} "
                f"deck_id={deck_id} source_id={source_id}"
            )

        selected = self._sample(candidates, total_count, distribution)
        random.shuffle(selected)

        quiz = QuizSession(
            deck_id=deck_id,
            source_document_id=source_id,
            scope_type=scope_type,
            session_type="test",
            status="in_progress",
            remaining_item_ids=[q.id for q in selected],
            total_items=len(selected),
            items_reviewed=0,
        )
        return qs_repo.save(quiz)

    def build_comprehensive(
        self,
        db_session,
        deck_ids: list[int],
        total_count: int,
    ) -> QuizSession:
        """Build a comprehensive session drawing proportionally from multiple decks.

        Raises ValueError if no questions are available across all decks.
        """
        q_repo = QuestionRepository(db_session)
        qs_repo = QuizSessionRepository(db_session)

        capped = min(total_count, COMPREHENSIVE_TEST_MAX_QUESTIONS)
        per_deck = max(1, capped // len(deck_ids))

        selected: list = []
        for deck_id in deck_ids:
            deck_qs = q_repo.get_random_sample(deck_id, per_deck)
            selected.extend(deck_qs)

        if not selected:
            raise ValueError(
                f"No questions found across decks {deck_ids}."
            )

        if len(selected) > capped:
            selected = random.sample(selected, capped)
        random.shuffle(selected)

        quiz = QuizSession(
            deck_id=None,
            source_document_id=None,
            scope_type="comprehensive",
            session_type="test",
            status="in_progress",
            remaining_item_ids=[q.id for q in selected],
            total_items=len(selected),
            items_reviewed=0,
        )
        return qs_repo.save(quiz)

    # ------------------------------------------------------------------
    # Sampling helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sample(
        questions: list,
        count: int,
        distribution: dict[str, float] | None,
    ) -> list:
        if not distribution:
            return random.sample(questions, min(count, len(questions)))

        by_type: dict[str, list] = {}
        for q in questions:
            by_type.setdefault(q.type, []).append(q)

        selected: list = []
        for q_type, fraction in distribution.items():
            target = max(1, round(count * fraction))
            pool = by_type.get(q_type, [])
            selected.extend(random.sample(pool, min(target, len(pool))))

        # Top up with any remaining questions if under-sampled
        chosen_ids = {id(q) for q in selected}
        extras = [q for q in questions if id(q) not in chosen_ids]
        if len(selected) < count and extras:
            selected.extend(
                random.sample(extras, min(count - len(selected), len(extras)))
            )

        return selected[:count]
