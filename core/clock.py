"""Single source of 'now' — naive UTC.

Centralized so scheduling and timestamps are consistent and tests can freeze it.
Naive UTC avoids SQLite tz round-trip pitfalls; convert at the FSRS boundary later.
"""
from __future__ import annotations

from datetime import datetime, timezone


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
