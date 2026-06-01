"""Note types: the Anki-style model that defines fields and card templates.

A NoteType has ordered Fields and one or more CardTemplates. Each template
generates one Card per Note (e.g. Basic+Reversed has two templates → two cards).
Custom note-type *creation* is gated to Advanced mode in the UI; the data model
itself is unrestricted.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.clock import now
from data.db import Base

if TYPE_CHECKING:
    pass


class NoteType(Base):
    __tablename__ = "note_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    css: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_cloze: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    fields: Mapped[list["Field"]] = relationship(
        back_populates="note_type",
        cascade="all, delete-orphan",
        order_by="Field.ordinal",
    )
    templates: Mapped[list["CardTemplate"]] = relationship(
        back_populates="note_type",
        cascade="all, delete-orphan",
        order_by="CardTemplate.ordinal",
    )


class Field(Base):
    __tablename__ = "fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    note_type_id: Mapped[int] = mapped_column(ForeignKey("note_types.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, default=0)

    note_type: Mapped["NoteType"] = relationship(back_populates="fields")


class CardTemplate(Base):
    __tablename__ = "card_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    note_type_id: Mapped[int] = mapped_column(ForeignKey("note_types.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    front_html: Mapped[str] = mapped_column(Text, default="", nullable=False)
    back_html: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, default=0)

    note_type: Mapped["NoteType"] = relationship(back_populates="templates")
