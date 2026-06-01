"""Pytest bootstrap.

Placed at the project root so pytest adds the root to ``sys.path`` (making the
top-level packages importable) and so the Qt platform is forced to ``offscreen``
before PyQt6 is imported, allowing GUI objects to be constructed headlessly.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


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
