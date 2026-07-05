"""Customizable, color-coded note flags (status labels).

Distinct from organizational Tags: flags mark work/quality status — e.g.
Incomplete, Confusing definition, Needs example, Wrong — each with an editable
name + color (managed in Settings). Shown as chips in the card/notes browser.
"""
from __future__ import annotations

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column

from data.db import Base

note_flag_assignments = Table(
    "note_flag_assignments",
    Base.metadata,
    Column("note_id", ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    Column("flag_id", ForeignKey("note_flags.id", ondelete="CASCADE"), primary_key=True),
)


class NoteFlag(Base):
    __tablename__ = "note_flags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="#868e96", nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
