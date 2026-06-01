"""Deck model and deck_sources many-to-many junction table."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

# Many-to-many junction between Deck and SourceDocument.
# ON DELETE CASCADE keeps the junction tidy when either side is removed.
deck_sources = Table(
    "deck_sources",
    Base.metadata,
    Column(
        "deck_id",
        Integer,
        ForeignKey("decks.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "source_document_id",
        Integer,
        ForeignKey("source_documents.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Deck(Base):
    __tablename__ = "decks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    deck_type: Mapped[str] = mapped_column(String(10), nullable=False)   # "card" | "test"
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )

    # Relationships — FK references use string names to avoid circular imports.
    cards: Mapped[list["Card"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Card", back_populates="deck", foreign_keys="Card.deck_id"
    )
    questions: Mapped[list["Question"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Question", back_populates="deck", foreign_keys="Question.deck_id"
    )
    quiz_sessions: Mapped[list["QuizSession"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "QuizSession", back_populates="deck", foreign_keys="QuizSession.deck_id"
    )
    source_documents: Mapped[list["SourceDocument"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "SourceDocument",
        secondary="deck_sources",
        back_populates="decks",
    )

    def __repr__(self) -> str:
        return f"<Deck id={self.id} name={self.name!r} type={self.deck_type!r}>"
