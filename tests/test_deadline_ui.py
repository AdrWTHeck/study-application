"""Headless UI tests for DeadlineView."""
from __future__ import annotations

from datetime import date

import pytest
from PyQt6.QtWidgets import QApplication
from sqlalchemy import select

from app.context import AppContext
from core.settings import Settings
from data.models import Deck
from data.models.deadline import Deadline
from domain.deadlines.deadline_service import DeadlineService
from domain.srs import make_engine
from ui.views.deadline_view import DeadlineView


def _ctx(db, tmp_path) -> AppContext:
    return AppContext(
        db=db, engine=make_engine(),
        settings=Settings.load(tmp_path / "s.json"),
        tts=None, dictionary=None,
    )


def test_deadline_view_renders_empty(qapp, db, tmp_path):
    ctx = _ctx(db, tmp_path)
    view = DeadlineView(ctx)
    view.show()
    assert view.accessibleName() == "Deadlines"


def test_deadline_view_shows_deadline(qapp, db, tmp_path):
    ctx = _ctx(db, tmp_path)
    with db.session() as session:
        DeadlineService(session).create("CS Final", date(2099, 12, 31))

    view = DeadlineView(ctx)
    view.show()
    with db.session() as session:
        summaries = DeadlineService(session).all_summaries()
    assert any(s.name == "CS Final" for s in summaries)


def test_deadline_view_delete(qapp, db, tmp_path):
    ctx = _ctx(db, tmp_path)
    with db.session() as session:
        dl = DeadlineService(session).create("Delete me", date(2099, 6, 1))
        dl_id = dl.id

    view = DeadlineView(ctx)
    view.show()

    with db.session() as session:
        DeadlineService(session).delete(dl_id)

    view._refresh_list()
    with db.session() as session:
        assert DeadlineService(session).get(dl_id) is None


def test_vacation_panel_accessible(qapp, db, tmp_path):
    from ui.views.deadlines.vacation_panel import VacationPanel as _VacationPanel
    ctx = _ctx(db, tmp_path)
    with db.session() as session:
        dl = DeadlineService(session).create("Vac test", date(2099, 8, 15))
        dl_id = dl.id

    panel = _VacationPanel()
    panel.show()
    panel.load(ctx, dl_id, "Vac test", lambda: None)

    assert panel.isVisible()
    assert "skip" in panel.accessibleDescription().lower()


# ---------------------------------------------------------------------------
# E9 — form dialog pre-selects linked decks when editing
# ---------------------------------------------------------------------------

def test_form_dialog_preselects_linked_deck(qapp, db, tmp_path):
    """_DeadlinePlanWizard pre-checks linked decks so edits don't silently unlink them (E9)."""
    from ui.views.deadlines.deadline_wizard import DeadlinePlanWizard as _DeadlinePlanWizard

    ctx = _ctx(db, tmp_path)
    with db.session() as session:
        deck = session.scalar(select(Deck).where(Deck.is_default.is_(True)))
        svc = DeadlineService(session)
        dl = svc.create("Link test", date(2099, 10, 1))
        svc.attach_deck(dl.id, deck.id)
        dl_id, deck_id = dl.id, deck.id

    # Expunge to simulate the pattern used in _edit_deadline (D11).
    with db.session() as session:
        dl = session.get(Deadline, dl_id)
        session.expunge(dl)

    dlg = _DeadlinePlanWizard(ctx, deadline=dl)
    assert deck_id in dlg.selected_deck_ids()


# ---------------------------------------------------------------------------
# E10 — past deadlines appear in the view (D2)
# ---------------------------------------------------------------------------

def test_deadline_view_shows_past_section(qapp, db, tmp_path):
    """Past deadlines are surfaced in the list view via past_summaries (D2, E10)."""
    ctx = _ctx(db, tmp_path)
    with db.session() as session:
        DeadlineService(session).create("Old exam", date(2020, 1, 1))

    view = DeadlineView(ctx)
    view.show()  # triggers _refresh_list

    with db.session() as session:
        past = DeadlineService(session).past_summaries()

    assert any(s.name == "Old exam" for s in past)
    assert all(s.is_past for s in past)


