from sqlalchemy import select

from app.context import AppContext
from core.settings import Settings
from data.models import Question
from data.models.testing import SHORT_ANSWER
from domain.decks.deck_service import DeckService
from domain.srs import make_engine
from domain.testing.question_service import QuestionService
from ui.views.question_editor import QuestionEditorDialog
from ui.views.tests_view import TestsView


def _ctx(db, tmp_path) -> AppContext:
    return AppContext(
        db=db, engine=make_engine(),
        settings=Settings.load(tmp_path / "s.json"), tts=None, dictionary=None,
    )


def _deck_with_questions(db) -> tuple[int, str]:
    with db.session() as s:
        deck = DeckService(s).create("Quiz", deck_type="test")
        qs = QuestionService(s)
        qs.create_mcq(deck.id, "2+2?", [("4", True), ("5", False)])
        qs.create_text(deck.id, "Capital of France?", ["Paris"], SHORT_ANSWER)
        return deck.id, deck.name


def test_browser_lists_test_decks(qapp, db, tmp_path):
    _deck_with_questions(db)
    view = TestsView(_ctx(db, tmp_path))
    assert len(view._test_tree.get_all_data()) >= 1


def test_take_test_answer_flow_and_score(qapp, db, tmp_path):
    deck_id, name = _deck_with_questions(db)
    view = TestsView(_ctx(db, tmp_path))
    view._take_test(deck_id, name)
    assert view._stack.currentIndex() == 2
    assert len(view._questions) == 2
    view._submit("4")        # mcq correct
    view._submit("Berlin")   # short answer wrong
    assert view._stack.currentIndex() == 3  # results
    assert view._quiz.session_score(view._last_session_id) == 50.0
    view._done_results()
    assert view._stack.currentIndex() == 0


def test_answer_options_are_full_buttons_with_shortcuts(qapp, db, tmp_path):
    from ui.components.answer_button import AnswerOptionButton

    deck_id, name = _deck_with_questions(db)
    view = TestsView(_ctx(db, tmp_path))
    view._take_test(deck_id, name)
    # First question is the MCQ with two options → two full-width answer buttons.
    buttons = view._answer_container.findChildren(AnswerOptionButton)
    assert len(buttons) == 2
    assert buttons[0].option_text == "4"
    assert "Answer 1: 4" == buttons[0].accessibleName()
    # A numeric shortcut exists per option.
    assert len(view._answer_shortcuts) >= 2
    view._close_session()


def test_retry_incorrect_starts_subset(qapp, db, tmp_path):
    deck_id, name = _deck_with_questions(db)
    view = TestsView(_ctx(db, tmp_path))
    view._take_test(deck_id, name)
    view._submit("4")        # correct
    view._submit("Berlin")   # wrong
    view._retry_incorrect()
    assert view._stack.currentIndex() == 2
    assert len(view._questions) == 1
    view._close_session()


def test_results_dashboard_builds_metric_cards(qapp, db, tmp_path):
    deck_id, name = _deck_with_questions(db)
    view = TestsView(_ctx(db, tmp_path))
    view._take_test(deck_id, name)
    view._submit("4")        # correct
    view._submit("Berlin")   # wrong
    assert view._stack.currentIndex() == 3  # results
    # The partitioned dashboard has several metric cards (not one text blob).
    cards = [
        view._results_grid.itemAt(i).widget()
        for i in range(view._results_grid.count())
    ]
    result_cards = [c for c in cards if c is not None and c.objectName() == "ResultCard"]
    assert len(result_cards) >= 3
    view._done_results()


def test_results_score_ring_and_insight(qapp, db, tmp_path):
    from PyQt6.QtWidgets import QWidget

    from ui.components.progress_ring import ProgressRing

    deck_id, name = _deck_with_questions(db)
    view = TestsView(_ctx(db, tmp_path))
    view._take_test(deck_id, name)
    view._submit("4")        # mcq correct
    view._submit("Berlin")   # short answer wrong
    # Score ring is present with an accessible percentage.
    rings = view.findChildren(ProgressRing)
    assert len(rings) == 1
    assert "50 percent" in rings[0].accessibleName()
    # A wrong short-answer makes it the weakest area → insight box shown.
    insights = [w for w in view.findChildren(QWidget)
                if w.objectName() == "InsightBox"]
    assert insights, "insight box expected when a question type has misses"
    # Correct/missed stat boxes carry the counts as text.
    stat_boxes = [w for w in view.findChildren(QWidget)
                  if w.objectName() == "ScoreStatBox"]
    assert {b.accessibleName() for b in stat_boxes} == {"1 correct", "1 missed"}
    assert view._retry_btn.text() == "Retry incorrect (1)"
    view._done_results()


def test_progress_ring_values_and_accessible_name(qapp):
    from PyQt6.QtGui import QColor

    from ui.components.progress_ring import ProgressRing

    ring = ProgressRing(diameter=120)
    for pct in (0, 50, 100):
        ring.set_value(pct, f"{pct} detail", QColor("#7fa76a"))
        assert ring._value_label.text() == f"{pct}%"
        assert f"Score {pct} percent" in ring.accessibleName()


def test_pie_chart_accessible_summary(qapp):
    from ui.components.pie_chart import PieChart

    pie = PieChart()
    pie.set_data([("Correct", 3, "#2e7d32"), ("Incorrect", 1, "#c62828")])
    summary = pie.accessibleName()
    assert "Correct 3" in summary and "Incorrect 1" in summary


def test_question_editor_creates_mcq(qapp, db, tmp_path):
    with db.session() as s:
        deck_id = DeckService(s).create("Q", deck_type="test").id
    dialog = QuestionEditorDialog(_ctx(db, tmp_path), deck_id)
    dialog.prompt.setPlainText("2+2?")
    dialog._option_rows[0][0].setText("4")
    dialog._option_rows[0][1].setChecked(True)
    dialog._option_rows[1][0].setText("5")
    dialog._save()
    with db.session() as s:
        assert s.scalars(select(Question)).first() is not None
