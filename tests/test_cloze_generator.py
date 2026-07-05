from sqlalchemy import select

from data.models import Card
from domain.decks.deck_service import DeckService
from domain.notes.cloze_generator import ClozeDeckBuilder, line_completion_values
from domain.srs import make_engine


def test_line_completion_pairs_lines():
    values = line_completion_values("Line one\nLine two\nLine three")
    assert len(values) == 2
    assert "Line one" in values[0]["Text"]
    assert "{{c1::Line two}}" in values[0]["Text"]
    assert "{{c1::Line three}}" in values[1]["Text"]


def test_blank_lines_skipped():
    assert len(line_completion_values("a\n\n\nb")) == 1


def test_single_line_yields_nothing():
    assert line_completion_values("only one line") == []


def test_build_creates_one_card_per_pair(db):
    with db.session() as s:
        deck = DeckService(s).create("Poem")
        created = ClozeDeckBuilder(s, make_engine()).build(
            deck.id, "Roses are red\nViolets are blue\nSugar is sweet"
        )
        assert created == 2
        cards = s.scalars(select(Card).where(Card.deck_id == deck.id)).all()
        assert len(cards) == 2  # Cloze note type → one card per note
