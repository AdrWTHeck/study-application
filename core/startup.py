"""Application startup sequence.

Order: open the database → enable WAL/FK → integrity check (halt + offer restore
on failure) → **schema-version guard** → rolling backup → create tables → seed →
stamp schema version.

The schema-version guard (PRAGMA user_version) detects a database from before the
current schema (e.g. a pre-rebuild file). Rather than crash on a missing column,
it archives the old file aside and recreates a fresh one — no data is destroyed.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect, text

from core.backup import (
    create_rolling_backup,
    enable_wal_mode,
    most_recent_backup,
    run_integrity_check,
)
from core.paths import AppPaths
import data.models  # noqa: F401  (import registers all models on Base.metadata)
from data.db import Database
from data.seed import seed_defaults

logger = logging.getLogger(__name__)

ROLLING_BACKUP_COUNT = 2
SCHEMA_VERSION = 1  # bump when the ORM schema changes incompatibly


@dataclass
class StartupResult:
    success: bool
    db: Database | None = None
    integrity_failed: bool = False
    most_recent_backup: Path | None = None
    reset_from: Path | None = None  # set when an incompatible DB was archived


def run_startup(paths: AppPaths, backup_count: int = ROLLING_BACKUP_COUNT) -> StartupResult:
    db = Database(paths.db_path)

    # Force WAL/FK on the first connection (also creates the DB file).
    enable_wal_mode(db.engine)

    if not run_integrity_check(db.engine):
        backup = most_recent_backup(paths.backups_dir)
        logger.critical("Database integrity check failed. Most recent backup: %s", backup)
        return StartupResult(success=False, integrity_failed=True, most_recent_backup=backup)

    # Schema-version guard: an existing DB whose version doesn't match the app's
    # is from before this schema — archive it and start fresh.
    reset_from = None
    if _has_tables(db):
        version = _user_version(db)
        if version != SCHEMA_VERSION:
            logger.warning(
                "Database schema v%s != app schema v%s; archiving old DB and recreating.",
                version, SCHEMA_VERSION,
            )
            db.dispose()
            reset_from = _archive_incompatible_db(paths.db_path)
            db = Database(paths.db_path)
            enable_wal_mode(db.engine)

    create_rolling_backup(paths.db_path, paths.backups_dir, backup_count)
    _run_additive_migrations(db)
    db.create_all()
    seed_defaults(db)
    _set_user_version(db, SCHEMA_VERSION)

    return StartupResult(success=True, db=db, reset_from=reset_from)


# ---------------------------------------------------------------------------
# Schema-version helpers
# ---------------------------------------------------------------------------

def _has_tables(db: Database) -> bool:
    return bool(inspect(db.engine).get_table_names())


def _user_version(db: Database) -> int:
    with db.engine.connect() as conn:
        return conn.execute(text("PRAGMA user_version")).scalar() or 0


def _set_user_version(db: Database, version: int) -> None:
    with db.engine.begin() as conn:
        conn.execute(text(f"PRAGMA user_version = {int(version)}"))


def _run_additive_migrations(db: Database) -> None:
    """Apply safe, additive ALTER TABLE migrations for new nullable columns.

    Each statement is wrapped in its own try/except so one failure doesn't
    block others. SQLite raises OperationalError when a column already exists.
    """
    _add_column_if_missing = [
        "ALTER TABLE decks ADD COLUMN icon TEXT",
        "ALTER TABLE deadlines ADD COLUMN phase TEXT",
        "ALTER TABLE deadlines ADD COLUMN skip_weekends INTEGER DEFAULT 0",
        "ALTER TABLE deadlines ADD COLUMN daily_cap INTEGER",
        "ALTER TABLE companion_state ADD COLUMN xp_today INTEGER DEFAULT 0",
        "ALTER TABLE companion_state ADD COLUMN xp_today_date TEXT DEFAULT ''",
        "ALTER TABLE review_logs ADD COLUMN scheduler_name TEXT",
        "ALTER TABLE review_logs ADD COLUMN prev_stability REAL",
        "ALTER TABLE review_logs ADD COLUMN new_stability REAL",
        "ALTER TABLE review_logs ADD COLUMN prev_difficulty REAL",
        "ALTER TABLE review_logs ADD COLUMN new_difficulty REAL",
        "ALTER TABLE highlights ADD COLUMN annotation TEXT",
        "ALTER TABLE source_documents ADD COLUMN working_copy_path VARCHAR(1024)",
        "ALTER TABLE source_documents ADD COLUMN original_archived BOOLEAN DEFAULT 0",
    ]
    with db.engine.begin() as conn:
        for stmt in _add_column_if_missing:
            try:
                conn.execute(text(stmt))
            except Exception:
                pass  # column already exists — safe to ignore


def _archive_incompatible_db(db_path: Path) -> Path | None:
    """Move an incompatible DB aside (kept, not deleted) and drop its WAL/SHM."""
    if not db_path.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archived = db_path.with_name(f"{db_path.stem}.pre-rebuild-{stamp}{db_path.suffix}")
    db_path.rename(archived)
    for suffix in ("-wal", "-shm"):
        sidecar = db_path.with_name(db_path.name + suffix)
        if sidecar.exists():
            sidecar.unlink()
    logger.info("Archived incompatible database to %s", archived)
    return archived
