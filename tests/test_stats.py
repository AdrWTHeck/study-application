from datetime import timedelta

from sqlalchemy import select

from core.clock import now
from data.models import Deck, NoteType, ReviewLog
from data.models.testing import SHORT_ANSWER
from domain.dashboard.stats_service import StatsService
from domain.decks.deck_service import DeckService
from domain.notes.note_service import NoteService
from domain.srs import make_engine
from domain.testing.question_service import QuestionService
from domain.testing.quiz_service import QuizService


def _card(session):
    deck = session.scalar(select(Deck).where(Deck.is_default.is_(True)))
    basic = session.scalar(select(NoteType).where(NoteType.name == "Basic"))
    note = NoteService(session, make_engine()).create_note(deck.id, basic.id, {"Front": "a", "Back": "1"})
    return note.cards[0]


def test_new_and_due_counts(db):
    with db.session() as s:
        _card(s)
        stats = StatsService(s)
        assert stats.new_count() == 1
        assert stats.due_count() == 0  # a brand-new card is not "due"


def test_retention_rate(db):
    with db.session() as s:
        card = _card(s)
        s.add(ReviewLog(card_id=card.id, rating=3, prev_state="review", new_state="review"))
        s.add(ReviewLog(card_id=card.id, rating=4, prev_state="review", new_state="review"))
        s.add(ReviewLog(card_id=card.id, rating=1, prev_state="review", new_state="relearning"))
        s.flush()
        rate, n = StatsService(s).retention_rate()
        assert n == 3 and rate == round(100 * 2 / 3, 1)


def test_retention_none_without_reviews(db):
    with db.session() as s:
        assert StatsService(s).retention_rate() == (None, 0)


def test_streak_counts_consecutive_days(db):
    with db.session() as s:
        card = _card(s)
        today = now()
        for offset in (0, 1, 2):
            s.add(ReviewLog(card_id=card.id, rating=3, prev_state="review", new_state="review",
                            reviewed_at=today - timedelta(days=offset)))
        s.flush()
        assert StatsService(s).streak() == 3


def test_streak_zero_when_stale(db):
    with db.session() as s:
        card = _card(s)
        s.add(ReviewLog(card_id=card.id, rating=3, prev_state="review", new_state="review",
                        reviewed_at=now() - timedelta(days=5)))
        s.flush()
        assert StatsService(s).streak() == 0


def test_test_summaries_track_best(db):
    with db.session() as s:
        deck = DeckService(s).create("Quiz", deck_type="test")
        q = QuestionService(s).create_text(deck.id, "Cap?", ["Paris"], SHORT_ANSWER)
        quiz = QuizService(s)
        s1 = quiz.start(deck.id); quiz.record(s1, q, "x"); quiz.finish(s1)        # 0%
        s2 = quiz.start(deck.id); quiz.record(s2, q, "Paris"); quiz.finish(s2)    # 100%
        summary = next(x for x in StatsService(s).test_summaries() if x.deck == "Quiz")
        assert summary.best == 100.0 and summary.attempts == 2 and summary.last == 100.0
