"""Database safeguards: WAL, integrity check, rolling backups, orphan cleanup.

Ported from the previous iteration (the logic was sound). All functions are
pure utilities taking explicit arguments, so they unit-test without global state.
"""
from __future__ import annotations

import logging
import shutil
from datetime import date
from pathlib import Path

from sqlalchemy import Engine, text

logger = logging.getLogger(__name__)


def enable_wal_mode(engine: Engine) -> None:
    """Force WAL + foreign keys on the first connection (before integrity check)."""
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode = WAL"))
        conn.execute(text("PRAGMA foreign_keys = ON"))


def run_integrity_check(engine: Engine) -> bool:
    """Return True iff ``PRAGMA integrity_check`` reports 'ok'."""
    try:
        with engine.connect() as conn:
            row = conn.execute(text("PRAGMA integrity_check")).fetchone()
            ok = row is not None and row[0] == "ok"
            if not ok:
                logger.error("Integrity check failed: %s", row[0] if row else "no result")
            return ok
    except Exception:
        logger.exception("Integrity check raised.")
        return False


def create_rolling_backup(db_path: Path, backup_dir: Path, max_count: int) -> Path | None:
    """Copy the DB to ``study_app_YYYY-MM-DD.db`` and prune to *max_count* copies."""
    if not db_path.exists():
        logger.debug("Skipping backup — database does not exist yet.")
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"study_app_{date.today().isoformat()}.db"
    try:
        shutil.copy2(db_path, backup_path)
    except Exception:
        logger.exception("Failed to create rolling backup.")
        return None
    _prune_backups(backup_dir, max_count)
    return backup_path


def _prune_backups(backup_dir: Path, max_count: int) -> None:
    backups = sorted(backup_dir.glob("study_app_*.db"))
    while len(backups) > max_count:
        oldest = backups.pop(0)
        try:
            oldest.unlink()
        except Exception:
            logger.exception("Failed to remove old backup %s.", oldest)


def most_recent_backup(backup_dir: Path) -> Path | None:
    backups = sorted(backup_dir.glob("study_app_*.db"))
    return backups[-1] if backups else None


def cleanup_orphan_audio(audio_dir: Path, known_filenames: set[str]) -> int:
    """Delete .wav files not referenced by any card. Returns count removed.

    Decoupled from the repository layer (takes the known set directly) so it is
    safe to call only once the Card model exists (Phase 2).
    """
    if not audio_dir.exists():
        return 0
    deleted = 0
    for wav in audio_dir.glob("*.wav"):
        if wav.name not in known_filenames:
            try:
                wav.unlink()
                deleted += 1
            except Exception:
                logger.exception("Failed to delete orphan audio %s.", wav)
    if deleted:
        logger.info("Orphan audio cleanup: removed %d file(s).", deleted)
    return deleted
