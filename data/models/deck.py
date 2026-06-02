"""Deck — flat collection with favorite, category, color, and tags."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.clock import now
from data.db import Base
from data.models.tag import deck_tags

if TYPE_CHECKING:
    from data.models.card import Card
    from data.models.note import Note
    from data.models.tag import Tag


class Deck(Base):
    __tablename__ = "decks"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    deck_type: Mapped[str] = mapped_column(String(10), nullable=False, default="card")  # card | test
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    notes: Mapped[list["Note"]] = relationship(
        back_populates="deck", cascade="all, delete-orphan"
    )
    cards: Mapped[list["Card"]] = relationship(
        back_populates="deck", cascade="all, delete-orphan"
    )
    tags: Mapped[list["Tag"]] = relationship(secondary=deck_tags)

    def __repr__(self) -> str:
        return f"<Deck id={self.id} name={self.name!r} type={self.deck_type}>"
