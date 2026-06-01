from core.settings import Settings


def test_defaults_are_accessibility_first(tmp_path):
    s = Settings.load(tmp_path / "settings.json")
    assert s.get("mode") == "accessibility"
    assert s.get("tts_content_enabled") is True
    assert s.get("onboarding_complete") is False


def test_set_persists_and_roundtrips(tmp_path):
    path = tmp_path / "settings.json"
    Settings.load(path).set("font_scale", 1.5)
    assert Settings.load(path).get("font_scale") == 1.5


def test_update_persists_multiple(tmp_path):
    path = tmp_path / "settings.json"
    Settings.load(path).update({"theme": "hc_dark", "font_scale": 1.25})
    reloaded = Settings.load(path)
    assert reloaded.get("theme") == "hc_dark"
    assert reloaded.get("font_scale") == 1.25


def test_observer_fires_on_change(tmp_path):
    s = Settings.load(tmp_path / "settings.json")
    seen = []
    s.subscribe(lambda k, v: seen.append((k, v)))
    s.set("theme", "hc_dark")
    assert ("theme", "hc_dark") in seen


def test_no_notify_when_value_unchanged(tmp_path):
    s = Settings.load(tmp_path / "settings.json")
    seen = []
    s.subscribe(lambda k, v: seen.append(k))
    s.set("theme", s.get("theme"))
    assert seen == []


def test_unsubscribe_stops_notifications(tmp_path):
    s = Settings.load(tmp_path / "settings.json")
    seen = []
    off = s.subscribe(lambda k, v: seen.append(k))
    off()
    s.set("theme", "light")
    assert seen == []


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ not valid json", encoding="utf-8")
    s = Settings.load(path)
    assert s.get("mode") == "accessibility"
