from sqlalchemy import select

from app.context import AppContext
from core.settings import Settings
from data.models import Deck, Note, NoteType
from domain.notes.note_service import NoteService
from domain.srs import make_engine
from ui.views.cards_view import CardsView
from ui.views.note_form import AddNoteDialog
from ui.views.note_type_editor import NoteTypeEditor
from ui.views.notes_view import NotesView


def _ctx(db, tmp_path, mode="accessibility") -> AppContext:
    settings = Settings.load(tmp_path / "s.json")
    settings.set("mode", mode)
    return AppContext(db=db, engine=make_engine(), settings=settings, tts=None)


def _seed_note(db) -> tuple[int, str]:
    with db.session() as s:
        deck = s.scalar(select(Deck).where(Deck.is_default.is_(True)))
        basic = s.scalar(select(NoteType).where(NoteType.name == "Basic"))
        NoteService(s, make_engine()).create_note(deck.id, basic.id, {"Front": "Q", "Back": "A"})
        return deck.id, deck.name


def test_notes_view_lists_notes(qapp, db, tmp_path):
    deck_id, name = _seed_note(db)
    view = NotesView(_ctx(db, tmp_path))
    view.open_deck(deck_id, name)
    assert view._list_layout.count() >= 1
    assert len(view._checks) == 1


def test_notes_view_search_filters(qapp, db, app_context, sample_deck):
    view = NotesView(app_context)
    with db.session() as s:
        from data.models import Deck
        name = s.get(Deck, sample_deck).name
    view.open_deck(sample_deck, name)
    assert len(view._checks) == 5  # all five sample notes

    view._search.setText("mitochondria")
    assert len(view._checks) == 1  # only the matching note

    view._search.setText("zzz-none")
    assert len(view._checks) == 0


def test_notes_view_state_filter_new(qapp, db, app_context, sample_deck):
    view = NotesView(app_context)
    with db.session() as s:
        from data.models import Deck
        name = s.get(Deck, sample_deck).name
    view.open_deck(sample_deck, name)
    # All sample cards are New, so the New filter keeps all 5; Review keeps 0.
    new_idx = [lbl for lbl, _ in __import__(
        "ui.views.notes_view", fromlist=["_NOTE_FILTERS"]
    )._NOTE_FILTERS].index("New")
    view._filter.setCurrentIndex(new_idx)
    assert len(view._checks) == 5
    review_idx = [lbl for lbl, _ in __import__(
        "ui.views.notes_view", fromlist=["_NOTE_FILTERS"]
    )._NOTE_FILTERS].index("Review")
    view._filter.setCurrentIndex(review_idx)
    assert len(view._checks) == 0


def test_edit_note_dialog_updates_value(qapp, db, tmp_path):
    _seed_note(db)
    with db.session() as s:
        note_id = s.scalars(select(Note)).first().id
    dialog = AddNoteDialog(_ctx(db, tmp_path), note_id=note_id)
    assert dialog._field_inputs["Front"].toPlainText() == "Q"  # prefilled
    dialog._field_inputs["Front"].setPlainText("Updated")
    dialog._save()
    with db.session() as s:
        assert s.scalars(select(Note)).first().values_by_field_name()["Front"] == "Updated"


def test_note_type_editor_creates_type(qapp, db, tmp_path):
    dialog = NoteTypeEditor(_ctx(db, tmp_path))
    dialog.name_input.setText("Custom")
    dialog.fields_input.setPlainText("A\nB")
    dialog.front_input.setPlainText("{{A}}")
    dialog.back_input.setPlainText("{{A}}<hr>{{B}}")
    dialog._save()
    with db.session() as s:
        assert s.scalar(select(NoteType).where(NoteType.name == "Custom")) is not None


def test_new_note_type_action_is_advanced_only(qapp, db, tmp_path):
    accessibility = CardsView(_ctx(db, tmp_path, mode="accessibility"))
    advanced = CardsView(_ctx(db, tmp_path, mode="advanced"))
    assert accessibility._new_type_action.isVisible() is False
    assert advanced._new_type_action.isVisible() is True


def test_embedded_notes_view_hides_header(qapp, db, tmp_path):
    standalone = NotesView(_ctx(db, tmp_path))
    embedded = NotesView(_ctx(db, tmp_path), embedded=True)
    assert standalone._header_host.isVisibleTo(standalone) is True
    assert embedded._header_host.isVisibleTo(embedded) is False
