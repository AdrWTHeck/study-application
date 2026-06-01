from sqlalchemy import func, select

from data.models import Deck, NoteType
from data.seed import seed_defaults


def test_seed_creates_builtin_note_types(db):
    with db.session() as s:
        names = {nt.name for nt in s.scalars(select(NoteType))}
    assert {"Basic", "Basic (and reversed)", "Cloze"} <= names


def test_seed_creates_default_deck(db):
    with db.session() as s:
        deck = s.scalar(select(Deck).where(Deck.is_default.is_(True)))
    assert deck is not None and deck.deck_type == "card"


def test_seed_is_idempotent(db):
    seed_defaults(db)
    with db.session() as s:
        assert s.scalar(select(func.count()).select_from(NoteType)) == 3
