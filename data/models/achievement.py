"""Achievement unlocks for milestones and study progress."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from core.clock import now
from data.db import Base


class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)
