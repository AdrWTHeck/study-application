from core.backup import create_rolling_backup, most_recent_backup, run_integrity_check
from data.db import Database


def test_integrity_check_ok_on_fresh_db(tmp_path):
    db = Database(tmp_path / "t.db")
    db.create_all()
    assert run_integrity_check(db.engine) is True


def test_rolling_backup_creates_and_prunes(tmp_path):
    db_path = tmp_path / "study_app.db"
    db_path.write_bytes(b"data")
    backups = tmp_path / "backups"
    backups.mkdir()
    # Pre-existing older backups from prior days.
    for day in ("2020-01-01", "2020-01-02", "2020-01-03"):
        (backups / f"study_app_{day}.db").write_bytes(b"old")

    out = create_rolling_backup(db_path, backups, max_count=2)

    assert out is not None and out.exists()
    remaining = sorted(backups.glob("study_app_*.db"))
    assert len(remaining) == 2  # pruned to the two newest
    assert most_recent_backup(backups) == out


def test_backup_skipped_when_db_missing(tmp_path):
    assert create_rolling_backup(tmp_path / "nope.db", tmp_path / "b", max_count=2) is None
