"""SourceDocument and TextSegment ORM models."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # "pending" | "complete" | "failed"
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    # --- Relationships --------------------------------------------------
    text_segments: Mapped[list["TextSegment"]] = relationship(
        "TextSegment",
        back_populates="source_document",
        cascade="all, delete-orphan",
    )
    decks: Mapped[list["Deck"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Deck",
        secondary="deck_sources",
        back_populates="source_documents",
    )
    quiz_sessions: Mapped[list["QuizSession"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "QuizSession",
        back_populates="source_document",
        foreign_keys="QuizSession.source_document_id",
    )

    def __repr__(self) -> str:
        return f"<SourceDocument id={self.id} filename={self.filename!r}>"


class TextSegment(Base):
    __tablename__ = "text_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("source_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    segment_index: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # position within the page
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Relationships --------------------------------------------------
    source_document: Mapped["SourceDocument"] = relationship(
        "SourceDocument", back_populates="text_segments"
    )
    questions: Mapped[list["Question"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Question", back_populates="source_segment"
    )

    def __repr__(self) -> str:
        preview = self.text[:40] if self.text else ""
        return f"<TextSegment id={self.id} page={self.page_number} text={preview!r}>"
