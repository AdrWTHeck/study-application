"""Testing module: questions (+ options/answers), quiz sessions, and results.

Questions live in test-type decks (the same Deck model, deck_type="test").
The card→question bridge sets ``source_card_id`` + ``is_generated_draft`` so
generated questions are clearly labeled and editable (learner autonomy, AUT-01).
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.clock import now
from data.db import Base

if TYPE_CHECKING:
    pass

# Question types.
MCQ = "mcq"
TRUE_FALSE = "true_false"
SHORT_ANSWER = "short_answer"
FILL_BLANK = "fill_blank"
OPTION_TYPES = (MCQ, TRUE_FALSE)
TEXT_TYPES = (SHORT_ANSWER, FILL_BLANK)


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(16), default=SHORT_ANSWER)
    prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_card_id: Mapped[int | None] = mapped_column(
        ForeignKey("cards.id", ondelete="SET NULL"), nullable=True
    )
    is_generated_draft: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    options: Mapped[list["QuestionOption"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="QuestionOption.ordinal"
    )
    answers: Mapped[list["QuestionAnswer"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )


class QuestionOption(Base):
    __tablename__ = "question_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    ordinal: Mapped[int] = mapped_column(Integer, default=0)

    question: Mapped["Question"] = relationship(back_populates="options")


class QuestionAnswer(Base):
    __tablename__ = "question_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    accepted_text: Mapped[str] = mapped_column(Text, default="", nullable=False)

    question: Mapped["Question"] = relationship(back_populates="answers")


class QuizSession(Base):
    __tablename__ = "quiz_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default="in_progress")  # in_progress | complete
    settings_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    results: Mapped[list["QuestionResult"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class QuestionResult(Base):
    __tablename__ = "question_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("quiz_sessions.id", ondelete="CASCADE"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    user_response: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answered_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    session: Mapped["QuizSession"] = relationship(back_populates="results")
