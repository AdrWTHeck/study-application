import pytest

from domain.dictionary.builder import build_dictionary
from domain.dictionary.service import DictionaryService

SAMPLE = [
    {"word": "apple", "pos": "noun",
     "senses": [{"glosses": ["A round fruit"], "examples": [{"text": "I ate an apple."}]}]},
    {"word": "apply", "pos": "verb",
     "senses": [{"glosses": ["To put to use"]}]},
    {"word": "banana", "pos": "noun",
     "senses": [{"glosses": ["A long curved fruit"]}]},
]


def _build(tmp_path):
    db = tmp_path / "dict.db"
    build_dictionary(SAMPLE, db)
    return DictionaryService(db)


def test_build_counts_senses(tmp_path):
    assert build_dictionary(SAMPLE, tmp_path / "d.db") == 3


def test_prefix_search_is_sorted_and_case_insensitive(tmp_path):
    svc = _build(tmp_path)
    assert svc.available
    assert svc.prefix_search("ap") == ["apple", "apply"]
    assert svc.prefix_search("BA") == ["banana"]


def test_prefix_search_supports_substring_and_fuzzy_matches(tmp_path):
    svc = _build(tmp_path)
    assert svc.prefix_search("ppl") == ["apple", "apply"]
    fuzzy = svc.prefix_search("aple")
    assert "apple" in fuzzy
    assert "apply" in fuzzy


def test_lookup_returns_senses_and_examples(tmp_path):
    svc = _build(tmp_path)
    result = svc.lookup("Apple")
    assert result is not None
    assert result.source == "wiktionary"
    assert result.senses[0].gloss == "A round fruit"
    assert result.senses[0].examples == ["I ate an apple."]


def test_search_definitions_via_fts(tmp_path):
    svc = _build(tmp_path)
    if not svc._fts_available():
        pytest.skip("FTS5 not available in this sqlite build")
    words = {word for word, _ in svc.search_definitions("fruit")}
    assert "apple" in words and "banana" in words


def test_missing_db_is_safe(tmp_path):
    svc = DictionaryService(tmp_path / "nope.db")
    assert svc.available is False
    assert svc.prefix_search("a") == []
    svc.lookup("apple")  # WordNet fallback or None — must not raise
