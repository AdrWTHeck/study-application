"""Deadline tracker — named exam/event deadlines linked to card decks.

Each deadline has a target date and an optional set of attached decks.
VacationDay ranges mark days to skip when computing daily study targets.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.clock import now
from data.db import Base

if TYPE_CHECKING:
    from data.models.deck import Deck

deadline_decks = Table(
    "deadline_decks",
    Base.metadata,
    Column("deadline_id", ForeignKey("deadlines.id", ondelete="CASCADE"), primary_key=True),
    Column("deck_id", ForeignKey("decks.id", ondelete="CASCADE"), primary_key=True),
)


class Deadline(Base):
    __tablename__ = "deadlines"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    focus: Mapped[bool] = mapped_column(Boolean, default=False)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phase: Mapped[str | None] = mapped_column(String(200), nullable=True)
    skip_weekends: Mapped[bool] = mapped_column(Boolean, default=False)
    daily_cap: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    decks: Mapped[list["Deck"]] = relationship("Deck", secondary=deadline_decks, lazy="select")
    vacations: Mapped[list["VacationDay"]] = relationship(
        "VacationDay", back_populates="deadline", cascade="all, delete-orphan"
    )


class VacationDay(Base):
    __tablename__ = "vacation_days"

    id: Mapped[int] = mapped_column(primary_key=True)
    deadline_id: Mapped[int] = mapped_column(
        ForeignKey("deadlines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    deadline: Mapped["Deadline"] = relationship("Deadline", back_populates="vacations")
