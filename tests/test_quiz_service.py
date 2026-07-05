from data.models.testing import SHORT_ANSWER
from domain.decks.deck_service import DeckService
from domain.testing.question_service import QuestionService
from domain.testing.quiz_service import QuizService


def _deck_with_questions(session):
    deck = DeckService(session).create("Quiz", deck_type="test")
    qs = QuestionService(session)
    q1 = qs.create_mcq(deck.id, "2+2?", [("4", True), ("5", False)])
    q2 = qs.create_text(deck.id, "Capital of France?", ["Paris"], SHORT_ANSWER)
    return deck, q1, q2


def test_session_flow_and_score(db):
    with db.session() as s:
        deck, q1, q2 = _deck_with_questions(s)
        quiz = QuizService(s)
        session = quiz.start(deck.id)
        quiz.record(session, q1, "4")       # correct
        quiz.record(session, q2, "Berlin")  # wrong
        quiz.finish(session)
        assert quiz.session_score(session.id) == 50.0
        assert session.status == "complete" and session.finished_at is not None


def test_incorrect_questions_for_retest(db):
    with db.session() as s:
        deck, q1, q2 = _deck_with_questions(s)
        quiz = QuizService(s)
        session = quiz.start(deck.id)
        quiz.record(session, q1, "5")       # wrong
        quiz.record(session, q2, "Paris")   # correct
        assert [q.id for q in quiz.incorrect_questions(session.id)] == [q1.id]


def test_accuracy_by_type(db):
    with db.session() as s:
        deck, q1, q2 = _deck_with_questions(s)
        quiz = QuizService(s)
        session = quiz.start(deck.id)
        quiz.record(session, q1, "4")
        quiz.record(session, q2, "Paris")
        accuracy = quiz.accuracy_by_type(session.id)
        assert accuracy["mcq"] == (1, 1)
        assert accuracy["short_answer"] == (1, 1)


def test_history_lists_completed_sessions(db):
    with db.session() as s:
        deck, q1, q2 = _deck_with_questions(s)
        quiz = QuizService(s)
        session = quiz.start(deck.id)
        quiz.record(session, q1, "4")
        quiz.record(session, q2, "Paris")
        quiz.finish(session)
        history = quiz.history(deck.id)
        assert len(history) == 1 and history[0][2] == 100.0


def test_slowest_questions_ranked(db):
    with db.session() as s:
        deck, q1, q2 = _deck_with_questions(s)
        quiz = QuizService(s)
        session = quiz.start(deck.id)
        quiz.record(session, q1, "4", time_ms=1200)
        quiz.record(session, q2, "Paris", time_ms=8500)
        slowest = quiz.slowest_questions(session.id, limit=5)
        # q2 took longer → ranked first.
        assert [q.id for q, _ in slowest] == [q2.id, q1.id]
        assert slowest[0][1] == 8500


def test_slowest_questions_skips_untimed(db):
    with db.session() as s:
        deck, q1, q2 = _deck_with_questions(s)
        quiz = QuizService(s)
        session = quiz.start(deck.id)
        quiz.record(session, q1, "4", time_ms=None)
        quiz.record(session, q2, "Paris", time_ms=3000)
        slowest = quiz.slowest_questions(session.id)
        assert [q.id for q, _ in slowest] == [q2.id]


def test_session_duration_falls_back_to_sum(db):
    with db.session() as s:
        deck, q1, q2 = _deck_with_questions(s)
        quiz = QuizService(s)
        session = quiz.start(deck.id)
        quiz.record(session, q1, "4", time_ms=1000)
        quiz.record(session, q2, "Paris", time_ms=2000)
        # Not finished → no finished_at, falls back to summed per-question time.
        assert quiz.session_duration_ms(session.id) == 3000


def test_answer_review_details(db):
    with db.session() as s:
        deck, q1, q2 = _deck_with_questions(s)
        quiz = QuizService(s)
        session = quiz.start(deck.id)
        quiz.record(session, q1, "4", time_ms=1500)        # correct MCQ
        quiz.record(session, q2, "Berlin", time_ms=4000)   # wrong short answer
        review = quiz.answer_review(session.id)
        assert len(review) == 2

        mcq_row = review[0]
        assert mcq_row.is_correct is True
        assert mcq_row.user_response == "4"
        assert mcq_row.correct_answer == "4"          # the correct option text
        assert mcq_row.time_ms == 1500

        text_row = review[1]
        assert text_row.is_correct is False
        assert text_row.user_response == "Berlin"
        assert text_row.correct_answer == "Paris"     # accepted answer surfaced
