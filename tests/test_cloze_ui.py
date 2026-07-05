from sqlalchemy import select

from app.context import AppContext
from core.settings import Settings
from data.models import Card, Deck
from domain.srs import make_engine
from ui.views.cloze_generator_dialog import ClozeGeneratorDialog


def _ctx(db, tmp_path) -> AppContext:
    return AppContext(
        db=db, engine=make_engine(),
        settings=Settings.load(tmp_path / "s.json"), tts=None, dictionary=None,
    )


def test_cloze_dialog_generates_into_new_deck(qapp, db, tmp_path):
    dialog = ClozeGeneratorDialog(_ctx(db, tmp_path))
    dialog.new_deck_name.setText("My Poem")
    dialog.text.setPlainText("Roses are red\nViolets are blue\nSugar is sweet")
    dialog._generate()
    assert dialog.created_count == 2
    with db.session() as s:
        deck = s.scalar(select(Deck).where(Deck.name == "My Poem"))
        assert deck is not None
        cards = s.scalars(select(Card).where(Card.deck_id == deck.id)).all()
        assert len(cards) == 2
