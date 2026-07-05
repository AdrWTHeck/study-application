"""Review log — one row per rating. Powers stats (dashboard) and is exactly the
history a future FSRS optimizer needs (docs/FSRS_FEASIBILITY.md)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.clock import now
from data.db import Base


class ReviewLog(Base):
    __tablename__ = "review_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"))
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..4
    prev_state: Mapped[str] = mapped_column(String(12))
    new_state: Mapped[str] = mapped_column(String(12))
    prev_interval: Mapped[float] = mapped_column(Float, default=0.0)
    new_interval: Mapped[float] = mapped_column(Float, default=0.0)
    prev_ease: Mapped[float] = mapped_column(Float, default=0.0)
    new_ease: Mapped[float] = mapped_column(Float, default=0.0)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    # FSRS memory-model snapshot (nullable; populated when the FSRS engine is
    # active — feeds an optional future optimizer and richer stats).
    scheduler_name: Mapped[str | None] = mapped_column(String(8), nullable=True)
    prev_stability: Mapped[float | None] = mapped_column(Float, nullable=True)
    new_stability: Mapped[float | None] = mapped_column(Float, nullable=True)
    prev_difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)
    new_difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)
