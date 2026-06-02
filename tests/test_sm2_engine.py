from datetime import datetime, timedelta

from domain.srs import LEARNING, NEW, RELEARNING, REVIEW, CardState, Rating, Sm2Engine

NOW = datetime(2026, 1, 1, 12, 0, 0)
eng = Sm2Engine()


def _review_card(ease=2.5, interval=10.0):
    return CardState(state=REVIEW, due=NOW, ease_factor=ease, interval_days=interval, reps=3)


def test_new_state_defaults():
    s = eng.new_state(NOW)
    assert s.state == NEW and s.due == NOW and s.ease_factor == 2.5


def test_new_good_advances_to_second_step():
    s = eng.review(eng.new_state(NOW), Rating.GOOD, NOW)
    assert s.state == LEARNING and s.learning_step == 1
    assert s.due == NOW + timedelta(minutes=10)


def test_two_goods_graduate_to_review():
    s = eng.new_state(NOW)
    s = eng.review(s, Rating.GOOD, NOW)
    s = eng.review(s, Rating.GOOD, NOW)
    assert s.state == REVIEW and s.interval_days == 1 and s.reps == 1
    assert s.due == NOW + timedelta(days=1)


def test_easy_graduates_immediately():
    s = eng.review(eng.new_state(NOW), Rating.EASY, NOW)
    assert s.state == REVIEW and s.interval_days == 4
    assert s.due == NOW + timedelta(days=4)


def test_again_resets_learning_step():
    s = eng.review(eng.new_state(NOW), Rating.GOOD, NOW)
    s = eng.review(s, Rating.AGAIN, NOW)
    assert s.state == LEARNING and s.learning_step == 0
    assert s.due == NOW + timedelta(minutes=1)


def test_review_good_multiplies_by_ease():
    s = eng.review(_review_card(interval=10), Rating.GOOD, NOW)
    assert s.interval_days == 25.0
    assert s.due == NOW + timedelta(days=25)
    assert s.reps == 4


def test_review_hard_lowers_ease():
    s = eng.review(_review_card(ease=2.5, interval=10), Rating.HARD, NOW)
    assert round(s.ease_factor, 2) == 2.35
    assert s.interval_days == 12.0


def test_review_again_lapses_to_relearning():
    s = eng.review(_review_card(ease=2.5, interval=10), Rating.AGAIN, NOW)
    assert s.state == RELEARNING and s.lapses == 1
    assert round(s.ease_factor, 2) == 2.30
    assert s.due == NOW + timedelta(minutes=10)


def test_review_easy_applies_bonus():
    s = eng.review(_review_card(ease=2.5, interval=10), Rating.EASY, NOW)
    assert round(s.ease_factor, 2) == 2.65
    assert round(s.interval_days, 2) == 34.45


def test_relearning_good_graduates_back_to_review():
    s = CardState(state=RELEARNING, due=NOW, ease_factor=2.3, interval_days=1.0, reps=3, lapses=1)
    s = eng.review(s, Rating.GOOD, NOW)
    assert s.state == REVIEW and s.interval_days == 1


def test_ease_never_below_minimum():
    s = _review_card(ease=1.3, interval=10)
    for _ in range(5):
        s = eng.review(s, Rating.HARD, NOW)
        s.state = REVIEW  # keep it in review to keep applying hard
    assert s.ease_factor >= 1.3
