"""Unit tests for DeadlineService — CRUD, vacations, and target math."""
from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from data.models.deadline import Deadline, VacationDay
from domain.deadlines.deadline_service import DeadlineService


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _today() -> date:
    from core.clock import now
    return now().date()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def test_create_and_list(db):
    with db.session() as session:
        svc = DeadlineService(session)
        dl = svc.create("Biology final", date(2099, 12, 31))
        assert dl.id is not None
        assert dl.name == "Biology final"
        assert not dl.focus

    with db.session() as session:
        svc = DeadlineService(session)
        listing = svc.list_all()
        assert any(d.name == "Biology final" for d in listing)


def test_update(db):
    with db.session() as session:
        svc = DeadlineService(session)
        dl = svc.create("Old name", date(2099, 6, 1))

    with db.session() as session:
        svc = DeadlineService(session)
        updated = svc.update(dl.id, name="New name", focus=True)
        assert updated is not None
        assert updated.name == "New name"
        assert updated.focus is True


def test_delete(db):
    with db.session() as session:
        svc = DeadlineService(session)
        dl = svc.create("Temp deadline", date(2099, 9, 1))

    with db.session() as session:
        svc = DeadlineService(session)
        svc.delete(dl.id)
        assert svc.get(dl.id) is None


def test_attach_and_detach_deck(db):
    from data.models import Deck
    from data.repositories.deck_repository import DeckRepository

    with db.session() as session:
        repo = DeckRepository(session)
        deck = repo.default()
        svc = DeadlineService(session)
        dl = svc.create("Deck test", date(2099, 11, 1))
        svc.attach_deck(dl.id, deck.id)

    with db.session() as session:
        svc = DeadlineService(session)
        dl = svc.get(dl.id)
        assert any(d.id == deck.id for d in dl.decks)
        svc.detach_deck(dl.id, deck.id)

    with db.session() as session:
        svc = DeadlineService(session)
        dl = svc.get(dl.id)
        assert not any(d.id == deck.id for d in dl.decks)


# ---------------------------------------------------------------------------
# Vacations
# ---------------------------------------------------------------------------

def test_add_and_remove_vacation(db):
    with db.session() as session:
        svc = DeadlineService(session)
        dl = svc.create("Vac test", date(2099, 12, 31))

    with db.session() as session:
        svc = DeadlineService(session)
        vac = svc.add_vacation(dl.id, date(2099, 7, 1), date(2099, 7, 7), "Summer break")
        assert vac is not None
        assert vac.note == "Summer break"
        vacs = svc.list_vacations(dl.id)
        assert len(vacs) == 1

    with db.session() as session:
        svc = DeadlineService(session)
        svc.remove_vacation(vac.id)
        assert svc.list_vacations(dl.id) == []


# ---------------------------------------------------------------------------
# Target computation
# ---------------------------------------------------------------------------

def test_days_left_excludes_vacations(db):
    ref = date(2099, 7, 1)  # Monday
    target = date(2099, 7, 10)  # 9 days later, expecting 9 working days naive

    with db.session() as session:
        svc = DeadlineService(session)
        dl = svc.create("Math exam", target)
        svc.add_vacation(dl.id, date(2099, 7, 5), date(2099, 7, 7))  # 3 blocked days

    with db.session() as session:
        svc = DeadlineService(session)
        dl = svc.get(dl.id)
        left = svc.days_left(dl, reference=ref)
        # Total calendar days ref+1..target = 9; 3 blocked → 6 remaining
        assert left == 6


def test_days_left_past_deadline(db):
    with db.session() as session:
        svc = DeadlineService(session)
        dl = svc.create("Old exam", date(2020, 1, 1))

    with db.session() as session:
        svc = DeadlineService(session)
        dl = svc.get(dl.id)
        assert svc.days_left(dl, reference=date(2099, 1, 1)) == 0


def test_upcoming_filters_past(db):
    with db.session() as session:
        svc = DeadlineService(session)
        svc.create("Future", date(2099, 12, 31))
        svc.create("Past", date(2020, 1, 1))

    with db.session() as session:
        svc = DeadlineService(session)
        results = svc.upcoming(reference=date(2050, 1, 1))
        assert all(d.target_date >= date(2050, 1, 1) for d in results)
        assert any(d.name == "Future" for d in results)
        assert not any(d.name == "Past" for d in results)


def test_soonest_returns_earliest(db):
    ref = date(2099, 1, 1)
    with db.session() as session:
        svc = DeadlineService(session)
        svc.create("Second", date(2099, 6, 1))
        svc.create("First", date(2099, 3, 1))

    with db.session() as session:
        svc = DeadlineService(session)
        s = svc.soonest(reference=ref)
        assert s is not None
        assert s.name == "First"


