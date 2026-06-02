"""Card — one (note × template) studyable item with its scheduling state.

The SRS columns are a *superset*: SM-2 uses ease_factor/interval_days, FSRS will
use stability/difficulty — both share state/due/last_review/reps/lapses, so
switching engines needs no migration (see docs/FSRS_FEASIBILITY.md).
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.clock import now
from data.db import Base

if TYPE_CHECKING:
    from data.models.deck import Deck
    from data.models.note import Note
    from data.models.note_type import CardTemplate


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"))
    template_id: Mapped[int | None] = mapped_column(ForeignKey("card_templates.id"), nullable=True)
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"))

    # --- shared scheduling state (both engines; drives UI counts + due queries)
    srs_state: Mapped[str] = mapped_column(String(12), default="new", nullable=False)
    due: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)
    last_review: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    learning_step: Mapped[int] = mapped_column(Integer, default=0)

    # --- SM-2 fields
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[float] = mapped_column(Float, default=0.0)

    # --- FSRS fields (reserved; null until FSRS is enabled)
    stability: Mapped[float | None] = mapped_column(Float, nullable=True)
    difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    note: Mapped["Note"] = relationship(back_populates="cards")
    template: Mapped["CardTemplate | None"] = relationship()
    deck: Mapped["Deck"] = relationship(back_populates="cards")

    def __repr__(self) -> str:
        return f"<Card id={self.id} state={self.srs_state!r} due={self.due}>"
