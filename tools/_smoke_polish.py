"""Dev-only: render the upgraded deck browser (advanced) + notes browser."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from PyQt6.QtWidgets import QApplication  # noqa: E402

import data.models  # noqa: E402,F401
from app.context import AppContext  # noqa: E402
from core.settings import Settings  # noqa: E402
from data.db import Database  # noqa: E402
from data.models import Deck, NoteType  # noqa: E402
from data.seed import seed_defaults  # noqa: E402
from domain.decks.deck_service import DeckService  # noqa: E402
from domain.notes.note_service import NoteService  # noqa: E402
from domain.srs import Sm2Engine  # noqa: E402
from ui.theme.theme_controller import ThemeController  # noqa: E402
from ui.views.cards_view import CardsView  # noqa: E402
from ui.views.notes_view import NotesView  # noqa: E402

app = QApplication([])
tmp = Path(tempfile.mkdtemp())
db = Database(tmp / "app.db")
db.create_all()
seed_defaults(db)

with db.session() as s:
    deck = s.scalar(select(Deck).where(Deck.is_default.is_(True)))
    basic = s.scalar(select(NoteType).where(NoteType.name == "Basic"))
    DeckService(s).set_color(deck.id, "#e67700")
    notes = NoteService(s, Sm2Engine())
    for i in range(3):
        notes.create_note(deck.id, basic.id, {"Front": f"Capital of country {i}?", "Back": f"City {i}"})
    DeckService(s).create("French Vocabulary")
    deck_id, deck_name = deck.id, deck.name

settings = Settings.load(tmp / "s.json")
settings.set("mode", "advanced")
ctx = AppContext(db=db, engine=Sm2Engine(), settings=settings, tts=None)
theme = ThemeController(settings)
theme.apply(app)

out = Path(__file__).resolve().parent / "_preview"
out.mkdir(parents=True, exist_ok=True)

cards = CardsView(ctx)
cards.resize(940, 560)
cards.show()
app.processEvents()
cards.grab().save(str(out / "deck_browser_advanced.png"))
print("deck_browser_advanced.png; new-type btn hidden:", cards._new_type_btn.isHidden())

notes = NotesView(ctx)
notes.resize(940, 560)
notes.open_deck(deck_id, deck_name)
notes.show()
app.processEvents()
notes.grab().save(str(out / "notes_browser.png"))
print("notes_browser.png; rows:", notes._list_layout.count(), "checks:", len(notes._checks))
print("OK")
