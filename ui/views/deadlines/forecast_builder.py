"""Build a DeadlineForecast view-model from DeadlineSummary objects.

Fully pure: no Qt imports, no DB access. The calendar grid is generated wide
enough to cover Month, 2-weeks, and To-next-deadline toggle modes without
needing a separate data fetch when the mode changes.
"""
from __future__ import annotations

import calendar as _cal
from datetime import date, timedelta

from domain.deadlines.deadline_service import DeadlineSummary
from domain.deadlines.word_pool import resolve_pool, word_of_the_day
from ui.views.deadlines.view_models import (
    DeadlineForecast,
    ForecastCalendarDay,
    ForecastWorkItem,
)


def completion_band(planned: int, completed: int) -> str:
    """Return a completion band string for a calendar day."""
    if planned <= 0:
        return "none"
    if completed <= 0:
        return "empty"
    ratio = completed / planned
    if ratio >= 1.0:
        return "full"
    if ratio >= 0.67:
        return "high"
    if ratio >= 0.34:
        return "medium"
    return "low"


def build_forecast(
    all_summaries: list[DeadlineSummary],
    today: date,
    word_pool: list[tuple[str, str]] | None = None,
) -> DeadlineForecast:
    """Derive the full DeadlineForecast view-model from current summaries.

    *word_pool* is the resolved (word, definition) list; when omitted, the full
    base pool is used. Callers pass a user-customized pool from settings.
    """
    pool = word_pool if word_pool is not None else resolve_pool()
    word, word_def = word_of_the_day(today.toordinal(), pool)

    active = [s for s in all_summaries if not s.is_past and s.deck_names]

    work_items: list[ForecastWorkItem] = []
    for s in active:
        if s.total_remaining == 0:
            assigned_today = 0
        elif s.days_left == 0:
            assigned_today = s.total_remaining
        else:
            assigned_today = s.daily_target or 0
        completed_today = min(s.reviewed_today, assigned_today) if assigned_today > 0 else 0
        work_items.append(ForecastWorkItem(
            deadline_id=s.deadline_id,
            name=s.name,
            assigned_today=assigned_today,
            completed_today=completed_today,
            days_left=s.days_left,
            is_overdue=s.is_past,
            is_focus=s.focus,
        ))

    work_items.sort(key=lambda i: (-i.assigned_today, i.days_left))

    active_work = [w for w in work_items if w.assigned_today > 0]
    if not active_work:
        signal = "No deadline work is required today. Take a breath."
    else:
        top = active_work[0]
        if top.is_overdue:
            signal = f"{top.name} is overdue and should come first. You got this."
        elif len(active_work) == 1:
            signal = f"{top.name} is driving today's workload. You got this."
        else:
            signal = f"{top.name} is driving most of today's workload. You got this."

    total_assigned = sum(w.assigned_today for w in work_items)
    total_completed = sum(w.completed_today for w in work_items)

    calendar_days = _build_calendar_days(all_summaries, work_items, today)

    return DeadlineForecast(
        word=word,
        word_definition=word_def,
        signal=signal,
        work_items=work_items,
        calendar_days=calendar_days,
        total_assigned=total_assigned,
        total_completed=total_completed,
    )


def _build_calendar_days(
    all_summaries: list[DeadlineSummary],
    work_items: list[ForecastWorkItem],
    today: date,
) -> list[ForecastCalendarDay]:
    """Build a Mon-aligned grid wide enough for all three toggle modes.

    Covers:
    - Current month (Month mode)
    - today through today+13 (2-weeks mode)
    - today through soonest upcoming deadline (To-next-deadline mode)
    """
    first = today.replace(day=1)
    last_day_num = _cal.monthrange(today.year, today.month)[1]
    last_of_month = today.replace(day=last_day_num)

    # Earliest Monday to show (beginning of the month-grid or today's week)
    first_mon = first - timedelta(days=first.weekday())
    today_mon = today - timedelta(days=today.weekday())
    grid_start = min(first_mon, today_mon)

    # Latest Sunday to show: cover month end, today+13, and soonest deadline
    soonest_dl = min(
        (s.target_date for s in all_summaries if not s.is_past),
        default=last_of_month,
    )
    raw_end = max(last_of_month, today + timedelta(days=13), soonest_dl)
    grid_end = raw_end + timedelta(days=(6 - raw_end.weekday()))

    deadline_date_to_names: dict[date, list[str]] = {}
    for s in all_summaries:
        deadline_date_to_names.setdefault(s.target_date, []).append(s.name)

    days: list[ForecastCalendarDay] = []
    cursor = grid_start
    while cursor <= grid_end:
        planned = 0
        if cursor >= today:
            for s in all_summaries:
                if s.is_past or cursor > s.target_date or s.total_remaining <= 0:
                    continue
                planned += s.daily_target or 0

        completed_on_day = 0
        if cursor == today:
            completed_on_day = sum(
                min(w.completed_today, w.assigned_today) for w in work_items
            )

        days.append(ForecastCalendarDay(
            day=cursor,
            is_current_month=cursor.month == today.month,
            is_today=cursor == today,
            is_deadline=cursor in deadline_date_to_names,
            is_rest=False,
            planned_cards=planned,
            completed_cards=completed_on_day,
            deadline_names=deadline_date_to_names.get(cursor, []),
        ))
        cursor += timedelta(days=1)

    return days
