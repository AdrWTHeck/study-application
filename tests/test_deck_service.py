from sqlalchemy import select

from data.models import Deck, NoteType
from domain.decks.deck_service import DeckService
from domain.notes.note_service import NoteService
from domain.srs import make_engine


def test_create_and_list(db):
    with db.session() as s:
        svc = DeckService(s)
        svc.create("French")
        names = {summary.deck.name for summary in svc.list_summaries()}
    assert {"French", "Default"} <= names


def test_counts_reflect_new_cards(db):
    with db.session() as s:
        deck = s.scalar(select(Deck).where(Deck.is_default.is_(True)))
        basic = s.scalar(select(NoteType).where(NoteType.name == "Basic"))
        notes = NoteService(s, make_engine())
        notes.create_note(deck.id, basic.id, {"Front": "Q", "Back": "A"})
        notes.create_note(deck.id, basic.id, {"Front": "Q2", "Back": "A2"})
        summary = next(x for x in DeckService(s).list_summaries() if x.deck.id == deck.id)
    assert summary.new == 2 and summary.total == 2


def test_favorite_and_rename(db):
    with db.session() as s:
        svc = DeckService(s)
        deck = svc.create("Temp")
        svc.set_favorite(deck.id, True)
        svc.rename(deck.id, "Renamed")
        assert svc.decks.get(deck.id).is_favorite is True
        assert svc.decks.get(deck.id).name == "Renamed"


def test_delete(db):
    with db.session() as s:
        svc = DeckService(s)
        deck = svc.create("Temp")
        deck_id = deck.id
        svc.delete(deck_id)
        assert svc.decks.get(deck_id) is None


def test_set_color(db):
    with db.session() as s:
        svc = DeckService(s)
        deck = svc.create("Colorful")
        svc.set_color(deck.id, "#ff0000")
        assert svc.decks.get(deck.id).color == "#ff0000"


def test_set_tags(db):
    with db.session() as s:
        svc = DeckService(s)
        deck = svc.create("Tagged")
        svc.set_tags(deck.id, ["math", "exam"])
        assert {t.name for t in svc.decks.get(deck.id).tags} == {"math", "exam"}
