from core.paths import get_app_paths


def test_paths_are_created(tmp_path):
    paths = get_app_paths(base=tmp_path / "d")
    assert paths.data_dir.exists()
    assert paths.audio_dir.exists()
    assert paths.backups_dir.exists()


def test_path_layout(tmp_path):
    paths = get_app_paths(base=tmp_path / "d")
    assert paths.db_path.parent == paths.data_dir
    assert paths.settings_path.name == "settings.json"
    assert paths.dictionary_path.name == "wiktionary.db"
