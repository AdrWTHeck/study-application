"""Quiz generation orchestration — runs generators on text segments and persists results."""
from __future__ import annotations

import logging

from models.base import get_session
from models.question import Question
from repositories.question_repository import QuestionRepository
from repositories.source_repository import SourceRepository
from services.quiz.generators.fill_blank_generator import FillBlankGenerator
from services.quiz.generators.mcq_generator import MCQGenerator
from services.quiz.generators.short_answer_generator import ShortAnswerGenerator

logger = logging.getLogger(__name__)


class QuizService:
    """Orchestrates question generation and manual question management.

    All DB mutations use a single session per public method call —
    commit on success, rollback on error.
    """

    def __init__(self) -> None:
        self._generators = [
            FillBlankGenerator(),
            MCQGenerator(),
            ShortAnswerGenerator(),
        ]

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate_for_document(self, source_document_id: int, deck_id: int) -> int:
        """Run all generators on every segment of a document.

        Returns the number of Question rows created.
        """
        session = get_session()
        try:
            src_repo = SourceRepository(session)
            q_repo = QuestionRepository(session)

            doc = src_repo.get(source_document_id)
            if doc is None:
                logger.warning("SourceDocument %d not found.", source_document_id)
                return 0

            count = 0
            for seg in src_repo.get_all_segments(source_document_id):
                count += self._persist_for_segment(
                    q_repo, seg.text, seg.id, deck_id
                )
            session.commit()
            logger.info(
                "Generated %d questions for document %d (deck %d).",
                count, source_document_id, deck_id,
            )
            return count
        except Exception:
            session.rollback()
            logger.exception(
                "Question generation failed for document %d.", source_document_id
            )
            return 0
        finally:
            session.close()

    def generate_for_segment(
        self, source_segment_id: int, deck_id: int
    ) -> list[Question]:
        """Generate and persist questions for a single text segment."""
        session = get_session()
        try:
            src_repo = SourceRepository(session)
            q_repo = QuestionRepository(session)

            seg = src_repo.get_segment(source_segment_id)
            if seg is None:
                return []

            questions: list[Question] = []
            for generator in self._generators:
                for raw in generator.generate(seg.text):
                    q = self._build_question(raw, generator.generator_type(),
                                             deck_id, seg.id)
                    q_repo.save(q)
                    questions.append(q)

            session.commit()
            for q in questions:
                session.refresh(q)
            return questions
        except Exception:
            session.rollback()
            logger.exception("Generation failed for segment %d.", source_segment_id)
            return []
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Manual question management
    # ------------------------------------------------------------------

    def save_manual_question(
        self,
        deck_id: int,
        question_text: str,
        answer: str,
        q_type: str,
        distractors: list[str] | None = None,
    ) -> Question | None:
        session = get_session()
        try:
            q_repo = QuestionRepository(session)
            q = self._build_question(
                {"question_text": question_text, "answer": answer,
                 "type": q_type, "distractors": distractors},
                "manual", deck_id, None,
            )
            q_repo.save(q)
            session.commit()
            session.refresh(q)
            return q
        except Exception:
            session.rollback()
            logger.exception("Failed to save manual question.")
            return None
        finally:
            session.close()

    def delete_question(self, question_id: int) -> bool:
        session = get_session()
        try:
            q_repo = QuestionRepository(session)
            q = q_repo.get(question_id)
            if q is None:
                return False
            q_repo.delete(q)
            session.commit()
            return True
        except Exception:
            session.rollback()
            logger.exception("Failed to delete question %d.", question_id)
            return False
        finally:
            session.close()

    def get_questions_for_deck(self, deck_id: int) -> list[Question]:
        session = get_session()
        try:
            return QuestionRepository(session).get_by_deck(deck_id)
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _persist_for_segment(
        self,
        q_repo: QuestionRepository,
        text: str,
        segment_id: int | None,
        deck_id: int,
    ) -> int:
        count = 0
        for generator in self._generators:
            for raw in generator.generate(text):
                q = self._build_question(raw, generator.generator_type(),
                                         deck_id, segment_id)
                q_repo.save(q)
                count += 1
        return count

    @staticmethod
    def _build_question(
        raw: dict,
        generator_type: str,
        deck_id: int,
        segment_id: int | None,
    ) -> Question:
        return Question(
            deck_id=deck_id,
            source_segment_id=segment_id,
            question_text=raw["question_text"],
            answer=raw["answer"],
            type=raw["type"],
            generator_type=generator_type,
            distractors=raw.get("distractors"),
        )