# ---------------------------------------------------------------------------
# E1 — remaining_cards counts real new + due cards
# ---------------------------------------------------------------------------

def test_remaining_cards_counts_new_and_due(db):
    """total_remaining includes NEW cards and past-due REVIEW cards only (E1)."""
    from datetime import datetime

    from sqlalchemy import select

    from data.models import Deck, NoteType
    from domain.notes.note_service import NoteService
    from domain.srs import make_engine
    from domain.srs.srs_base import REVIEW

    with db.session() as session:
        deck = session.scalar(select(Deck).where(Deck.is_default.is_(True)))
        nt = session.scalar(select(NoteType).where(NoteType.name == "Basic"))
        ns = NoteService(session, make_engine())

        note_new = ns.create_note(deck.id, nt.id, {"Front": "Q-new", "Back": "A"})
        note_due = ns.create_note(deck.id, nt.id, {"Front": "Q-due", "Back": "A"})
        note_future = ns.create_note(deck.id, nt.id, {"Front": "Q-future", "Back": "A"})

        # Make note_due a past-due review card.
        note_due.cards[0].srs_state = REVIEW
        note_due.cards[0].due = datetime(2000, 1, 1)

        # note_future is not-yet-due review — should NOT count.
        note_future.cards[0].srs_state = REVIEW
        note_future.cards[0].due = datetime(2099, 12, 31)

        # note_new remains NEW → always counts.

        svc = DeadlineService(session)
        dl = svc.create("Exam", date(2099, 12, 31))
        svc.attach_deck(dl.id, deck.id)
        summary = svc.summarize(dl)

    # 1 NEW + 1 past-due REVIEW = 2; future REVIEW excluded.
    assert summary.total_remaining == 2


# ---------------------------------------------------------------------------
# E2 — days_left edge cases
# ---------------------------------------------------------------------------

def test_days_left_vacation_spans_full_window(db):
    """Vacation that covers the entire remaining window → days_left == 0 (E2)."""
    ref = date(2099, 7, 1)
    target = date(2099, 7, 5)  # window = 2,3,4,5 (4 days)

    with db.session() as session:
        svc = DeadlineService(session)
        dl = svc.create("Exam", target)
        svc.add_vacation(dl.id, date(2099, 7, 2), date(2099, 7, 5))  # blocks all 4

    with db.session() as session:
        svc = DeadlineService(session)
        dl = svc.get(dl.id)
        assert svc.days_left(dl, reference=ref) == 0


def test_days_left_vacation_before_ref_is_ignored(db):
    """Vacation entirely before the reference date has no effect on days_left (E2)."""
    ref = date(2099, 7, 5)
    target = date(2099, 7, 10)  # window = 6,7,8,9,10 (5 days)

    with db.session() as session:
        svc = DeadlineService(session)
        dl = svc.create("Exam", target)
        # Vacation before ref — none of these days are in the window.
        svc.add_vacation(dl.id, date(2099, 7, 1), date(2099, 7, 4))

    with db.session() as session:
        svc = DeadlineService(session)
        dl = svc.get(dl.id)
        assert svc.days_left(dl, reference=ref) == 5


# ---------------------------------------------------------------------------
# E3 — daily_target returns None when past-due
# ---------------------------------------------------------------------------

def test_daily_target_past_due_returns_none(db):
    """daily_target() is None for a past deadline — not a meaningful number (C8, E3)."""
    with db.session() as session:
        svc = DeadlineService(session)
        dl = svc.create("Old exam", date(2020, 1, 1))

    with db.session() as session:
        svc = DeadlineService(session)
        dl = svc.get(dl.id)
        assert svc.daily_target(dl, reference=date(2099, 1, 1)) is None


# ---------------------------------------------------------------------------
# E4 — overlapping vacation ranges don't double-count blocked days
# ---------------------------------------------------------------------------

def test_days_left_overlapping_vacations_not_double_counted(db):
    """Overlapping vacation ranges use set union — each day blocked at most once (E4)."""
    ref = date(2099, 7, 1)
    target = date(2099, 7, 10)  # window = 2..10 (9 days)

    with db.session() as session:
        svc = DeadlineService(session)
        dl = svc.create("Exam", target)
        svc.add_vacation(dl.id, date(2099, 7, 3), date(2099, 7, 6))  # blocks 3,4,5,6
        svc.add_vacation(dl.id, date(2099, 7, 5), date(2099, 7, 8))  # blocks 5,6,7,8 (overlap)
        # Union = 3,4,5,6,7,8 → 6 blocked; window 2..10 = 9 days; remaining = 3

    with db.session() as session:
        svc = DeadlineService(session)
        dl = svc.get(dl.id)
        assert svc.days_left(dl, reference=ref) == 3


