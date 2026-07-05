"""Companion and diagnostic models for the Pomodoro study companion (§6.3)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.clock import now
from data.db import Base

XP_PER_LEVEL = 100


class CompanionState(Base):
    """Single-row table holding the user's companion progress."""

    __tablename__ = "companion_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), default="tree")   # "tree" | "pet"
    name: Mapped[str] = mapped_column(String(64), default="")
    level: Mapped[int] = mapped_column(Integer, default=1)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    # Daily growth: XP earned *today* plus the date that figure applies to.
    # Reset to 0 by the service when the date rolls over (the dashboard widget
    # shows "grown today", not the lifetime total).
    xp_today: Mapped[int] = mapped_column(Integer, default=0)
    xp_today_date: Mapped[str] = mapped_column(String(10), default="")  # "YYYY-MM-DD"
    last_fed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    # -- computed helpers (no DB columns) ------------------------------------

    @property
    def xp_for_next_level(self) -> int:
        return self.level * XP_PER_LEVEL

    @property
    def xp_in_current_level(self) -> int:
        return self.xp % XP_PER_LEVEL

    @property
    def growth_state(self) -> str:
        """Human-readable growth stage based on level."""
        if self.level <= 2:
            return "seed" if self.kind == "tree" else "egg"
        if self.level <= 5:
            return "sprout" if self.kind == "tree" else "hatchling"
        if self.level <= 10:
            return "sapling" if self.kind == "tree" else "fledgling"
        if self.level <= 20:
            return "grown" if self.kind == "tree" else "companion"
        return "flourishing" if self.kind == "tree" else "elder"

    @property
    def glyph(self) -> str:
        """Single emoji for the companion's current growth state."""
        tree_glyphs = {
            "seed": "🌱", "sprout": "🌿", "sapling": "🌳",
            "grown": "🌲", "flourishing": "✨🌲",
        }
        pet_glyphs = {
            "egg": "🥚", "hatchling": "🐣", "fledgling": "🐥",
            "companion": "🐦", "elder": "🦉",
        }
        glyphs = tree_glyphs if self.kind == "tree" else pet_glyphs
        return glyphs.get(self.growth_state, "🌱")


class DiagnosticItem(Base):
    """One confidence rating for a single note, part of a session diagnostic sweep."""

    __tablename__ = "diagnostic_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_key: Mapped[str] = mapped_column(String(64))  # UUID per session
    note_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("notes.id", ondelete="SET NULL"), nullable=True
    )
    prompt_text: Mapped[str] = mapped_column(String(500))
    before_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0–3
    after_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)   # 0–3
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
