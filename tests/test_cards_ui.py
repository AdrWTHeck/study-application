from sqlalchemy import select

from app.context import AppContext
from core.settings import Settings
from data.models import Card, Deck, NoteType
from domain.notes.note_service import NoteService
from domain.srs import Rating, Sm2Engine
from ui.views.cards_view import CardsView
from ui.views.note_form import AddNoteDialog
from ui.views.review_view import ReviewView


def _ctx(db, tmp_path) -> AppContext:
    return AppContext(db=db, engine=Sm2Engine(), settings=Settings.load(tmp_path / "s.json"), tts=None)


def _add_basic_note(db):
    with db.session() as s:
        deck = s.scalar(select(Deck).where(Deck.is_default.is_(True)))
        basic = s.scalar(select(NoteType).where(NoteType.name == "Basic"))
        NoteService(s, Sm2Engine()).create_note(deck.id, basic.id, {"Front": "Q", "Back": "A"})
        return deck.id


def test_cards_view_lists_default_deck(qapp, db, tmp_path):
    view = CardsView(_ctx(db, tmp_path))
    assert view._list_layout.count() >= 1  # at least the Default deck row


def test_review_view_builds_queue_and_answers(qapp, db, tmp_path):
    deck_id = _add_basic_note(db)
    review = ReviewView(_ctx(db, tmp_path))
    review.start(deck_id)
    assert len(review._queue) == 1
    review._reveal()
    assert review._revealed is True
    review._rate(Rating.GOOD)
    review._finish()
    with db.session() as s:
        card = s.scalars(select(Card)).first()
    assert card.srs_state == "learning"


def test_add_note_dialog_creates_card(qapp, db, tmp_path):
    dialog = AddNoteDialog(_ctx(db, tmp_path))
    names = [name for _, name in dialog._types]
    dialog.type_combo.setCurrentIndex(names.index("Basic"))
    for editor in dialog._field_inputs.values():
        editor.setPlainText("X")
    dialog._save()
    with db.session() as s:
        assert s.scalars(select(Card)).first() is not None
