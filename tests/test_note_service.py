from sqlalchemy import select

from data.models import Card, Deck, Note, NoteType
from domain.notes.note_service import NoteService
from domain.notes.note_type_service import NoteTypeService
from domain.srs import make_engine


def _basic(session):
    deck = session.scalar(select(Deck).where(Deck.is_default.is_(True)))
    basic = session.scalar(select(NoteType).where(NoteType.name == "Basic"))
    return deck, basic


def test_move_to_deck_moves_cards(db):
    with db.session() as s:
        deck, basic = _basic(s)
        other = Deck(name="Other")
        s.add(other)
        s.flush()
        service = NoteService(s, make_engine())
        note = service.create_note(deck.id, basic.id, {"Front": "Q", "Back": "A"})
        service.move_to_deck(note, other.id)
        assert note.deck_id == other.id
        assert all(c.deck_id == other.id for c in note.cards)


def test_delete_note_by_id_removes_cards(db):
    with db.session() as s:
        deck, basic = _basic(s)
        service = NoteService(s, make_engine())
        note = service.create_note(deck.id, basic.id, {"Front": "Q", "Back": "A"})
        note_id = note.id
        service.delete_note_by_id(note_id)
        assert s.scalar(select(Note).where(Note.id == note_id)) is None
        assert s.scalars(select(Card)).first() is None


def test_update_values(db):
    with db.session() as s:
        deck, basic = _basic(s)
        service = NoteService(s, make_engine())
        note = service.create_note(deck.id, basic.id, {"Front": "Q", "Back": "A"})
        service.update_values(note, {"Front": "Q2"})
        assert note.values_by_field_name()["Front"] == "Q2"


def test_create_custom_note_type_and_generate(db):
    with db.session() as s:
        note_type = NoteTypeService(s).create_type(
            "MyType", ["A", "B"], [("Card 1", "{{A}}", "{{A}}<hr>{{B}}")]
        )
        assert note_type.id is not None
        assert len(note_type.fields) == 2 and len(note_type.templates) == 1
        deck = s.scalar(select(Deck).where(Deck.is_default.is_(True)))
        note = NoteService(s, make_engine()).create_note(deck.id, note_type.id, {"A": "x", "B": "y"})
        assert len(note.cards) == 1