# ---------------------------------------------------------------------------
# E5 — all_summaries with multiple deadlines
# ---------------------------------------------------------------------------

def test_all_summaries_sorted_earliest_first(db):
    """all_summaries returns upcoming deadlines ordered by target_date ascending (E5)."""
    ref = date(2099, 1, 1)
    with db.session() as session:
        svc = DeadlineService(session)
        svc.create("C", date(2099, 9, 1))
        svc.create("A", date(2099, 3, 1))
        svc.create("B", date(2099, 6, 1))

    with db.session() as session:
        summaries = DeadlineService(session).all_summaries(reference=ref)

    assert [s.name for s in summaries] == ["A", "B", "C"]


def test_all_summaries_excludes_past_deadlines(db):
    """all_summaries omits deadlines whose target_date is strictly before reference (E5)."""
    ref = date(2099, 6, 1)
    with db.session() as session:
        svc = DeadlineService(session)
        svc.create("Past", date(2099, 5, 31))
        svc.create("Future", date(2099, 6, 2))

    with db.session() as session:
        summaries = DeadlineService(session).all_summaries(reference=ref)

    assert len(summaries) == 1
    assert summaries[0].name == "Future"


# ---------------------------------------------------------------------------
# E6 — past_summaries (added in D-series)
# ---------------------------------------------------------------------------

def test_past_summaries_ordered_most_recent_first(db):
    """past_summaries returns past deadlines ordered most-recent-past first (D2, E6)."""
    ref = date(2099, 6, 1)
    with db.session() as session:
        svc = DeadlineService(session)
        svc.create("Older", date(2099, 4, 1))
        svc.create("Recent", date(2099, 5, 1))

    with db.session() as session:
        summaries = DeadlineService(session).past_summaries(reference=ref)

    assert len(summaries) == 2
    assert summaries[0].name == "Recent"
    assert summaries[1].name == "Older"
    assert all(s.is_past for s in summaries)


def test_past_summaries_empty_when_none_past(db):
    """past_summaries returns an empty list when all deadlines are upcoming (E6)."""
    ref = date(2099, 1, 1)
    with db.session() as session:
        DeadlineService(session).create("Future", date(2099, 12, 31))

    with db.session() as session:
        assert DeadlineService(session).past_summaries(reference=ref) == []


# ---------------------------------------------------------------------------
# E7 — DeadlineSummary is safe after the session that created it closes
# ---------------------------------------------------------------------------

def test_deadline_summary_fields_safe_after_session_closes(db):
    """All DeadlineSummary fields are accessible after session closes — no ORM dependency (C1, E7)."""
    with db.session() as session:
        svc = DeadlineService(session)
        dl = svc.create("Detach test", date(2099, 11, 1))
        summary = svc.summarize(dl)

    # Session is now closed — none of these should raise DetachedInstanceError.
    assert summary.name == "Detach test"
    assert summary.target_date == date(2099, 11, 1)
    assert summary.deadline_id == dl.id
    assert not summary.is_past
    assert summary.daily_target is not None  # future deadline with days remaining
    assert summary.total_cards == 0          # no decks linked
    assert summary.reviewed_today == 0       # no reviews done
    assert summary.phase is None             # no phase set
    assert summary.created_at <= date(2099, 11, 1)
    assert summary.status_badge in ("NOT STARTED", "ALL DONE", "ON TRACK", "BEHIND",
                                     "REST DAY", "OVERDUE")
    assert isinstance(summary.smart_message, str)
    assert summary.deck_ids == []
    assert summary.deck_icons == []


# ---------------------------------------------------------------------------
# E8 — schema smoke test
# ---------------------------------------------------------------------------

def test_schema_has_required_deadline_tables(db):
    """deadlines, vacation_days, and deadline_decks tables are present in the schema (E8)."""
    from data.db import Base

    tables = set(Base.metadata.tables.keys())
    assert "deadlines" in tables
    assert "vacation_days" in tables
    assert "deadline_decks" in tables


# ---------------------------------------------------------------------------
# E9 — skip_weekends reduces days_left
# ---------------------------------------------------------------------------

