"""Related-cards feature: lookup, struggle policy, and the opt-in reschedule.

Note the structure of every test: writes happen in one ``db.session()`` block
(which commits on exit), THEN the FTS index is rebuilt and queried. The search
index is read over a separate SQLite connection, so it only sees committed data.
"""
from datetime import timedelta

from sqlalchemy import select

from core.clock import now
from data.models import Card, Deck, NoteType, QuestionResult
from data.models.testing import SHORT_ANSWER
from domain.decks.deck_service import DeckService
from domain.notes.note_service import NoteService
from domain.search.search_service import SearchService
from domain.srs import make_engine
from domain.srs.srs_base import REVIEW
from domain.testing.question_service import QuestionService
from domain.testing.quiz_service import QuizService
from domain.testing.related_cards import RelatedCardsService


def _default_deck(session) -> Deck:
    return session.scalar(select(Deck).where(Deck.is_default.is_(True)))


def _basic(session) -> NoteType:
    return session.scalar(select(NoteType).where(NoteType.name == "Basic"))


# -- 1. the lookup ----------------------------------------------------------


def test_related_notes_ranks_relevant_first_and_excludes_non_matches(db):
    with db.session() as s:
        deck, basic = _default_deck(s), _basic(s)
        ns = NoteService(s, make_engine())
        photo = ns.create_note(deck.id, basic.id,
                               {"Front": "Photosynthesis", "Back": "light reactions in the chloroplast"})
        mito = ns.create_note(deck.id, basic.id,
                              {"Front": "Mitochondria", "Back": "the powerhouse of the cell"})
        photo_id, mito_id = photo.id, mito.id

    search = SearchService(db)
    search.rebuild()
    ids = [hit.id for hit in search.related_notes("photosynthesis chloroplast")]

    assert ids and ids[0] == photo_id     # the relevant note ranks first
    assert mito_id not in ids             # an unrelated note doesn't match at all


def test_related_notes_can_exclude_ids(db):
    with db.session() as s:
        deck, basic = _default_deck(s), _basic(s)
        note = NoteService(s, make_engine()).create_note(
            deck.id, basic.id, {"Front": "Osmosis", "Back": "water diffusion across a membrane"})
        note_id = note.id

    search = SearchService(db)
    search.rebuild()
    assert search.related_notes("osmosis water") != []
    assert search.related_notes("osmosis water", exclude_note_ids=(note_id,)) == []


# -- 2. struggle policy + related lookup ------------------------------------


def test_suggestions_for_wrong_question(db):
    with db.session() as s:
        deck, basic = _default_deck(s), _basic(s)
        NoteService(s, make_engine()).create_note(
            deck.id, basic.id, {"Front": "Photosynthesis", "Back": "happens in the chloroplast"})
        td = DeckService(s).create("Bio quiz", deck_type="test")
        q = QuestionService(s).create_text(td.id, "Define photosynthesis", ["light reaction"], SHORT_ANSWER)
        quiz = QuizService(s)
        sess = quiz.start(td.id)
        quiz.record(sess, q, "no idea")  # wrong
        quiz.finish(sess)
        session_id = sess.id

    search = SearchService(db)
    search.rebuild()
    with db.session() as s:
        struggles = RelatedCardsService(s, search).suggestions_for_session(session_id)

    assert len(struggles) == 1
    assert struggles[0].miss_count == 1
    assert any("Photosynthesis" in rc.preview for rc in struggles[0].related)
    assert all(rc.card_ids for rc in struggles[0].related)  # every row has studyable cards


def test_source_card_is_first_and_flagged(db):
    with db.session() as s:
        deck, basic = _default_deck(s), _basic(s)
        note = NoteService(s, make_engine()).create_note(
            deck.id, basic.id, {"Front": "Capital of France", "Back": "Paris"})
        card = note.cards[0]
        td = DeckService(s).create("Geography", deck_type="test")
        # card->question bridge sets source_card_id
        q = QuestionService(s).card_to_question(card, td.id)
        quiz = QuizService(s)
        sess = quiz.start(td.id)
        quiz.record(sess, q, "wrong")
        quiz.finish(sess)
        session_id, note_id = sess.id, note.id

    search = SearchService(db)
    search.rebuild()
    with db.session() as s:
        struggles = RelatedCardsService(s, search).suggestions_for_session(session_id)

    first = struggles[0].related[0]
    assert first.is_source is True
    assert first.note_id == note_id


def test_perfect_score_has_no_suggestions(db):
    with db.session() as s:
        deck, basic = _default_deck(s), _basic(s)
        NoteService(s, make_engine()).create_note(
            deck.id, basic.id, {"Front": "Photosynthesis", "Back": "chloroplast"})
        td = DeckService(s).create("Bio", deck_type="test")
        q = QuestionService(s).create_text(td.id, "Define photosynthesis", ["light"], SHORT_ANSWER)
        quiz = QuizService(s)
        sess = quiz.start(td.id)
        quiz.record(sess, q, "light")  # correct
        quiz.finish(sess)
        session_id = sess.id

    search = SearchService(db)
    search.rebuild()
    with db.session() as s:
        assert RelatedCardsService(s, search).suggestions_for_session(session_id) == []


