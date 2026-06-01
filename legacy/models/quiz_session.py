"""QuizSession ORM model — shared by card sessions and test sessions."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class QuizSession(Base):
    __tablename__ = "quiz_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- Scope ----------------------------------------------------------
    deck_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("decks.id"), nullable=True
    )  # null when scoped to a source document only
    source_document_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("source_documents.id"), nullable=True
    )
    scope_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "deck" | "document" | "combined" | "comprehensive"
    session_type: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # "card" | "test"

    # --- Progress -------------------------------------------------------
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="in_progress"
    )  # "in_progress" | "complete" | "abandoned"
    remaining_item_ids: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )  # ordered IDs not yet presented
    total_items: Mapped[int] = mapped_column(Integer, nullable=False)
    items_reviewed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # --- Analytics (test sessions only; set on completion) --------------
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_time_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_time_per_question: Mapped[float | None] = mapped_column(Float, nullable=True)
    wrong_question_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    deck_scores: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # {deck_id: score%}; comprehensive tests only

    # --- Timestamps -----------------------------------------------------
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # --- Relationships --------------------------------------------------
    deck: Mapped["Deck | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Deck", back_populates="quiz_sessions", foreign_keys=[deck_id]
    )
    source_document: Mapped["SourceDocument | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "SourceDocument", back_populates="quiz_sessions", foreign_keys=[source_document_id]
    )
    question_results: Mapped[list["QuestionResult"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "QuestionResult", back_populates="session"
    )

    def __repr__(self) -> str:
        return (
            f"<QuizSession id={self.id} type={self.session_type!r} "
            f"status={self.status!r}>"
        )