def test_days_left_skip_weekends(db):
    """With skip_weekends=True, Sat/Sun are excluded from the days_left count."""
    # 2099-07-01 is a Wednesday; target 2099-07-10 (Friday).
    # Full window (Thu Jul 2 → Fri Jul 10): 9 days.
    # Weekends in window: Sat Jul 5, Sun Jul 6 → 2 days skipped.
    # Expected: 9 - 2 = 7
    ref = date(2099, 7, 1)
    target = date(2099, 7, 10)

    with db.session() as session:
        svc = DeadlineService(session)
        dl = svc.create("Weekend skip test", target, skip_weekends=True)

    with db.session() as session:
        svc = DeadlineService(session)
        dl = svc.get(dl.id)
        left_skip = svc.days_left(dl, reference=ref)
        dl.skip_weekends = False
        left_no_skip = svc.days_left(dl, reference=ref)

    assert left_no_skip == 9
    assert left_skip == 7


# ---------------------------------------------------------------------------
# E10 — is_over_cap and required_daily in summarize()
# ---------------------------------------------------------------------------

def test_summarize_is_over_cap(db):
    """When required pace > daily_cap, is_over_cap is True and required_daily != daily_target."""
    from datetime import datetime
    from sqlalchemy import select
    from data.models import Deck, NoteType
    from domain.notes.note_service import NoteService
    from domain.srs import make_engine

    with db.session() as session:
        deck = session.scalar(select(Deck).where(Deck.is_default.is_(True)))
        nt = session.scalar(select(NoteType).where(NoteType.name == "Basic"))
        ns = NoteService(session, make_engine())
        # Create 10 new cards
        for i in range(10):
            ns.create_note(deck.id, nt.id, {"Front": f"Q{i}", "Back": "A"})

        svc = DeadlineService(session)
        # 1 day left, daily_cap=3 → required=10, capped=3 → is_over_cap
        dl = svc.create("Cap test", date(2099, 7, 2), daily_cap=3)
        svc.attach_deck(dl.id, deck.id)
        summary = svc.summarize(dl, reference=date(2099, 7, 1))

    assert summary.is_over_cap is True
    assert summary.required_daily == 10
    assert summary.daily_target == 3


def test_summarize_not_over_cap_when_cap_is_sufficient(db):
    """When daily_cap >= required pace, is_over_cap is False."""
    from sqlalchemy import select
    from data.models import Deck, NoteType
    from domain.notes.note_service import NoteService
    from domain.srs import make_engine

    with db.session() as session:
        deck = session.scalar(select(Deck).where(Deck.is_default.is_(True)))
        nt = session.scalar(select(NoteType).where(NoteType.name == "Basic"))
        ns = NoteService(session, make_engine())
        ns.create_note(deck.id, nt.id, {"Front": "Q", "Back": "A"})

        svc = DeadlineService(session)
        # 5 days left, 1 card → required=1, cap=10 → not over cap
        dl = svc.create("Cap OK test", date(2099, 7, 6), daily_cap=10)
        svc.attach_deck(dl.id, deck.id)
        summary = svc.summarize(dl, reference=date(2099, 7, 1))

    assert summary.is_over_cap is False
    assert summary.daily_target == summary.required_daily


# ---------------------------------------------------------------------------
# E11 — deadlines_for_decks batch query
# ---------------------------------------------------------------------------

def test_deadlines_for_decks_returns_soonest_per_deck(db):
    """deadlines_for_decks returns one summary per deck — the soonest upcoming deadline."""
    from sqlalchemy import select
    from data.models import Deck

    ref = date(2099, 1, 1)
    with db.session() as session:
        deck = session.scalar(select(Deck).where(Deck.is_default.is_(True)))
        svc = DeadlineService(session)
        soon = svc.create("Soon", date(2099, 3, 1))
        later = svc.create("Later", date(2099, 9, 1))
        svc.attach_deck(soon.id, deck.id)
        svc.attach_deck(later.id, deck.id)
        deck_id = deck.id

    with db.session() as session:
        result = DeadlineService(session).deadlines_for_decks([deck_id], reference=ref)

    assert deck_id in result
    assert result[deck_id] is not None
    assert result[deck_id].name == "Soon"


def test_deadlines_for_decks_unknown_deck_returns_none(db):
    """deadlines_for_decks returns None for a deck with no linked deadline."""
    ref = date(2099, 1, 1)
    with db.session() as session:
        result = DeadlineService(session).deadlines_for_decks([999999], reference=ref)
    assert result[999999] is None


def test_deadlines_for_decks_empty_input_returns_empty(db):
    """deadlines_for_decks with an empty list returns an empty dict."""
    with db.session() as session:
        assert DeadlineService(session).deadlines_for_decks([]) == {}
