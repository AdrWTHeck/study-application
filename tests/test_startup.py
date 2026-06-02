from core.paths import get_app_paths
from core.startup import run_startup


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