def test_low_score_threshold_flags_weak_but_correct_answer(db):
    # A deterministic 'correct but weak' result (score 85, is_correct True).
    with db.session() as s:
        deck, basic = _default_deck(s), _basic(s)
        NoteService(s, make_engine()).create_note(
            deck.id, basic.id, {"Front": "Osmosis", "Back": "water diffusion"})
        td = DeckService(s).create("Bio", deck_type="test")
        q = QuestionService(s).create_text(td.id, "What is osmosis", ["osmosis is water diffusion"], SHORT_ANSWER)
        sess = QuizService(s).start(td.id)
        s.add(QuestionResult(session_id=sess.id, question_id=q.id,
                             user_response="x", is_correct=True, score=85.0))
        s.flush()
        session_id = sess.id

    search = SearchService(db)
    search.rebuild()
    with db.session() as s:
        default = RelatedCardsService(s, search).suggestions_for_session(session_id)
        strict = RelatedCardsService(s, search, low_score_threshold=90.0).suggestions_for_session(session_id)

    assert default == []        # score 85 >= 60 default -> not a struggle
    assert len(strict) == 1     # raising the bar surfaces the weak-but-correct answer


def test_miss_count_counts_repeats_across_sessions(db):
    with db.session() as s:
        deck, basic = _default_deck(s), _basic(s)
        NoteService(s, make_engine()).create_note(
            deck.id, basic.id, {"Front": "Photosynthesis", "Back": "chloroplast"})
        td = DeckService(s).create("Bio", deck_type="test")
        q = QuestionService(s).create_text(td.id, "Define photosynthesis", ["light"], SHORT_ANSWER)
        quiz = QuizService(s)
        for _ in range(2):
            sess = quiz.start(td.id)
            quiz.record(sess, q, "wrong")
            quiz.finish(sess)
        last_session_id = sess.id

    search = SearchService(db)
    search.rebuild()
    with db.session() as s:
        struggles = RelatedCardsService(s, search).suggestions_for_session(last_session_id)
    assert struggles[0].miss_count == 2


# -- 3. autonomy: surfacing never reschedules; nudge is earlier-only --------


def test_suggesting_does_not_reschedule(db):
    with db.session() as s:
        deck, basic = _default_deck(s), _basic(s)
        note = NoteService(s, make_engine()).create_note(
            deck.id, basic.id, {"Front": "Photosynthesis", "Back": "chloroplast"})
        card = note.cards[0]
        card.srs_state = REVIEW
        card.due = now() + timedelta(days=5)
        td = DeckService(s).create("Bio", deck_type="test")
        q = QuestionService(s).create_text(td.id, "Define photosynthesis", ["light"], SHORT_ANSWER)
        quiz = QuizService(s)
        sess = quiz.start(td.id)
        quiz.record(sess, q, "wrong")
        quiz.finish(sess)
        s.flush()
        session_id, card_id, due_before = sess.id, card.id, card.due

    search = SearchService(db)
    search.rebuild()
    with db.session() as s:
        struggles = RelatedCardsService(s, search).suggestions_for_session(session_id)
        assert struggles                                   # there ARE suggestions
        assert s.get(Card, card_id).due == due_before      # but nothing was rescheduled


def test_nudge_brings_due_forward_only(db):
    moment = now()
    with db.session() as s:
        deck, basic = _default_deck(s), _basic(s)
        ns = NoteService(s, make_engine())
        future = ns.create_note(deck.id, basic.id, {"Front": "A", "Back": "a"})
        overdue = ns.create_note(deck.id, basic.id, {"Front": "B", "Back": "b"})
        fresh = ns.create_note(deck.id, basic.id, {"Front": "C", "Back": "c"})

        fcard = future.cards[0]
        fcard.srs_state = REVIEW
        fcard.due = moment + timedelta(days=10)
        ocard = overdue.cards[0]
        ocard.srs_state = REVIEW
        ocard.due = moment - timedelta(days=2)
        # fresh.cards[0] stays New
        s.flush()
        fid, oid, nid = fcard.id, ocard.id, fresh.cards[0].id
        overdue_due = ocard.due

    with db.session() as s:
        moved = RelatedCardsService(s, SearchService(db)).nudge_cards_due_now(
            [fid, oid, nid], at=moment)
        assert moved == 1                                  # only the future review card moved
        assert s.get(Card, fid).due == moment              # pulled earlier
        assert s.get(Card, oid).due == overdue_due         # already overdue -> untouched
        assert s.get(Card, nid).srs_state == "new"         # New card -> untouched


def test_nudge_preserves_learned_state(db):
    moment = now()
    with db.session() as s:
        deck, basic = _default_deck(s), _basic(s)
        note = NoteService(s, make_engine()).create_note(deck.id, basic.id, {"Front": "A", "Back": "a"})
        card = note.cards[0]
        card.srs_state = REVIEW
        card.due = moment + timedelta(days=10)
        card.ease_factor = 2.3
        card.interval_days = 12.0
        card.reps = 4
        s.flush()
        card_id = card.id

    with db.session() as s:
        RelatedCardsService(s, SearchService(db)).nudge_cards_due_now([card_id], at=moment)
        moved = s.get(Card, card_id)
        # only *when* the card is seen changes; the memory model is untouched.
        assert moved.due == moment
        assert moved.srs_state == REVIEW
        assert moved.ease_factor == 2.3
        assert moved.interval_days == 12.0
        assert moved.reps == 4
