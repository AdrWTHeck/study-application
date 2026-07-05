from sqlalchemy import select

from data.models import Deck, NoteFlag, NoteType
from domain.notes.flag_service import FlagService
from domain.notes.note_service import NoteService
from domain.srs import make_engine


def _note(session):
    deck = session.scalar(select(Deck).where(Deck.is_default.is_(True)))
    basic = session.scalar(select(NoteType).where(NoteType.name == "Basic"))
    return NoteService(session, make_engine()).create_note(deck.id, basic.id, {"Front": "a", "Back": "b"})


def test_default_flags_seeded(db):
    with db.session() as s:
        names = {f.name for f in FlagService(s).list_flags()}
    assert {"Incomplete", "Confusing definition", "Needs example", "Wrong"} <= names


def test_create_update_delete_flag(db):
    with db.session() as s:
        svc = FlagService(s)
        flag = svc.create_flag("Custom", "#123456")
        assert flag.id is not None and flag.color == "#123456"
        svc.update_flag(flag.id, name="Renamed", color="#000000")
        assert s.get(NoteFlag, flag.id).name == "Renamed"
        svc.delete_flag(flag.id)
        assert s.get(NoteFlag, flag.id) is None


def test_assign_and_read_note_flags(db):
    with db.session() as s:
        note = _note(s)
        svc = FlagService(s)
        flags = {f.name: f.id for f in svc.list_flags()}
        svc.set_note_flags(note.id, [flags["Incomplete"], flags["Wrong"]])
        assert {f.name for f in svc.flags_for_note(note.id)} == {"Incomplete", "Wrong"}


def test_notes_with_flag(db):
    with db.session() as s:
        note = _note(s)
        svc = FlagService(s)
        incomplete = next(f for f in svc.list_flags() if f.name == "Incomplete")
        svc.set_note_flags(note.id, [incomplete.id])
        assert note.id in [n.id for n in svc.notes_with_flag(incomplete.id)]


def test_reassign_replaces_flags(db):
    with db.session() as s:
        note = _note(s)
        svc = FlagService(s)
        flags = {f.name: f.id for f in svc.list_flags()}
        svc.set_note_flags(note.id, [flags["Incomplete"]])
        svc.set_note_flags(note.id, [flags["Wrong"]])
        assert {f.name for f in svc.flags_for_note(note.id)} == {"Wrong"}
