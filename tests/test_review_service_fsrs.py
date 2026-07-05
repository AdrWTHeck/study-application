"""ReviewService driven by the FSRS engine (default scheduler integration)."""
from sqlalchemy import func, select

from data.models import Card, Deck, NoteType, ReviewLog
from domain.cards.review_service import ReviewService
from domain.notes.note_service import NoteService
from domain.srs import FsrsEngine, Rating


def _seed_cards(session, count):
    deck = session.scalar(select(Deck).where(Deck.is_default.is_(True)))
    basic = session.scalar(select(NoteType).where(NoteType.name == "Basic"))
    notes = NoteService(session, FsrsEngine())
    for i in range(count):
        notes.create_note(deck.id, basic.id, {"Front": f"Q{i}", "Back": f"A{i}"})
    return deck


def test_fsrs_queue_includes_new_cards(db):
    with db.session() as s:
        deck = _seed_cards(s, 3)
        queue = ReviewService(s, FsrsEngine()).build_queue(deck.id)
    assert len(queue) == 3


def test_fsrs_answer_updates_card_and_writes_log(db):
    with db.session() as s:
        deck = _seed_cards(s, 1)
        review = ReviewService(s, FsrsEngine())
        card = review.build_queue(deck.id)[0]
        review.answer(card, Rating.GOOD)

        assert card.srs_state in ("learning", "review")
        assert card.stability is not None and card.difficulty is not None

        log = s.scalars(select(ReviewLog)).first()
        assert log.scheduler_name == "fsrs"
        assert log.new_stability is not None
        assert s.scalar(select(func.count()).select_from(ReviewLog)) == 1


def test_fsrs_again_keeps_card_in_queue_soon(db):
    with db.session() as s:
        deck = _seed_cards(s, 1)
        review = ReviewService(s, FsrsEngine())
        card = review.build_queue(deck.id)[0]
        review.answer(card, Rating.AGAIN)
        # An "Again" on a fresh card schedules it again shortly (still learning).
        assert card.srs_state in ("learning", "relearning")
