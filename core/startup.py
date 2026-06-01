"""Application startup sequence.

Order: open the database → enable WAL/FK → integrity check (halt + offer restore
on failure) → rolling backup → create tables. Models and default-deck seeding
arrive in Phase 2; ``create_all`` is a no-op until then.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

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


@dataclass
class StartupResult:
    success: bool
    db: Database | None = None
    integrity_failed: bool = False
    most_recent_backup: Path | None = None


def run_startup(paths: AppPaths, backup_count: int = ROLLING_BACKUP_COUNT) -> StartupResult:
    db = Database(paths.db_path)

    # Force WAL/FK on the first connection (also creates the DB file).
    enable_wal_mode(db.engine)

    if not run_integrity_check(db.engine):
        backup = most_recent_backup(paths.backups_dir)
        logger.critical("Database integrity check failed. Most recent backup: %s", backup)
        return StartupResult(success=False, integrity_failed=True, most_recent_backup=backup)

    create_rolling_backup(paths.db_path, paths.backups_dir, backup_count)
    db.create_all()
    seed_defaults(db)

    return StartupResult(success=True, db=db)
