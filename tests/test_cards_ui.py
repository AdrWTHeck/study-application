from PyQt6.QtCore import Qt
from sqlalchemy import select

from app.context import AppContext
from core.settings import Settings
from data.models import Card, Deck, NoteType
from domain.decks.deck_service import DeckService
from domain.notes.note_service import NoteService
from domain.srs import Rating, make_engine
from ui.views.cards_view import CardsView
from ui.views.note_form import AddNoteDialog
from ui.views.review_view import ReviewView


def _ctx(db, tmp_path) -> AppContext:
    return AppContext(db=db, engine=make_engine(), settings=Settings.load(tmp_path / "s.json"), tts=None)


def _add_basic_note(db):
    with db.session() as s:
        deck = s.scalar(select(Deck).where(Deck.is_default.is_(True)))
        basic = s.scalar(select(NoteType).where(NoteType.name == "Basic"))
        NoteService(s, make_engine()).create_note(deck.id, basic.id, {"Front": "Q", "Back": "A"})
        return deck.id


def _tree_paths(view) -> list[str]:
    """Collect all full paths stored in the deck tree (depth-first)."""
    paths: list[str] = []

    def _walk(item):
        stored = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if stored:
            paths.append(stored)
        for i in range(item.childCount()):
            _walk(item.child(i))

    for i in range(view._deck_tree.topLevelItemCount()):
        _walk(view._deck_tree.topLevelItem(i))
    return paths


def test_cards_view_lists_default_deck(qapp, db, tmp_path):
    view = CardsView(_ctx(db, tmp_path))
    assert view._deck_tree.topLevelItemCount() >= 1  # at least the Default deck


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


def test_review_respects_new_cards_per_session_setting(qapp, db, app_context, sample_deck):
    app_context.settings.set("new_cards_per_session", 2)
    review = ReviewView(app_context)
    review.start(sample_deck)
    assert len(review._queue) == 2
    review._finish()


def test_review_counter_and_interval_hints(qapp, db, app_context, sample_deck):
    review = ReviewView(app_context)
    review.start(sample_deck, deck_name="Biology")
    assert review._deck_label.text() == "Biology"
    assert review._progress.text() == f"1 of {len(review._queue)}"
    card = review._queue[0]
    due_before = card.due
    review._reveal()
    hints = [b._hint.text() for b in review._rating_buttons]
    assert all(hints)                      # every rating shows a predicted interval
    assert len(set(hints)) > 1             # and they differ across ratings
    assert card.due == due_before          # preview never touches scheduling
    review._finish()


def test_review_summary_shows_rating_counts(qapp, db, app_context, sample_deck):
    app_context.settings.set("new_cards_per_session", 1)
    review = ReviewView(app_context)
    review.start(sample_deck)
    review._reveal()
    review._rate(Rating.EASY)              # EASY schedules far out — no requeue
    assert review._summary.isVisibleTo(review)
    assert review._summary_reviewed.text() == "1"
    assert review._summary_pills[Rating.EASY].text() == "Easy 1"
    assert review._summary_pills[Rating.AGAIN].text() == "Again 0"
    review._finish()


def test_add_note_dialog_creates_card(qapp, db, tmp_path):
    dialog = AddNoteDialog(_ctx(db, tmp_path))
    names = [name for _, name in dialog._types]
    dialog.type_combo.setCurrentIndex(names.index("Basic"))
    for editor in dialog._field_inputs.values():
        editor.setPlainText("X")
    dialog._save()
    with db.session() as s:
        assert s.scalars(select(Card)).first() is not None


def test_deck_search_filters_rows(qapp, db, app_context, sample_deck):
    view = CardsView(app_context)
    # Default + Biology deck both visible
    assert view._deck_tree.topLevelItemCount() >= 2
    view._search.setText("Biology")
    # Only "Biology" matches
    assert view._deck_tree.topLevelItemCount() == 1
    view._search.setText("zzz-no-match")
    # Tree explicitly hidden; label explicitly shown
    assert view._deck_tree.isHidden()
    assert not view._no_decks_label.isHidden()


def test_deck_tree_nested_deck_creates_parent_node(qapp, db, app_context):
    """Decks with '::' names produce a collapsible hierarchy in the tree."""
    with db.session() as s:
        DeckService(s).create("Science::Biology")
    view = CardsView(app_context)
    paths = _tree_paths(view)
    assert "Science" in paths
    assert "Science::Biology" in paths
    # Science should be a top-level item with Biology as its child
    for i in range(view._deck_tree.topLevelItemCount()):
        top = view._deck_tree.topLevelItem(i)
        if top.data(0, Qt.ItemDataRole.UserRole + 1) == "Science":
            assert top.childCount() >= 1


def test_selecting_deck_populates_detail_pane(qapp, db, app_context, sample_deck):
    from data.models import Deck

    view = CardsView(app_context)
    with db.session() as s:
        name = s.get(Deck, sample_deck).name
    assert view._reselect([sample_deck])
    assert view._detail_title.text() == name
    assert view._detail.isVisibleTo(view)
    # sample_deck has 5 new cards → badges show them.
    assert view._detail_badges._labels["new"].text() == "5 new"
    # Embedded notes browser follows the selection.
    assert view._notes._deck_id == sample_deck


def test_review_action_card_starts_review(qapp, db, app_context, sample_deck):
    from ui.views.cards_view import _REVIEW_PAGE

    view = CardsView(app_context)
    assert view._reselect([sample_deck])
    view._review_card.click()
    assert view._stack.currentIndex() == _REVIEW_PAGE
    assert len(view._review._queue) > 0
    view._review._finish()
    assert view._stack.currentIndex() == 0


def test_quick_pass_action_card_switches_page(qapp, db, app_context, sample_deck):
    from ui.views.cards_view import _QUICK_PASS_PAGE

    view = CardsView(app_context)
    assert view._reselect([sample_deck])
    view._quick_pass_card.click()
    assert view._stack.currentIndex() == _QUICK_PASS_PAGE
    view._quick_pass.finished.emit()
    assert view._stack.currentIndex() == 0


def test_duplicate_deck_copies_cards(qapp, db, app_context, sample_deck, monkeypatch):
    from sqlalchemy import func

    from data.models import Deck, Note
    from PyQt6.QtWidgets import QMessageBox

    # _duplicate_deck shows a blocking confirmation dialog on success; stub it
    # out so the test doesn't hang waiting for a click that will never come.
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))

    view = CardsView(app_context)
    with db.session() as s:
        name = s.get(Deck, sample_deck).name
    view._duplicate_deck(sample_deck, name)
    with db.session() as s:
        copy = s.scalar(select(Deck).where(Deck.name == f"{name} (copy)"))
        assert copy is not None
        count = s.scalar(select(func.count()).select_from(Note).where(Note.deck_id == copy.id))
    assert count == 5  # sample_deck has 5 notes
