"""Database safeguards run at every launch (FR-INF-07–10).

All four functions are pure utility: they take explicit path/engine arguments
and have no dependency on global state, making them easy to unit-test.
"""
from __future__ import annotations

import logging
import shutil
from datetime import date
from pathlib import Path

from sqlalchemy import Engine, text

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FR-INF-07 — WAL mode
# ---------------------------------------------------------------------------

def enable_wal_mode(engine: Engine) -> None:
    """Explicitly set WAL journal mode and enable foreign keys on *engine*.

    The SQLAlchemy connect-event listener in models/base.py ensures these
    pragmas are applied on every connection.  This function is an additional
    one-time call during startup so the first connection is guaranteed to
    have WAL active before the integrity check runs.
    """
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode = WAL"))
        conn.execute(text("PRAGMA foreign_keys = ON"))


# ---------------------------------------------------------------------------
# FR-INF-08 — Integrity check
# ---------------------------------------------------------------------------

def run_integrity_check(engine: Engine) -> bool:
    """Return True if PRAGMA integrity_check returns 'ok', False otherwise."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA integrity_check"))
            row = result.fetchone()
            ok = row is not None and row[0] == "ok"
            if not ok:
                logger.error(
                    "Database integrity check failed: %s", row[0] if row else "no result"
                )
            return ok
    except Exception:
        logger.exception("Integrity check raised an exception.")
        return False


# ---------------------------------------------------------------------------
# FR-INF-09 — Rolling backup
# ---------------------------------------------------------------------------

def create_rolling_backup(
    db_path: Path,
    backup_dir: Path,
    max_count: int,
) -> Path | None:
    """Copy *db_path* to a timestamped file in *backup_dir* and prune old copies.

    Backup filename: ``study_app_YYYY-MM-DD.db``.
    If a backup for today already exists it is overwritten.
    Returns the path of the newly created backup, or None on failure.
    """
    if not db_path.exists():
        logger.debug("Skipping rolling backup — database does not exist yet.")
        return None

    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_name = f"study_app_{date.today().isoformat()}.db"
    backup_path = backup_dir / backup_name

    try:
        shutil.copy2(db_path, backup_path)
        logger.debug("Created backup: %s", backup_path)
    except Exception:
        logger.exception("Failed to create rolling backup.")
        return None

    _prune_backups(backup_dir, max_count)
    return backup_path


def _prune_backups(backup_dir: Path, max_count: int) -> None:
    """Delete the oldest backups so that at most *max_count* remain."""
    backups = sorted(backup_dir.glob("study_app_*.db"))
    while len(backups) > max_count:
        oldest = backups.pop(0)
        try:
            oldest.unlink()
            logger.debug("Pruned old backup: %s", oldest)
        except Exception:
            logger.exception("Failed to remove old backup %s.", oldest)


def most_recent_backup(backup_dir: Path) -> Path | None:
    """Return the path of the newest backup, or None if none exist."""
    backups = sorted(backup_dir.glob("study_app_*.db"))
    return backups[-1] if backups else None


# ---------------------------------------------------------------------------
# FR-INF-10 — Orphan audio cleanup
# ---------------------------------------------------------------------------

def cleanup_orphan_audio(audio_dir: Path, card_repo) -> int:
    """Delete .wav files in *audio_dir* that are not referenced by any card.

    *card_repo* must expose ``all_audio_paths() -> set[str]``.
    Paths stored in the DB are filename-only (e.g. ``123_1234567890.wav``).

    Returns the number of files deleted.
    """
    if not audio_dir.exists():
        return 0

    try:
        known = card_repo.all_audio_paths()
    except Exception:
        # Tables may not exist on first launch — treat as empty set.
        logger.debug("Could not query audio paths (first launch?); skipping orphan cleanup.")
        known = set()

    deleted = 0
    for wav_file in audio_dir.glob("*.wav"):
        if wav_file.name not in known:
            try:
                wav_file.unlink()
                deleted += 1
                logger.debug("Deleted orphan audio: %s", wav_file)
            except Exception:
                logger.exception("Failed to delete orphan audio %s.", wav_file)

    if deleted:
        logger.info("Orphan audio cleanup: deleted %d file(s).", deleted)
    return deleted
