from sqlalchemy import select

from app.context import AppContext
from core.settings import Settings
from data.models import Deck, NoteType
from domain.notes.flag_service import FlagService
from domain.notes.note_service import NoteService
from domain.srs import make_engine
from ui.views.flag_editor import FlagAssignDialog, FlagEditorDialog
from ui.views.notes_view import NotesView


def _ctx(db, tmp_path) -> AppContext:
    return AppContext(
        db=db, engine=make_engine(),
        settings=Settings.load(tmp_path / "s.json"), tts=None, dictionary=None,
    )


def _note(db):
    with db.session() as s:
        deck = s.scalar(select(Deck).where(Deck.is_default.is_(True)))
        basic = s.scalar(select(NoteType).where(NoteType.name == "Basic"))
        note = NoteService(s, make_engine()).create_note(deck.id, basic.id, {"Front": "a", "Back": "b"})
        return deck.id, deck.name, note.id


def test_flag_editor_lists_builtin_flags(qapp, db, tmp_path):
    dialog = FlagEditorDialog(_ctx(db, tmp_path))
    assert dialog._list.count() >= 4  # four built-in flags


def test_flag_assign_dialog_saves(qapp, db, tmp_path):
    _deck_id, _name, note_id = _note(db)
    dialog = FlagAssignDialog(_ctx(db, tmp_path), note_id)
    first_flag_id = next(iter(dialog._checks))
    dialog._checks[first_flag_id].setChecked(True)
    dialog._save()
    with db.session() as s:
        assert len(FlagService(s).flags_for_note(note_id)) == 1


def test_notes_view_renders_flag_chips(qapp, db, tmp_path):
    deck_id, name, note_id = _note(db)
    with db.session() as s:
        flags = FlagService(s).list_flags()
        FlagService(s).set_note_flags(note_id, [flags[0].id])
    view = NotesView(_ctx(db, tmp_path))
    view.open_deck(deck_id, name)
    assert view._list_layout.count() >= 1  # row built with chips, no error
