from sqlalchemy import select

from data.models import Deck, NoteType
from data.models.testing import SHORT_ANSWER
from domain.decks.deck_service import DeckService
from domain.notes.note_service import NoteService
from domain.srs import make_engine
from domain.testing.question_service import QuestionService


def _test_deck(session) -> int:
    return DeckService(session).create("Quiz", deck_type="test").id


def test_create_mcq(db):
    with db.session() as s:
        deck_id = _test_deck(s)
        q = QuestionService(s).create_mcq(deck_id, "Q?", [("A", True), ("B", False)])
        assert q.type == "mcq" and len(q.options) == 2
        assert [o.text for o in q.options if o.is_correct] == ["A"]


def test_create_true_false(db):
    with db.session() as s:
        deck_id = _test_deck(s)
        q = QuestionService(s).create_true_false(deck_id, "Sky is blue?", True)
        assert q.type == "true_false"
        assert [o.text for o in q.options if o.is_correct] == ["True"]


def test_create_short_answer(db):
    with db.session() as s:
        deck_id = _test_deck(s)
        q = QuestionService(s).create_text(deck_id, "Capital?", ["Paris"], SHORT_ANSWER)
        assert q.type == "short_answer"
        assert [a.accepted_text for a in q.answers] == ["Paris"]


def test_card_to_question_makes_labeled_draft(db):
    with db.session() as s:
        deck = s.scalar(select(Deck).where(Deck.is_default.is_(True)))
        basic = s.scalar(select(NoteType).where(NoteType.name == "Basic"))
        note = NoteService(s, make_engine()).create_note(
            deck.id, basic.id, {"Front": "Capital of France?", "Back": "Paris"}
        )
        card = note.cards[0]
        test_deck_id = _test_deck(s)
        q = QuestionService(s).card_to_question(card, test_deck_id)
        assert q.is_generated_draft is True
        assert q.source_card_id == card.id
        assert q.prompt == "Capital of France?"
        assert q.type == "short_answer"
        assert any(a.accepted_text == "Paris" for a in q.answers)


def test_confirm_and_delete(db):
    with db.session() as s:
        deck_id = _test_deck(s)
        svc = QuestionService(s)
        q = svc.create_text(deck_id, "Q", ["a"], SHORT_ANSWER, is_draft=True)
        svc.confirm_draft(q)
        assert q.is_generated_draft is False
        svc.delete(q)
        assert svc.questions.count_for_deck(deck_id) == 0
