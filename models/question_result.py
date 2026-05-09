"""QuestionResult ORM model — one record per question per test session."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class QuestionResult(Base):
    __tablename__ = "question_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- Foreign keys ---------------------------------------------------
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("quiz_sessions.id"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("questions.id"), nullable=False
    )

    # --- Answer data ----------------------------------------------------
    user_answer: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # raw text or MCQ option text
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    similarity_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # fill-blank and short-answer only

    # --- Timing ---------------------------------------------------------
    time_taken_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    presented_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # --- Relationships --------------------------------------------------
    session: Mapped["QuizSession"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "QuizSession", back_populates="question_results"
    )
    question: Mapped["Question"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Question", back_populates="results"
    )

    def __repr__(self) -> str:
        return (
            f"<QuestionResult id={self.id} session={self.session_id} "
            f"question={self.question_id} correct={self.correct}>"
        )
