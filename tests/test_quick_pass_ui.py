"""QuickPassView: reveal → Yes/No over due cards, feeding FSRS.

Yes leaves the card untouched (no engine call, no ReviewLog); No sends it back
through FSRS as Rating.AGAIN. New/never-seen cards are excluded from the queue.
"""
from datetime import timedelta

from sqlalchemy import func, select

from app.context import AppContext
from core.clock import now
from core.settings import Settings
from data.models import Card, NoteType, ReviewLog
from domain.decks.deck_service import DeckService
from domain.notes.note_service import NoteService
from domain.srs import RELEARNING, REVIEW, Rating, make_engine
from ui.views.quick_pass_view import QuickPassView


def _ctx(db, tmp_path) -> AppContext:
    return AppContext(db=db, engine=make_engine(),
                      settings=Settings.load(tmp_path / "s.json"), tts=None)


def _deck_with_due_and_new(db):
    """A deck with one DUE review card and one brand-new (never-seen) card."""
    with db.session() as s:
        deck_id = DeckService(s).create("Biology").id
        basic = s.scalar(select(NoteType).where(NoteType.name == "Basic"))
        ns = NoteService(s, make_engine())
        ns.create_note(deck_id, basic.id, {"Front": "due Q", "Back": "due A"})
        ns.create_note(deck_id, basic.id, {"Front": "new Q", "Back": "new A"})
    # Turn the first card into a due review card; leave the second new.
    with db.session() as s:
        card = s.scalars(
            select(Card).where(Card.deck_id == deck_id).order_by(Card.id)
        ).first()
        card.srs_state = REVIEW
        card.due = now() - timedelta(minutes=1)
        card.last_review = now() - timedelta(days=10)
        card.reps = 1
        card.lapses = 0
        card.interval_days = 10.0
        card.stability = 10.0
        card.difficulty = 5.0
        due_card_id = card.id
    return deck_id, due_card_id


def _log_count(db) -> int:
    with db.session() as s:
        return s.scalar(select(func.count()).select_from(ReviewLog))


def test_quick_pass_pulls_due_only_excludes_new(qapp, db, tmp_path):
    deck_id, _ = _deck_with_due_and_new(db)
    view = QuickPassView(_ctx(db, tmp_path))
    view.start(deck_id)
    # Only the due review card; the brand-new card is excluded (new_limit=0).
    assert len(view._queue) == 1
    view._finish()


def test_quick_pass_yes_leaves_card_untouched(qapp, db, tmp_path):
    deck_id, due_card_id = _deck_with_due_and_new(db)
    with db.session() as s:
        before = s.get(Card, due_card_id)
        before_due, before_state = before.due, before.srs_state
    logs_before = _log_count(db)

    view = QuickPassView(_ctx(db, tmp_path))
    view.start(deck_id)
    view._reveal()
    view._mark(got_it=True)
    view._finish()

    with db.session() as s:
        after = s.get(Card, due_card_id)
        assert after.due == before_due
        assert after.srs_state == before_state
    assert _log_count(db) == logs_before  # Yes writes no ReviewLog


def test_quick_pass_no_applies_again_and_logs(qapp, db, tmp_path):
    deck_id, due_card_id = _deck_with_due_and_new(db)
    logs_before = _log_count(db)

    view = QuickPassView(_ctx(db, tmp_path))
    view.start(deck_id)
    view._reveal()
    view._mark(got_it=False)
    view._finish()

    with db.session() as s:
        after = s.get(Card, due_card_id)
        assert after.srs_state == RELEARNING   # AGAIN lapses a review card
        assert after.lapses == 1
        log = s.scalars(select(ReviewLog).order_by(ReviewLog.id.desc())).first()
        assert log is not None
        assert log.scheduler_name == "fsrs"
        assert log.rating == int(Rating.AGAIN)
    assert _log_count(db) == logs_before + 1
