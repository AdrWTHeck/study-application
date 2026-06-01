from datetime import timedelta

from sqlalchemy import func, select

from core.clock import now
from data.models import Deck, NoteType, ReviewLog
from domain.cards.review_service import ReviewService
from domain.notes.note_service import NoteService
from domain.srs import Rating, Sm2Engine


def _seed_cards(session, count):
    deck = session.scalar(select(Deck).where(Deck.is_default.is_(True)))
    basic = session.scalar(select(NoteType).where(NoteType.name == "Basic"))
    notes = NoteService(session, Sm2Engine())
    for i in range(count):
        notes.create_note(deck.id, basic.id, {"Front": f"Q{i}", "Back": f"A{i}"})
    return deck


def test_queue_includes_new_cards(db):
    with db.session() as s:
        deck = _seed_cards(s, 3)
        queue = ReviewService(s, Sm2Engine()).build_queue(deck.id)
    assert len(queue) == 3


def test_new_limit_respected(db):
    with db.session() as s:
        deck = _seed_cards(s, 5)
        queue = ReviewService(s, Sm2Engine(), new_limit=2).build_queue(deck.id)
    assert len(queue) == 2


def test_answer_updates_state_and_writes_log(db):
    with db.session() as s:
        deck = _seed_cards(s, 1)
        review = ReviewService(s, Sm2Engine())
        card = review.build_queue(deck.id)[0]
        review.answer(card, Rating.GOOD)
        assert card.srs_state == "learning"
        assert s.scalar(select(func.count()).select_from(ReviewLog)) == 1


def test_overdue_review_card_requeues(db):
    with db.session() as s:
        deck = _seed_cards(s, 1)
        review = ReviewService(s, Sm2Engine())
        card = review.build_queue(deck.id)[0]
        review.answer(card, Rating.GOOD)   # learning step 2
        review.answer(card, Rating.GOOD)   # graduate to review (+1 day)
        assert card.srs_state == "review"
        card.due = now() - timedelta(days=1)
        s.flush()
        assert card in review.build_queue(deck.id)
