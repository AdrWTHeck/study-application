"""Pytest bootstrap.

Placed at the project root so pytest adds the root to ``sys.path`` (making the
top-level packages importable) and so the Qt platform is forced to ``offscreen``
before PyQt6 is imported, allowing GUI objects to be constructed headlessly.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Required for QWebEngineView to work in headless environments:
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --no-sandbox")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest  # noqa: E402
import PyQt6.QtWebEngineWidgets  # noqa: F401, E402 — must be imported before QApplication
from PyQt6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _no_webengine(monkeypatch):
    """Guardrail: never create a real QWebEngineView in tests.

    ReaderView builds its Chromium-backed webview lazily on first show; under
    the offscreen platform that hard-crashes the whole pytest process. Tests
    exercise the reader's logic, never the embedded browser, so the lazy init
    is a no-op here — and a future test calling .show() stays safe.
    """
    from ui.views.reader_view import ReaderView

    monkeypatch.setattr(ReaderView, "_ensure_webview", lambda self: None)


@pytest.fixture
def db(tmp_path):
    """A fresh, seeded database for Phase 2+ data/service tests."""
    import data.models  # noqa: F401  (register models)
    from data.db import Database
    from data.seed import seed_defaults

    database = Database(tmp_path / "app.db")
    database.create_all()
    seed_defaults(database)
    yield database
    database.dispose()


@pytest.fixture
def app_context(db, tmp_path):
    """A ready :class:`AppContext` backed by the seeded db, for view tests.

    Gives UI tests a real database, default settings, and the default FSRS
    engine without each test re-wiring the context by hand.
    """
    from app.context import AppContext
    from core.settings import Settings
    from domain.srs import make_engine

    return AppContext(
        db=db,
        engine=make_engine(),
        settings=Settings.load(tmp_path / "settings.json"),
        tts=None,
    )


@pytest.fixture
def sample_deck(db):
    """A 'Biology' card deck seeded with 5 Basic notes (→ 5 new cards).

    Returns the deck id. Use this anywhere a test needs a realistic deck of
    cards to study, browse, or run a focus session against.
    """
    from sqlalchemy import select

    from data.models import NoteType
    from domain.decks.deck_service import DeckService
    from domain.notes.note_service import NoteService
    from domain.srs import make_engine

    pairs = [
        ("What is the powerhouse of the cell?", "Mitochondria"),
        ("How do plants make energy?", "Photosynthesis"),
        ("What molecule carries genetic information?", "DNA"),
        ("What is the basic structural unit of life?", "The cell"),
        ("What gas do plants absorb from the air?", "Carbon dioxide"),
    ]
    with db.session() as s:
        deck = DeckService(s).create("Biology")
        deck_id = deck.id
        basic = s.scalar(select(NoteType).where(NoteType.name == "Basic"))
        notes = NoteService(s, make_engine())
        for front, back in pairs:
            notes.create_note(deck_id, basic.id, {"Front": front, "Back": back})
    return deck_id


@pytest.fixture
def sample_test_deck(db):
    """A 'Biology Quiz' test deck with one MCQ, one true/false, one short answer.

    Returns the deck id. Use for quiz/test/timing tests.
    """
    from data.models.testing import SHORT_ANSWER
    from domain.decks.deck_service import DeckService
    from domain.testing.question_service import QuestionService

    with db.session() as s:
        deck = DeckService(s).create("Biology Quiz", deck_type="test")
        deck_id = deck.id
        qs = QuestionService(s)
        qs.create_mcq(
            deck_id,
            "Which organelle is the powerhouse of the cell?",
            [("Mitochondria", True), ("Nucleus", False), ("Ribosome", False)],
        )
        qs.create_true_false(deck_id, "DNA carries genetic information.", True)
        qs.create_text(deck_id, "Plants make energy through ___.", ["Photosynthesis"], SHORT_ANSWER)
    return deck_id


@pytest.fixture
def sample_companion(db):
    """A freshly created companion (tree). Returns its row id."""
    from domain.companion.companion_service import CompanionService

    with db.session() as s:
        companion = CompanionService(s).get_or_create("tree")
        return companion.id


@pytest.fixture
def sample_pdf(tmp_path):
    """A small one-page PDF: a heading, two body paragraphs, and a page number."""
    import fitz

    path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "CHAPTER ONE", fontsize=24)
    page.insert_text((72, 200), "This is the first body paragraph with plenty of words to pass the threshold.", fontsize=11)
    page.insert_text((72, 320), "A second body paragraph also containing more than enough words here.", fontsize=11)
    page.insert_text((300, 760), "5", fontsize=9)
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def code_pdf(tmp_path):
    """PDF with mixed-font, multi-size content mirroring a C textbook page.

    Includes: monospace type keywords, proportional descriptions, escape
    characters, operator symbols, multiple font sizes, and footnote text.
    Used for bounding-box capture tests covering varied character types.
    """
    import fitz

    path = tmp_path / "code.pdf"
    doc = fitz.open()
    page = doc.new_page()
    # Large heading
    page.insert_text((72, 60),  "Basic Types and Operators", fontsize=18)
    # Type table — monospace keyword (col 1) + proportional description (col 2)
    page.insert_text((72,  120), "char",   fontsize=11, fontname="Courier")
    page.insert_text((144, 120), "ASCII character type, 8 bits.", fontsize=11)
    page.insert_text((72,  145), "int",    fontsize=11, fontname="Courier")
    page.insert_text((144, 145), "Default integer, at least 16 bits.", fontsize=11)
    page.insert_text((72,  170), "float",  fontsize=11, fontname="Courier")
    page.insert_text((144, 170), "Single precision floating point.", fontsize=11)
    page.insert_text((72,  195), "double", fontsize=11, fontname="Courier")
    page.insert_text((144, 195), "Double precision floating point.", fontsize=11)
    # Escape / special characters
    page.insert_text((72, 235), "Char constants: '\\t' tab, '\\n' newline, '\\0' null.", fontsize=11)
    # Operator symbols
    page.insert_text((72, 260), "Operators: + - * / % == != < > <= >= && ||", fontsize=11)
    # Medium section heading
    page.insert_text((72, 300), "Integer Types", fontsize=14)
    # Normal body text (11 pt)
    page.insert_text((72, 330), "Normal body text with standard word spacing here.", fontsize=11)
    # Footnote (8 pt) — near bottom
    page.insert_text((72, 750), "See also: unsigned types and pointer arithmetic.", fontsize=8)
    doc.save(str(path))
    doc.close()
    return path
