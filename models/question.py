"""Question ORM model — no SM-2 fields (CON-12)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Question(Base):
    __tablename__ = "questions"

    # --- Identity -------------------------------------------------------
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deck_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("decks.id"), nullable=False
    )
    source_segment_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("text_segments.id"), nullable=True
    )  # null for manual / promoted cards

    # --- Content --------------------------------------------------------
    question_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "fill_blank" | "mcq" | "short_answer" | "verbatim"
    generator_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "rule_based" | "manual"
    distractors: Mapped[list | None] = mapped_column(
        JSON, nullable=True
    )  # list[str]; MCQ only

    # --- Timestamps -----------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    # --- Relationships --------------------------------------------------
    deck: Mapped["Deck"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Deck", back_populates="questions", foreign_keys=[deck_id]
    )
    source_segment: Mapped["TextSegment | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "TextSegment", back_populates="questions"
    )
    results: Mapped[list["QuestionResult"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "QuestionResult", back_populates="question"
    )

    def __repr__(self) -> str:
        preview = (self.question_text or "")[:40]
        return f"<Question id={self.id} type={self.type!r} text={preview!r}>"
