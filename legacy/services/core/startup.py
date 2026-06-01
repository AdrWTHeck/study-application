"""Application startup sequence (SDD §2.3).

Steps:
  1  Verify / create user_data directories; verify webster1913.db asset.
  2  Initialise SQLAlchemy engine.
  3  Enable WAL mode + foreign keys (FR-INF-07).
  4  Run PRAGMA integrity_check (FR-INF-08).
  5  Create rolling backup (FR-INF-09).
  6  Clean up orphan audio files (FR-INF-10).
  7  create_all ORM tables; seed default decks on first launch (FR-INF-01).
  8  Load AppSettings singleton (FR-INF-03).
  9  Return in-progress sessions for main.py to present resume/discard UI.
"""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

from config.constants import ROLLING_BACKUP_COUNT
from models import Base, init_engine, get_session
from models.deck import Deck
from repositories.card_repository import CardRepository
from repositories.quiz_session_repository import QuizSessionRepository
from services.core.app_settings import AppSettings
from services.core.backup import (
    cleanup_orphan_audio,
    create_rolling_backup,
    enable_wal_mode,
    most_recent_backup,
    run_integrity_check,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path constants — all derived from this file's location so the app is
# portable regardless of working directory.
# study_app/services/core/startup.py → parents[2] = study_app/
# ---------------------------------------------------------------------------
_APP_ROOT = Path(__file__).resolve().parents[2]

USER_DATA_DIR = _APP_ROOT / "user_data"
DB_PATH = USER_DATA_DIR / "study_app.db"
SETTINGS_PATH = USER_DATA_DIR / "settings.json"
AUDIO_DIR = USER_DATA_DIR / "audio"
BACKUP_DIR = USER_DATA_DIR / "backups"
ASSETS_DIR = _APP_ROOT / "assets"
WEBSTER_DB_PATH = ASSETS_DIR / "dictionaries" / "webster1913.db"


@dataclass
class StartupResult:
    success: bool
    integrity_failed: bool = False
    most_recent_backup: Path | None = None
    pending_sessions: list = field(default_factory=list)
    settings: AppSettings | None = None
    webster_available: bool = True


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run() -> StartupResult:
    """Execute the full startup sequence and return a StartupResult.

    On integrity failure (step 4) ``success=False`` and
    ``integrity_failed=True`` are set; main.py must show the restore dialog
    before proceeding.
    """
    # Step 1 — Ensure user_data directories exist (FR-INF-02).
    _ensure_dirs()

    # Step 1b — Verify bundled asset (FR-INF-06).
    webster_available = _verify_webster()

    # Step 2 — Initialise engine (creates DB file on first launch).
    engine = init_engine(str(DB_PATH))

    # Step 3 — WAL + foreign keys (FR-INF-07).
    enable_wal_mode(engine)

    # Step 4 — Integrity check (FR-INF-08).
    if not run_integrity_check(engine):
        backup = most_recent_backup(BACKUP_DIR)
        logger.critical("Database integrity check failed. Most recent backup: %s", backup)
        return StartupResult(
            success=False,
            integrity_failed=True,
            most_recent_backup=backup,
        )

    # Step 5 — Rolling backup (FR-INF-09).
    create_rolling_backup(DB_PATH, BACKUP_DIR, ROLLING_BACKUP_COUNT)

    # Step 6 — Orphan audio cleanup (FR-INF-10).
    session = get_session()
    try:
        card_repo = CardRepository(session)
        cleanup_orphan_audio(AUDIO_DIR, card_repo)
    finally:
        session.close()

    # Step 7 — Create ORM tables; seed on first launch (FR-INF-01).
    Base.metadata.create_all(engine)
    _seed_default_decks()

    # Step 8 — Load AppSettings (FR-INF-03).
    settings = AppSettings.get_instance()
    settings.load(SETTINGS_PATH)
    settings.webster_available = webster_available

    # Step 9 — Collect in-progress sessions for UI resume/discard dialog.
    session = get_session()
    try:
        pending = QuizSessionRepository(session).get_in_progress()
    finally:
        session.close()

    return StartupResult(
        success=True,
        pending_sessions=pending,
        settings=settings,
        webster_available=webster_available,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_dirs() -> None:
    """Create user_data, audio, and backups directories if absent."""
    for directory in (USER_DATA_DIR, AUDIO_DIR, BACKUP_DIR):
        directory.mkdir(parents=True, exist_ok=True)
        logger.debug("Ensured directory: %s", directory)


def _verify_webster() -> bool:
    """Return True if webster1913.db is present; log a warning otherwise."""
    if WEBSTER_DB_PATH.exists():
        return True
    logger.warning(
        "Webster's 1913 database not found at %s. "
        "Webster section will be disabled; WordNet remains available.",
        WEBSTER_DB_PATH,
    )
    return False


def _seed_default_decks() -> None:
    """Insert the two default decks on first launch (FR-INF-01).

    Idempotent: checks for existing defaults before inserting.
    """
    session = get_session()
    try:
        from repositories.deck_repository import DeckRepository
        repo = DeckRepository(session)

        if repo.get_default("card") is None:
            session.add(
                Deck(name="Uncategorized", deck_type="card", is_default=True)
            )
            logger.info("Seeded default card deck 'Uncategorized'.")

        if repo.get_default("test") is None:
            session.add(
                Deck(name="Uncategorized Tests", deck_type="test", is_default=True)
            )
            logger.info("Seeded default test deck 'Uncategorized Tests'.")

        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Failed to seed default decks.")
        raise
    finally:
        session.close()
