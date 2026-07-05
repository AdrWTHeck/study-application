from sqlalchemy import select

from app.context import AppContext
from core.settings import Settings
from data.models import Card, Deck, NoteType
from domain.notes.note_service import NoteService
from domain.srs import make_engine
from ui.views.cram_view import CramView


def _ctx(db, tmp_path) -> AppContext:
    return AppContext(db=db, engine=make_engine(), settings=Settings.load(tmp_path / "s.json"), tts=None)


def _add_basic_note(db):
    with db.session() as s:
        deck = s.scalar(select(Deck).where(Deck.is_default.is_(True)))
        basic = s.scalar(select(NoteType).where(NoteType.name == "Basic"))
        NoteService(s, make_engine()).create_note(deck.id, basic.id, {"Front": "Q", "Back": "A"})
        return deck.id


def test_cram_view_preserves_card_state(qapp, db, tmp_path):
    deck_id = _add_basic_note(db)
    view = CramView(_ctx(db, tmp_path))
    view.start(deck_id)
    assert len(view._queue) == 1
    view._reveal()
    view._record("pass")
    view._finish()

    with db.session() as s:
        card = s.scalars(select(Card)).first()
    assert card.srs_state == "new"


def test_cram_view_retry_requeues_card(qapp, db, tmp_path):
    with db.session() as s:
        deck = s.scalar(select(Deck).where(Deck.is_default.is_(True)))
        basic = s.scalar(select(NoteType).where(NoteType.name == "Basic"))
        for i in range(3):
            NoteService(s, make_engine()).create_note(deck.id, basic.id, {"Front": f"Q{i}", "Back": f"A{i}"})
        deck_id = deck.id

    view = CramView(_ctx(db, tmp_path))
    view.start(deck_id)
    first_card = view._queue[0]
    view._reveal()
    view._record("retry")
    assert len(view._queue) == 3
    assert first_card in view._queue
    assert view._queue.index(first_card) == 1


def test_cram_view_fail_requeues_card_to_end(qapp, db, tmp_path):
    with db.session() as s:
        deck = s.scalar(select(Deck).where(Deck.is_default.is_(True)))
        basic = s.scalar(select(NoteType).where(NoteType.name == "Basic"))
        for i in range(3):
            NoteService(s, make_engine()).create_note(deck.id, basic.id, {"Front": f"Q{i}", "Back": f"A{i}"})
        deck_id = deck.id

    view = CramView(_ctx(db, tmp_path))
    view.start(deck_id)
    first_card = view._queue[0]
    view._reveal()
    view._record("fail")
    assert len(view._queue) == 3
    assert view._queue[-1] == first_card
