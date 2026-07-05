"""Note — one piece of knowledge; its field values generate one or more cards."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.clock import now
from data.db import Base
from data.models.note_flag import note_flag_assignments
from data.models.tag import note_tags

if TYPE_CHECKING:
    from data.models.card import Card
    from data.models.deck import Deck
    from data.models.note_flag import NoteFlag
    from data.models.note_type import Field, NoteType
    from data.models.tag import Tag


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    note_type_id: Mapped[int] = mapped_column(ForeignKey("note_types.id"))
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    modified_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    note_type: Mapped["NoteType"] = relationship()
    deck: Mapped["Deck"] = relationship(back_populates="notes")
    field_values: Mapped[list["NoteFieldValue"]] = relationship(
        back_populates="note", cascade="all, delete-orphan"
    )
    cards: Mapped[list["Card"]] = relationship(
        back_populates="note", cascade="all, delete-orphan"
    )
    tags: Mapped[list["Tag"]] = relationship(secondary=note_tags)
    flags: Mapped[list["NoteFlag"]] = relationship(secondary=note_flag_assignments)

    def values_by_field_name(self) -> dict[str, str]:
        return {fv.field.name: fv.value for fv in self.field_values if fv.field is not None}


class NoteFieldValue(Base):
    __tablename__ = "note_field_values"

    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"))
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id"))
    value: Mapped[str] = mapped_column(Text, default="", nullable=False)

    note: Mapped["Note"] = relationship(back_populates="field_values")
    field: Mapped["Field"] = relationship()
