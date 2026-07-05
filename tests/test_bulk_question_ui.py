"""Headless UI tests for the bulk-add-questions dialog."""
from sqlalchemy import func, select

from data.models import Question
from data.models.testing import MCQ, TRUE_FALSE
from ui.views.bulk_question_dialog import BulkQuestionDialog


def test_preview_then_create_short_answers(qapp, db, app_context, sample_test_deck):
    dlg = BulkQuestionDialog(app_context)
    names = [name for _, name in dlg._decks]
    dlg.deck_combo.setCurrentIndex(names.index("Biology Quiz"))
    dlg.mode_combo.setCurrentIndex(0)  # short answer
    dlg.text.setPlainText("New question one? | answer one\nNew question two? | answer two")

    dlg._preview()
    assert dlg._stack.currentIndex() == 1
    assert len(dlg._rows) == 2

    dlg._create()
    assert dlg.created_count == 2
    with db.session() as s:
        count = s.scalar(
            select(func.count()).select_from(Question).where(Question.deck_id == sample_test_deck)
        )
    # 3 seeded questions + 2 new = 5.
    assert count == 5


def test_duplicate_unticked_and_skipped(qapp, db, app_context, sample_test_deck):
    dlg = BulkQuestionDialog(app_context)
    names = [name for _, name in dlg._decks]
    dlg.deck_combo.setCurrentIndex(names.index("Biology Quiz"))
    dlg.mode_combo.setCurrentIndex(0)
    dlg.text.setPlainText(
        "Which organelle is the powerhouse of the cell? | Mitochondria\n"
        "A brand new prompt? | yes"
    )
    dlg._preview()
    states = [(check.isChecked(), draft.duplicate) for check, draft in dlg._rows]
    assert states[0] == (False, True)
    assert states[1] == (True, False)
    dlg._create()
    assert dlg.created_count == 1


def test_mcq_mode_creates_mcq_questions(qapp, db, app_context, sample_test_deck):
    dlg = BulkQuestionDialog(app_context)
    names = [name for _, name in dlg._decks]
    dlg.deck_combo.setCurrentIndex(names.index("Biology Quiz"))
    dlg.mode_combo.setCurrentIndex(1)  # mcq
    dlg.text.setPlainText("Sky colour? | *Blue | Green | Red")
    dlg._preview()
    assert len(dlg._rows) == 1
    dlg._create()
    with db.session() as s:
        q = s.scalars(
            select(Question).where(
                Question.deck_id == sample_test_deck,
                Question.type == MCQ,
                Question.prompt == "Sky colour?",
            )
        ).first()
        assert q is not None
        correct = [o.text for o in q.options if o.is_correct]
    assert correct == ["Blue"]


def test_create_into_new_test_deck(qapp, db, app_context):
    from domain.decks.deck_service import DeckService

    dlg = BulkQuestionDialog(app_context)
    dlg.new_deck_name.setText("Fresh Quiz")
    dlg.mode_combo.setCurrentIndex(2)  # true/false
    dlg.text.setPlainText("Water is wet. | true\nFire is cold. | false")
    dlg._preview()
    dlg._create()
    assert dlg.created_count == 2
    with db.session() as s:
        decks = [d.name for d in DeckService(s).decks.by_type("test")]
        assert "Fresh Quiz" in decks
        tf = s.scalars(select(Question).where(Question.type == TRUE_FALSE)).all()
    assert len(tf) == 2
