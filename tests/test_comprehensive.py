from app.context import AppContext
from core.settings import Settings
from data.models.testing import SHORT_ANSWER
from domain.decks.deck_service import DeckService
from domain.srs import make_engine
from domain.testing.question_service import QuestionService
from domain.testing.quiz_service import QuizService
from ui.views.comprehensive_test import ComprehensiveTestView, DeckMultiSelectDialog


def _ctx(db, tmp_path) -> AppContext:
    return AppContext(
        db=db, engine=make_engine(),
        settings=Settings.load(tmp_path / "s.json"), tts=None, dictionary=None,
    )


def _two_decks(db) -> tuple[int, int]:
    with db.session() as s:
        easy = DeckService(s).create("Easy", deck_type="test")
        hard = DeckService(s).create("Hard", deck_type="test")
        qs = QuestionService(s)
        qs.create_text(easy.id, "2+2?", ["4"], SHORT_ANSWER)
        qs.create_text(hard.id, "Capital of France?", ["Paris"], SHORT_ANSWER)
        return easy.id, hard.id


def test_gather_questions_across_decks(db):
    easy, hard = _two_decks(db)
    with db.session() as s:
        assert len(QuizService(s).gather_questions([easy, hard])) == 2


def test_breakdown_by_deck_weakest_first(db):
    easy, hard = _two_decks(db)
    with db.session() as s:
        quiz = QuizService(s)
        session = quiz.start(easy)
        for q in quiz.gather_questions([easy, hard]):
            quiz.record(session, q, "4" if q.deck_id == easy else "wrong")
        quiz.finish(session)
        breakdown = quiz.breakdown_by_deck(session.id)
        assert breakdown[0].deck == "Hard" and breakdown[0].pct == 0.0
        assert breakdown[-1].deck == "Easy" and breakdown[-1].pct == 100.0


def test_comprehensive_view_runs_to_results(qapp, db, tmp_path):
    easy, hard = _two_decks(db)
    view = ComprehensiveTestView(_ctx(db, tmp_path))
    view.start([easy, hard])
    assert len(view._questions) == 2
    view._submit("4")
    view._submit("Paris")
    assert "Comprehensive score" in view._results_heading.text()
    assert "Weakest area" in view._weakest.text()
    view._done()


def test_deck_multiselect_collects_ids(qapp, db, tmp_path):
    easy, hard = _two_decks(db)
    dialog = DeckMultiSelectDialog(_ctx(db, tmp_path))
    for check in dialog._checks.values():
        check.setChecked(True)
    dialog._accept()
    assert set(dialog.selected_ids) == {easy, hard}
