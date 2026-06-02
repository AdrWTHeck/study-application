"""Card ORM model — satisfies SRSBase structurally (duck-typed)."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Card(Base):
    __tablename__ = "cards"

    # --- Identity -------------------------------------------------------
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deck_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("decks.id"), nullable=False
    )

    # --- Content --------------------------------------------------------
    front_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    back_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_path: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )  # relative path under user_data/audio/

    # --- SRS / category fields (SRSBase interface) ----------------------
    category: Mapped[str] = mapped_column(
        String(20), nullable=False, default="new"
    )  # "new" | "learning" | "review"
    learning_step: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )  # index into step array
    ease_factor: Mapped[float] = mapped_column(
        Float, nullable=False, default=2.5
    )  # SM-2; active in Review only
    interval: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )  # SM-2 days; active in Review only
    repetitions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )  # SM-2; active in Review only
    next_review_date: Mapped[date] = mapped_column(
        Date, nullable=False, default=date.today
    )

    # --- Timestamps -----------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    # --- Relationships --------------------------------------------------
    deck: Mapped["Deck"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Deck", back_populates="cards", foreign_keys=[deck_id]
    )

    # --- SRSBase interface methods (duck-typed) -------------------------
    def get_id(self) -> int:
        return self.id

    def get_deck_type(self) -> str:
        return self.deck.deck_type

    def __repr__(self) -> str:
        return (
            f"<Card id={self.id} category={self.category!r} "
            f"next_review={self.next_review_date}>"
        )