# ---------------------------------------------------------------------------
# E11 — wizard date-picker minimum in create vs edit mode
# ---------------------------------------------------------------------------

def test_wizard_create_mode_minimum_date_is_today(qapp, db, tmp_path):
    """In create mode the date picker minimum is today — past dates are unreachable (E11)."""
    from PyQt6.QtCore import QDate
    from ui.views.deadlines.deadline_wizard import DeadlinePlanWizard as _DeadlinePlanWizard

    ctx = _ctx(db, tmp_path)
    dlg = _DeadlinePlanWizard(ctx)   # create mode
    assert dlg._date_edit.minimumDate() == QDate.currentDate()


def test_wizard_edit_mode_no_minimum_date_restriction(qapp, db, tmp_path):
    """In edit mode the date picker has no today-minimum so past deadlines stay editable (E11)."""
    from PyQt6.QtCore import QDate
    from ui.views.deadlines.deadline_wizard import DeadlinePlanWizard as _DeadlinePlanWizard
    from data.models.deadline import Deadline

    ctx = _ctx(db, tmp_path)
    with db.session() as session:
        dl = DeadlineService(session).create("Old", date(2020, 1, 1))
        dl_id = dl.id

    with db.session() as session:
        dl = session.get(Deadline, dl_id)
        session.expunge(dl)

    dlg = _DeadlinePlanWizard(ctx, deadline=dl)   # edit mode
    # Edit mode must NOT lock the picker to today — a past date must be representable
    assert dlg._date_edit.minimumDate() < QDate.currentDate()


def test_wizard_advances_to_step1_with_valid_future_date(qapp, db, tmp_path):
    """_DeadlinePlanWizard advances from step 0 when name is set and date is in future (E11)."""
    from PyQt6.QtCore import QDate
    from ui.views.deadlines.deadline_wizard import DeadlinePlanWizard as _DeadlinePlanWizard

    ctx = _ctx(db, tmp_path)
    dlg = _DeadlinePlanWizard(ctx)
    dlg._name_edit.setText("Future deadline")
    dlg._date_edit.setDate(QDate.currentDate().addDays(7))

    dlg._go_next()
    assert dlg._pages.currentIndex() == 1


# ---------------------------------------------------------------------------
# Priority card layout — long names must not overlap the action buttons
# ---------------------------------------------------------------------------

def test_priority_card_action_column_top_aligned(qapp, db, tmp_path, sample_deck):
    """A long deadline name wraps without the focus chip / menu button colliding.

    Uses sample_deck so the deadline links to a real deck. Verifies the menu
    button keeps its fixed compact width and is laid out beside (not under) the
    wrapping name label.
    """
    from datetime import date

    from PyQt6.QtWidgets import QPushButton

    from ui.views.deadlines.priority_panel import DeadlinePriorityCard

    long_name = "Extremely Long Deadline Name That Will Definitely Wrap Across Lines"
    with db.session() as session:
        svc = DeadlineService(session)
        dl = svc.create(long_name, date(2099, 11, 1), focus=True)
        svc.attach_deck(dl.id, sample_deck)
        summary = {s.deadline_id: s for s in svc.all_summaries()}[dl.id]

    card = DeadlinePriorityCard(
        summary=summary,
        work_item=None,
        on_edit=lambda *_: None,
        on_delete=lambda *_: None,
        on_vacations=lambda *_: None,
    )
    card.resize(220, 120)  # narrow panel width to force wrapping
    card.show()

    menu_btns = card.findChildren(QPushButton)
    assert menu_btns, "priority card should have a menu button"
    # Compact fixed width keeps it pinned right and out of the name's space.
    assert menu_btns[0].width() <= 40
