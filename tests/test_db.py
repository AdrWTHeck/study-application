from sqlalchemy import text

from data.db import Database


def test_wal_mode_enabled(tmp_path):
    db = Database(tmp_path / "t.db")
    with db.session() as s:
        mode = s.execute(text("PRAGMA journal_mode")).scalar()
    assert str(mode).lower() == "wal"


def test_session_commits_on_success(tmp_path):
    db = Database(tmp_path / "t.db")
    with db.session() as s:
        s.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)"))
        s.execute(text("INSERT INTO t (v) VALUES ('x')"))
    with db.session() as s:
        assert s.execute(text("SELECT v FROM t")).scalar() == "x"


def test_session_rolls_back_on_error(tmp_path):
    db = Database(tmp_path / "t.db")
    with db.session() as s:
        s.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)"))
    try:
        with db.session() as s:
            s.execute(text("INSERT INTO t (v) VALUES ('y')"))
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    with db.session() as s:
        assert s.execute(text("SELECT COUNT(*) FROM t")).scalar() == 0
