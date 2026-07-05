"""Pure helper functions for deadline card rendering (legacy cards + sorting)."""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QDate

from domain.deadlines.deadline_service import DeadlineSummary


def qdate(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def from_qdate(qd: QDate) -> date:
    return date(qd.year(), qd.month(), qd.day())


def sort_summaries(summaries: list[DeadlineSummary]) -> list[DeadlineSummary]:
    """Focus first → most urgent (lowest days_left) → most work (highest remaining)."""
    def key(s: DeadlineSummary):
        return (0 if s.focus else 1, s.days_left, -(s.total_remaining or 0))
    return sorted(summaries, key=key)


def urgency_objectname(s: DeadlineSummary) -> str:
    if s.focus:
        return "DeadlineCardFocus"
    if not s.is_past and s.days_left <= 7:
        return "DeadlineCardUrgent"
    return "DeadlineCard"


def accent_objectname(s: DeadlineSummary) -> str:
    if s.focus:
        return "DeadlineAccentFocus"
    if not s.is_past and s.days_left <= 7:
        return "DeadlineAccentUrgent"
    return "DeadlineAccentNormal"


def status_badge_objectname(badge: str) -> str:
    return {
        "ON TRACK": "StatusBadgeOnTrack",
        "BEHIND": "StatusBadgeBehind",
        "REST DAY": "StatusBadgeRestDay",
        "NOT STARTED": "StatusBadgeNotStarted",
        "ALL DONE": "StatusBadgeAllDone",
        "OVERDUE": "StatusBadgeOverdue",
    }.get(badge, "StatusBadgeNotStarted")


def deadline_meta_text(summary: DeadlineSummary) -> str:
    parts: list[str] = []
    if summary.phase:
        parts.append(f"Phase: {summary.phase}")
    target = summary.target_date
    date_str = f"{target.strftime('%a, %b')} {target.day}, {target.year}"
    if summary.is_past:
        days_text = "Past"
    elif summary.days_left == 0:
        days_text = "Due today"
    else:
        days_text = f"in {summary.days_left} day{'s' if summary.days_left != 1 else ''}"
    parts.append(f"{date_str} · {days_text}")
    return "  ·  ".join(parts)


def urgency_chip(summary: DeadlineSummary) -> tuple[str, str] | None:
    if summary.is_past:
        return None
    if summary.days_left <= 3:
        return "⚠ Due very soon", "Very urgent: due in 3 days or fewer"
    if summary.days_left <= 7:
        return "⚠ Urgent", "Urgent: due within 7 days"
    if summary.days_left <= 30:
        return "Soon", "Due soon: within 30 days"
    return None
