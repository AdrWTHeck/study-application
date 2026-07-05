"""Dev-only: render the Cards browser + a review card to PNGs. Offscreen."""
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
from domain.notes.note_service import NoteService  # noqa: E402
from domain.srs import make_engine  # noqa: E402
from ui.theme.theme_controller import ThemeController  # noqa: E402
from ui.views.cards_view import CardsView  # noqa: E402
from ui.views.review_view import ReviewView  # noqa: E402

app = QApplication([])
tmp = Path(tempfile.mkdtemp())
db = Database(tmp / "app.db")
db.create_all()
seed_defaults(db)

with db.session() as s:
    deck = s.scalar(select(Deck).where(Deck.is_default.is_(True)))
    basic = s.scalar(select(NoteType).where(NoteType.name == "Basic"))
    notes = NoteService(s, make_engine())
    for i in range(3):
        notes.create_note(deck.id, basic.id, {"Front": f"Question {i}?", "Back": f"Answer {i}"})
    deck_id = deck.id

settings = Settings.load(tmp / "s.json")
ctx = AppContext(db=db, engine=make_engine(), settings=settings, tts=None)
theme = ThemeController(settings)
theme.apply(app)

out = Path(__file__).resolve().parent / "_preview"
out.mkdir(parents=True, exist_ok=True)

view = CardsView(ctx)
view.resize(900, 600)
view.show()
app.processEvents()
view.grab().save(str(out / "cards_browser.png"))
print("cards_browser.png; deck tree rows:", view._deck_tree.topLevelItemCount(),
      "detail:", view._detail_title.text())

review = ReviewView(ctx)
review.resize(900, 600)
review.start(deck_id)
review.show()
app.processEvents()
review.grab().save(str(out / "review_front.png"))
review._reveal()
app.processEvents()
review.grab().save(str(out / "review_back.png"))
print("review queue:", len(review._queue), "— OK")
