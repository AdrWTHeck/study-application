from sqlalchemy import select

from data.models import Deck, NoteType
from domain.notes.note_service import NoteService
from domain.srs import make_engine


def _context(session):
    deck = session.scalar(select(Deck).where(Deck.is_default.is_(True)))
    types = {nt.name: nt.id for nt in session.scalars(select(NoteType))}
    return deck.id, types, NoteService(session, make_engine())


def test_basic_generates_one_card(db):
    with db.session() as s:
        deck_id, types, svc = _context(s)
        note = svc.create_note(deck_id, types["Basic"], {"Front": "Q", "Back": "A"})
        assert len(note.cards) == 1
        assert note.cards[0].srs_state == "new"
        assert note.cards[0].due is not None


def test_reversed_generates_two_cards(db):
    with db.session() as s:
        deck_id, types, svc = _context(s)
        note = svc.create_note(deck_id, types["Basic (and reversed)"], {"Front": "Q", "Back": "A"})
        assert len(note.cards) == 2


def test_cloze_generates_one_card(db):
    with db.session() as s:
        deck_id, types, svc = _context(s)
        note = svc.create_note(deck_id, types["Cloze"], {"Text": "The {{c1::sun}} is hot", "Extra": ""})
        assert len(note.cards) == 1


def test_field_values_round_trip(db):
    with db.session() as s:
        deck_id, types, svc = _context(s)
        note = svc.create_note(deck_id, types["Basic"], {"Front": "Q", "Back": "A"})
        assert note.values_by_field_name() == {"Front": "Q", "Back": "A"}
