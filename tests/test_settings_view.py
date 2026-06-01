from core.settings import Settings
from ui.views.settings_view import SettingsView


def _view(qapp, tmp_path) -> SettingsView:
    return SettingsView(Settings.load(tmp_path / "s.json"))


def test_theme_combo_updates_settings(qapp, tmp_path):
    settings = Settings.load(tmp_path / "s.json")
    view = SettingsView(settings)
    view.theme_combo.setCurrentIndex(2)  # hc_dark
    assert settings.get("theme") == "hc_dark"


def test_mode_combo_updates_settings(qapp, tmp_path):
    settings = Settings.load(tmp_path / "s.json")
    view = SettingsView(settings)
    view.mode_combo.setCurrentIndex(1)  # advanced
    assert settings.get("mode") == "advanced"


def test_font_scale_slider_updates_settings(qapp, tmp_path):
    settings = Settings.load(tmp_path / "s.json")
    view = SettingsView(settings)
    view.scale_slider.setValue(150)
    assert settings.get("font_scale") == 1.5


def test_tts_ui_toggle_updates_settings(qapp, tmp_path):
    settings = Settings.load(tmp_path / "s.json")
    view = SettingsView(settings)
    view.tts_ui.setChecked(True)
    assert settings.get("tts_ui_enabled") is True


def test_controls_have_accessible_names(qapp, tmp_path):
    view = _view(qapp, tmp_path)
    assert view.theme_combo.accessibleName()
    assert view.scale_slider.accessibleName()
    assert view.font_combo.accessibleName()
