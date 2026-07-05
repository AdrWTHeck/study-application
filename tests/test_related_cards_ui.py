"""TestsView: the post-quiz 'Related cards to review' section + opt-in nudge."""
from datetime import timedelta

from PyQt6.QtWidgets import QMessageBox
from sqlalchemy import select

from app.context import AppContext
from core.clock import now
from core.settings import Settings
from data.models import Card, Deck, NoteType
from data.models.testing import SHORT_ANSWER
from domain.decks.deck_service import DeckService
from domain.notes.note_service import NoteService
from domain.srs import make_engine
from domain.srs.srs_base import REVIEW
from domain.testing.question_service import QuestionService
from ui.views.tests_view import TestsView


def _ctx(db, tmp_path) -> AppContext:
    return AppContext(
        db=db, engine=make_engine(),
        settings=Settings.load(tmp_path / "s.json"), tts=None, dictionary=None,
    )


def _setup(db) -> tuple[int, str]:
    """A card note about photosynthesis + a test question that shares its terms."""
    with db.session() as s:
        deck = s.scalar(select(Deck).where(Deck.is_default.is_(True)))
        basic = s.scalar(select(NoteType).where(NoteType.name == "Basic"))
        NoteService(s, make_engine()).create_note(
            deck.id, basic.id, {"Front": "Photosynthesis", "Back": "Occurs in the chloroplast"})
        td = DeckService(s).create("Bio quiz", deck_type="test")
        QuestionService(s).create_text(td.id, "Define photosynthesis", ["light reaction"], SHORT_ANSWER)
        return td.id, td.name


def test_results_show_related_section_on_a_miss(qapp, db, tmp_path):
    deck_id, name = _setup(db)
    view = TestsView(_ctx(db, tmp_path))
    view.show()  # so isVisible() reflects shown state under the offscreen platform
    view._take_test(deck_id, name)
    view._submit("no clue")                       # wrong -> struggle
    assert view._stack.currentIndex() == 3        # results page
    assert view._related_header.isVisible()
    assert view._related_list[1].count() > 0      # intro + at least one group
    assert view._related_card_ids                 # a related card was found
    assert view._nudge_btn.isVisible()
    view._close_session()


def test_related_section_hidden_when_disabled(qapp, db, tmp_path):
    deck_id, name = _setup(db)
    ctx = _ctx(db, tmp_path)
    ctx.settings.set("related_cards_enabled", False)
    view = TestsView(ctx)
    view._take_test(deck_id, name)
    view._submit("no clue")
    assert not view._related_header.isVisible()
    assert not view._nudge_btn.isVisible()
    assert view._related_card_ids == []
    view._close_session()


def test_perfect_score_shows_no_related(qapp, db, tmp_path):
    deck_id, name = _setup(db)
    view = TestsView(_ctx(db, tmp_path))
    view._take_test(deck_id, name)
    view._submit("light reaction")                # correct
    assert not view._related_header.isVisible()
    assert view._related_card_ids == []
    view._close_session()


def test_nudge_reschedules_only_on_confirmation(qapp, db, tmp_path, monkeypatch):
    deck_id, name = _setup(db)
    # push the related card's due into the future so a nudge has a visible effect.
    with db.session() as s:
        card = s.scalars(select(Card)).first()
        card.srs_state = REVIEW
        card.due = now() + timedelta(days=9)
        card_id = card.id

    view = TestsView(_ctx(db, tmp_path))
    view._take_test(deck_id, name)
    view._submit("no clue")
    assert view._related_card_ids

    # Decline first: nothing should change.
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    view._nudge_related()
    with db.session() as s:
        assert s.get(Card, card_id).due > now()

    # Confirm: the related card is pulled forward.
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    view._nudge_related()
    with db.session() as s:
        assert s.get(Card, card_id).due <= now()
    assert not view._nudge_btn.isEnabled()        # consumed after use
    view._close_session()
