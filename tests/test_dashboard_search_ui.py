from sqlalchemy import select

from app.context import AppContext
from app.navigation import Destination
from core.settings import Settings
from data.models import Deck, NoteType
from domain.notes.note_service import NoteService
from domain.srs import make_engine
from ui.views.dashboard_view import DashboardView
from ui.views.search_view import SearchView


def _ctx(db, tmp_path) -> AppContext:
    return AppContext(
        db=db, engine=make_engine(),
        settings=Settings.load(tmp_path / "s.json"), tts=None, dictionary=None,
    )


def test_dashboard_builds_and_quick_action_navigates(qapp, db, tmp_path):
    seen = []
    view = DashboardView(_ctx(db, tmp_path), navigate=seen.append)
    assert view._layout.count() > 0  # sections rendered
    view._go(Destination.CARDS)
    assert seen == [Destination.CARDS]


def test_search_view_finds_results(qapp, db, tmp_path):
    with db.session() as s:
        deck = s.scalar(select(Deck).where(Deck.is_default.is_(True)))
        basic = s.scalar(select(NoteType).where(NoteType.name == "Basic"))
        NoteService(s, make_engine()).create_note(deck.id, basic.id, {"Front": "Photosynthesis", "Back": "x"})
    view = SearchView(_ctx(db, tmp_path))
    view._input.setText("photosynthesis")
    view._run()
    assert view._results_layout.count() >= 1


def test_search_empty_query_no_results(qapp, db, tmp_path):
    view = SearchView(_ctx(db, tmp_path))
    view._input.setText("")
    view._run()
    assert view._results_layout.count() == 0


def test_search_focus_does_not_raise(qapp, db, tmp_path):
    SearchView(_ctx(db, tmp_path)).focus_search()
