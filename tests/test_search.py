from sqlalchemy import select

from data.models import Deck, NoteType
from data.models.testing import SHORT_ANSWER
from domain.decks.deck_service import DeckService
from domain.dictionary.builder import build_dictionary
from domain.dictionary.service import DictionaryService
from domain.notes.note_service import NoteService
from domain.search.search_service import SearchService
from domain.sources.source_service import SourceService
from domain.srs import make_engine
from domain.testing.question_service import QuestionService


def test_search_finds_notes_and_questions(db):
    with db.session() as s:
        deck = s.scalar(select(Deck).where(Deck.is_default.is_(True)))
        basic = s.scalar(select(NoteType).where(NoteType.name == "Basic"))
        NoteService(s, make_engine()).create_note(deck.id, basic.id, {"Front": "Photosynthesis", "Back": "chloroplast"})
        td = DeckService(s).create("Quiz", deck_type="test")
        QuestionService(s).create_text(td.id, "Define photosynthesis", ["light"], SHORT_ANSWER)
    service = SearchService(db)
    service.rebuild()
    types = {r.type for r in service.search("photosynthesis")}
    assert "note" in types and "question" in types


def test_search_matches_source_text(db, sample_pdf):
    with db.session() as s:
        SourceService(s).import_pdf(str(sample_pdf), title="Doc")
    service = SearchService(db)
    service.rebuild()
    assert any(r.type == "source" for r in service.search("paragraph"))


def test_search_empty_query_returns_nothing(db):
    service = SearchService(db)
    service.rebuild()
    assert service.search("") == []


def test_search_includes_dictionary_prefix_hits(db, tmp_path):
    sample = [
        {"word": "apple", "pos": "noun", "senses": [{"glosses": ["A fruit"]}]},
        {"word": "apply", "pos": "verb", "senses": [{"glosses": ["To use"]}]},
    ]
    dict_path = tmp_path / "dict.db"
    build_dictionary(sample, dict_path)
    dictionary = DictionaryService(dict_path)

    service = SearchService(db, dictionary_service=dictionary)
    results = service.search("appl")
    assert any(r.type == "dictionary" for r in results)
    assert any(r.title == "apple" for r in results)
    assert any(r.title == "apply" for r in results)


def test_search_before_rebuild_is_safe(db):
    assert SearchService(db).search("anything") == []
