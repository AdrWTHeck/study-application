"""Dev-only: render the PDF reader against a real PDF. Offscreen."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication  # noqa: E402

import data.models  # noqa: E402,F401
from app.context import AppContext  # noqa: E402
from core.paths import assets_dir  # noqa: E402
from core.settings import Settings  # noqa: E402
from data.db import Database  # noqa: E402
from data.seed import seed_defaults  # noqa: E402
from domain.srs import make_engine  # noqa: E402
from domain.sources.source_service import SourceService  # noqa: E402
from ui.theme.fonts import load_application_fonts  # noqa: E402
from ui.theme.theme_controller import ThemeController  # noqa: E402
from ui.views.reader_view import ReaderView  # noqa: E402

PDF = r"C:\Users\Adrian PG\Downloads\final project- cs3801-1.pdf"

app = QApplication([])
load_application_fonts(assets_dir() / "fonts")
tmp = Path(tempfile.mkdtemp())
db = Database(tmp / "app.db")
db.create_all()
seed_defaults(db)

with db.session() as s:
    source_id = SourceService(s).import_pdf(PDF, title="CS3801 Final Project").id

settings = Settings.load(tmp / "s.json")
ctx = AppContext(db=db, engine=make_engine(), settings=settings, tts=None, dictionary=None)
theme = ThemeController(settings)
theme.apply(app)

reader = ReaderView(ctx)
reader.resize(1240, 760)
reader.open_source(source_id)
reader.show()
app.processEvents()

out = Path(__file__).resolve().parent / "_preview"
out.mkdir(parents=True, exist_ok=True)
reader.grab().save(str(out / "reader.png"))
print("reader.png; page", reader._page, "of", reader._page_count,
      "| text chars:", len(reader._text.toPlainText()))
