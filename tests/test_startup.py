import sqlite3

from sqlalchemy import inspect, select, text

from core.paths import get_app_paths
from core.startup import SCHEMA_VERSION, run_startup
from data.models import Deck


def test_startup_succeeds_and_creates_db(tmp_path):
    paths = get_app_paths(base=tmp_path / "d")
    result = run_startup(paths)
    assert result.success
    assert result.db is not None
    assert paths.db_path.exists()


def test_startup_writes_backup(tmp_path):
    paths = get_app_paths(base=tmp_path / "d")
    run_startup(paths)
    assert list(paths.backups_dir.glob("study_app_*.db"))


def test_fresh_db_is_stamped_with_schema_version(tmp_path):
    paths = get_app_paths(base=tmp_path / "d")
    result = run_startup(paths)
    with result.db.engine.connect() as conn:
        assert conn.execute(text("PRAGMA user_version")).scalar() == SCHEMA_VERSION
    assert result.reset_from is None


def test_incompatible_db_is_archived_and_recreated(tmp_path):
    paths = get_app_paths(base=tmp_path / "d")
    # Simulate a pre-rebuild DB: a 'cards' table without the new columns, version 0.
    conn = sqlite3.connect(str(paths.db_path))
    conn.execute("CREATE TABLE cards (id INTEGER PRIMARY KEY, front_text TEXT)")
    conn.commit()
    conn.close()

    result = run_startup(paths)
    assert result.success
    assert result.reset_from is not None and result.reset_from.exists()
    # Fresh schema present.
    columns = {c["name"] for c in inspect(result.db.engine).get_columns("cards")}
    assert "srs_state" in columns


def test_compatible_db_is_not_reset(tmp_path):
    paths = get_app_paths(base=tmp_path / "d")
    first = run_startup(paths)
    with first.db.session() as s:
        s.add(Deck(name="Keep me", deck_type="card"))
    first.db.dispose()

    second = run_startup(paths)
    assert second.reset_from is None  # up-to-date DB left alone
    with second.db.session() as s:
        names = {d.name for d in s.scalars(select(Deck))}
    assert "Keep me" in names
