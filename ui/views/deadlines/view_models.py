"""Display-ready dataclasses for the deadline forecast page.

These are plain frozen values with no Qt or DB dependencies, making them easy
to test and pass between forecast builder and UI components.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ForecastWorkItem:
    deadline_id: int
    name: str
    assigned_today: int
    completed_today: int
    days_left: int
    is_overdue: bool
    is_focus: bool


@dataclass(frozen=True)
class ForecastCalendarDay:
    day: date
    is_current_month: bool
    is_today: bool
    is_deadline: bool
    is_rest: bool
    planned_cards: int
    completed_cards: int
    deadline_names: list[str]


@dataclass(frozen=True)
class DeadlineForecast:
    word: str
    word_definition: str
    signal: str
    work_items: list[ForecastWorkItem]
    calendar_days: list[ForecastCalendarDay]
    total_assigned: int
    total_completed: int
