"""Quiz session lifecycle: start, record graded answers, finish, plus retest
seeding and result stats (score, accuracy-by-type, history trend).
"""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from dataclasses import dataclass

from core.clock import now
from data.models import Deck, Question, QuestionResult, QuizSession
from domain.testing.grading import grade


@dataclass
class DeckBreakdown:
    deck: str
    correct: int
    total: int

    @property
    def pct(self) -> float:
        return round(100.0 * self.correct / self.total, 1) if self.total else 0.0


@dataclass
class AnswerReviewRow:
    """One question's outcome for the end-of-test answer review."""
    prompt: str
    user_response: str
    is_correct: bool
    correct_answer: str
    time_ms: int | None = None
    explanation: str = ""


class QuizService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def questions_for(self, deck_id: int) -> list[Question]:
        return list(
            self.session.scalars(
                select(Question).where(Question.deck_id == deck_id).order_by(Question.id)
            )
        )

    def gather_questions(self, deck_ids: list[int]) -> list[Question]:
        """All questions across several decks (comprehensive test)."""
        if not deck_ids:
            return []
        return list(
            self.session.scalars(
                select(Question).where(Question.deck_id.in_(deck_ids)).order_by(Question.deck_id, Question.id)
            )
        )

    def breakdown_by_deck(self, session_id: int) -> list[DeckBreakdown]:
        """Per-deck correct/total for a session, weakest first (comprehensive results)."""
        totals: dict[int, list[int]] = {}
        for result in self.results_for(session_id):
            question = self.session.get(Question, result.question_id)
            if question is None:
                continue
            entry = totals.setdefault(question.deck_id, [0, 0])
            entry[0] += 1 if result.is_correct else 0
            entry[1] += 1
        out: list[DeckBreakdown] = []
        for deck_id, (correct, total) in totals.items():
            deck = self.session.get(Deck, deck_id)
            out.append(DeckBreakdown(deck=deck.name if deck else f"Deck {deck_id}",
                                     correct=correct, total=total))
        out.sort(key=lambda b: b.pct)  # weakest area first
        return out

    def start(self, deck_id: int, settings: dict | None = None) -> QuizSession:
        session_row = QuizSession(deck_id=deck_id, settings_json=json.dumps(settings or {}))
        self.session.add(session_row)
        self.session.flush()
        return session_row

    def record(self, quiz_session: QuizSession, question: Question, response: str,
               time_ms: int | None = None, fuzzy_threshold: int = 80) -> QuestionResult:
        is_correct, score = grade(question, response, fuzzy_threshold)
        result = QuestionResult(
            session_id=quiz_session.id, question_id=question.id,
            user_response=response or "", is_correct=is_correct, score=score, time_ms=time_ms,
        )
        self.session.add(result)
        self.session.flush()
        return result

    def finish(self, quiz_session: QuizSession) -> None:
        quiz_session.finished_at = now()
        quiz_session.status = "complete"
        self.session.flush()

    # -- stats --------------------------------------------------------------

    def results_for(self, session_id: int) -> list[QuestionResult]:
        return list(
            self.session.scalars(
                select(QuestionResult).where(QuestionResult.session_id == session_id)
                .order_by(QuestionResult.id)
            )
        )

    def session_score(self, session_id: int) -> float:
        results = self.results_for(session_id)
        if not results:
            return 0.0
        return round(100.0 * sum(1 for r in results if r.is_correct) / len(results), 1)

    def accuracy_by_type(self, session_id: int) -> dict[str, tuple[int, int]]:
        out: dict[str, tuple[int, int]] = {}
        for result in self.results_for(session_id):
            question = self.session.get(Question, result.question_id)
            kind = question.type if question else "?"
            correct, total = out.get(kind, (0, 0))
            out[kind] = (correct + (1 if result.is_correct else 0), total + 1)
        return out

    def answer_review(self, session_id: int) -> list[AnswerReviewRow]:
        """Per-question breakdown: prompt, the user's answer, correctness, the
        correct answer, and time spent — for the end-of-test review list."""
        rows: list[AnswerReviewRow] = []
        for result in self.results_for(session_id):
            question = self.session.get(Question, result.question_id)
            if question is None:
                continue
            rows.append(AnswerReviewRow(
                prompt=question.prompt or "",
                user_response=result.user_response or "",
                is_correct=result.is_correct,
                correct_answer=self._correct_answer_text(question),
                time_ms=result.time_ms,
                explanation=question.explanation or "",
            ))
        return rows

    @staticmethod
    def _correct_answer_text(question: Question) -> str:
        correct_options = [o.text for o in question.options if o.is_correct]
        if correct_options:
            return ", ".join(correct_options)
        return ", ".join(a.accepted_text for a in question.answers)

    def incorrect_questions(self, session_id: int) -> list[Question]:
        questions = []
        for result in self.results_for(session_id):
            if not result.is_correct:
                question = self.session.get(Question, result.question_id)
                if question is not None:
                    questions.append(question)
        return questions

    def session_duration_ms(self, session_id: int) -> int:
        """Total wall-clock duration of a session, in milliseconds.

        Prefers the session's started/finished timestamps; falls back to the
        sum of per-question times if timestamps are unavailable.
        """
        quiz_session = self.session.get(QuizSession, session_id)
        if (
            quiz_session is not None
            and quiz_session.finished_at is not None
            and quiz_session.started_at is not None
        ):
            delta = quiz_session.finished_at - quiz_session.started_at
            ms = int(delta.total_seconds() * 1000)
            if ms > 0:
                return ms
        # Fallback: sum the recorded per-question times.
        return sum((r.time_ms or 0) for r in self.results_for(session_id))

    def slowest_questions(
        self, session_id: int, limit: int = 5
    ) -> list[tuple[Question, int]]:
        """Questions that took the longest, slowest first.

        Returns (Question, time_ms) pairs. Results without a recorded time are
        skipped. ``limit`` caps how many are returned.
        """
        timed: list[tuple[Question, int]] = []
        for result in self.results_for(session_id):
            if result.time_ms is None:
                continue
            question = self.session.get(Question, result.question_id)
            if question is not None:
                timed.append((question, result.time_ms))
        timed.sort(key=lambda pair: pair[1], reverse=True)
        return timed[:limit]

    def history(self, deck_id: int) -> list[tuple[int, object, float]]:
        sessions = self.session.scalars(
            select(QuizSession)
            .where(QuizSession.deck_id == deck_id, QuizSession.status == "complete")
            .order_by(QuizSession.started_at)
        )
        return [(s.id, s.finished_at, self.session_score(s.id)) for s in sessions]
