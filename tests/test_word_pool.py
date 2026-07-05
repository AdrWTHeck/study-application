"""Tests for the deadline word-of-the-day pool."""
from domain.deadlines.word_pool import (
    BASE_WORDS,
    resolve_pool,
    word_of_the_day,
)


def test_base_pool_has_at_least_50_words():
    assert len(BASE_WORDS) >= 50


def test_resolve_pool_filters_by_category():
    fun = resolve_pool(categories=["fun"])
    fun_words = {w for (w, _d, c) in BASE_WORDS if c == "fun"}
    assert {w for w, _d in fun} == fun_words
    assert all(w in fun_words for w, _d in fun)


def test_resolve_pool_custom_words_win():
    pool = resolve_pool(custom_words=["focus - pay attention", "grit"])
    assert ("focus", "pay attention") in pool
    assert ("grit", "") in pool
    assert len(pool) == 2


def test_resolve_pool_empty_categories_uses_all():
    full = resolve_pool(categories=[])
    assert len(full) == len(BASE_WORDS)


def test_word_of_the_day_is_stable_and_wraps():
    pool = resolve_pool(categories=["academic"])
    first = word_of_the_day(0, pool)
    assert first == pool[0]
    # Wraps around by pool length.
    assert word_of_the_day(len(pool), pool) == pool[0]


def test_word_of_the_day_empty_pool():
    assert word_of_the_day(5, []) == ("", "")
