"""Dev-only: boot the whole app (real main() path) headlessly, seed sample data,
and render every primary view. Surfaces any startup/wiring errors. Offscreen.
"""
import os
import sys
import tempfile
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    from sqlalchemy import select

    from PyQt6.QtWidgets import QApplication

    import data.models  # noqa: F401
    from app.main_window import MainWindow
    from app.navigation import Destination
    from core.paths import assets_dir, get_app_paths
    from core.settings import Settings
    from core.startup import run_startup
    from data.models import Deck, NoteType
    from data.models.testing import SHORT_ANSWER
    from domain.accessibility.tts_service import TTSService
    from domain.decks.deck_service import DeckService
    from domain.notes.note_service import NoteService
    from domain.srs import make_engine
    from domain.sources.source_service import SourceService
    from domain.testing.question_service import QuestionService
    from ui.theme.fonts import load_application_fonts
    from ui.theme.theme_controller import ThemeController

    tmp = Path(tempfile.mkdtemp())

    # --- boot exactly like main() -------------------------------------------
    paths = get_app_paths(base=tmp / "user_data")
    settings = Settings.load(paths.settings_path)
    settings.set("onboarding_complete", True)
    app = QApplication([])
    load_application_fonts(assets_dir() / "fonts")
    theme = ThemeController(settings)
    theme.apply(app)
    startup = run_startup(paths)
    if not startup.success:
        print("STARTUP FAILED: integrity check")
        return 1
    tts = TTSService(autostart=False)

    # --- seed a little sample content so views aren't empty ------------------
    sample_pdf = tmp / "sample.pdf"
    try:
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "CHAPTER ONE", fontsize=24)
        page.insert_text((72, 200), "This is a body paragraph with several words to read.", fontsize=11)
        doc.save(str(sample_pdf))
        doc.close()
    except Exception:
        sample_pdf = None

    with startup.db.session() as s:
        deck = s.scalar(select(Deck).where(Deck.is_default.is_(True)))
        basic = s.scalar(select(NoteType).where(NoteType.name == "Basic"))
        notes = NoteService(s, make_engine())
        notes.create_note(deck.id, basic.id, {"Front": "What is the capital of France?", "Back": "Paris"})
        notes.create_note(deck.id, basic.id, {"Front": "2 + 2 = ?", "Back": "4"})
        test_deck = DeckService(s).create("Sample Quiz", deck_type="test")
        QuestionService(s).create_text(test_deck.id, "Capital of France?", ["Paris"], SHORT_ANSWER)
    if sample_pdf is not None:
        with startup.db.session() as s:
            SourceService(s).import_pdf(str(sample_pdf), title="Sample Source")

    # --- build the window and render every view ------------------------------
    window = MainWindow(settings, theme, paths, startup.db, tts)
    window.resize(1200, 780)
    window.show()
    app.processEvents()

    out = Path(__file__).resolve().parent / "_preview"
    out.mkdir(parents=True, exist_ok=True)
    for dest in Destination:
        window._navigate(dest)
        app.processEvents()
        window.grab().save(str(out / f"app_{dest.name.lower()}.png"))
        print("rendered", dest.name)

    print("STARTUP OK — all views constructed and rendered.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
