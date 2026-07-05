"""Tests for the FSRS scheduling engine (default scheduler)."""
from datetime import timedelta

from core.clock import now
from domain.srs import FsrsEngine, make_engine
from domain.srs.preview import format_interval, preview_intervals
from domain.srs.srs_base import LEARNING, NEW, RELEARNING, REVIEW, CardState, Rating


def test_engine_name_and_default():
    assert FsrsEngine().name == "fsrs"
    assert make_engine().name == "fsrs"          # FSRS is the default
    # FSRS is the only engine; a stale/legacy value falls back to it, not a crash.
    assert make_engine("sm2").name == "fsrs"


def test_new_state_is_fresh():
    moment = now()
    state = FsrsEngine().new_state(moment)
    assert state.state == NEW
    assert state.due == moment
    assert state.stability is None and state.difficulty is None


def test_first_review_seeds_memory_state():
    engine = FsrsEngine()
    moment = now()
    new = engine.review(engine.new_state(moment), Rating.GOOD, moment)
    assert new.state in (LEARNING, REVIEW)
    assert new.stability is not None and new.difficulty is not None
    assert new.due is not None and new.due > moment
    assert new.reps == 1


def test_ratings_produce_increasing_intervals():
    engine = FsrsEngine()
    moment = now()
    fresh = engine.new_state(moment)
    dues = {}
    for rating in (Rating.AGAIN, Rating.HARD, Rating.GOOD, Rating.EASY):
        result = engine.review(fresh.copy(), rating, moment)
        dues[rating] = result.due
    # Harder ratings come due sooner than easier ones.
    assert dues[Rating.AGAIN] <= dues[Rating.HARD] <= dues[Rating.GOOD] <= dues[Rating.EASY]


def test_migrated_sm2_card_is_safe_initialized():
    """A review-state card with no stability/difficulty (from SM-2) must not crash."""
    engine = FsrsEngine()
    moment = now()
    sm2_card = CardState(
        state=REVIEW,
        due=moment,
        last_review=moment - timedelta(days=10),
        reps=5,
        lapses=1,
        ease_factor=2.5,
        interval_days=10.0,
        stability=None,
        difficulty=None,
    )
    new = engine.review(sm2_card, Rating.GOOD, moment)
    assert new.stability is not None and new.difficulty is not None
    assert new.reps == 6          # progress preserved + incremented
    assert new.lapses == 1
    assert new.due > moment


def test_lapse_on_review_card_again():
    engine = FsrsEngine()
    moment = now()
    review_card = CardState(
        state=REVIEW, due=moment, last_review=moment - timedelta(days=5),
        reps=3, lapses=0, interval_days=5.0, stability=8.0, difficulty=5.0,
    )
    new = engine.review(review_card, Rating.AGAIN, moment)
    assert new.state == RELEARNING
    assert new.lapses == 1


def test_round_trips_due_as_naive_utc():
    engine = FsrsEngine()
    moment = now()
    new = engine.review(engine.new_state(moment), Rating.GOOD, moment)
    # Stored datetimes must be naive (tzinfo stripped at the FSRS boundary).
    assert new.due.tzinfo is None
    assert new.last_review is None or new.last_review.tzinfo is None


def test_format_interval_buckets():
    assert format_interval(timedelta(seconds=30)) == "<1m"
    assert format_interval(timedelta(minutes=6)) == "6m"
    assert format_interval(timedelta(hours=2)) == "2h"
    assert format_interval(timedelta(days=4)) == "4d"
    assert format_interval(timedelta(days=90)) == "3mo"
    assert format_interval(timedelta(days=730)) == "2y"


def test_preview_intervals_covers_all_ratings_without_mutation(db):
    """The rating-button hints must not touch the card's scheduling."""
    from data.models import Card, Deck, Note, NoteType

    engine = FsrsEngine()
    with db.session() as s:
        deck = s.query(Deck).first()
        ntype = s.query(NoteType).first()
        note = Note(deck_id=deck.id, note_type_id=ntype.id)
        s.add(note)
        s.flush()
        card = Card(note_id=note.id, deck_id=deck.id)
        s.add(card)
        s.flush()

        before = (card.srs_state, card.due, card.reps, card.stability)
        hints = preview_intervals(engine, card, at=now())
        after = (card.srs_state, card.due, card.reps, card.stability)

        assert set(hints) == {Rating.AGAIN, Rating.HARD, Rating.GOOD, Rating.EASY}
        assert all(hints.values())  # every rating has a non-empty hint
        assert before == after      # pure preview — nothing scheduled
