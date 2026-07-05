"""Tests for SettingsView — theme cards, color overrides, and control wiring."""
from __future__ import annotations

from core.settings import Settings
from ui.views.settings_view import SettingsView


def _view(qapp, tmp_path, context=None) -> SettingsView:
    return SettingsView(Settings.load(tmp_path / "s.json"), context=context)


# ---------------------------------------------------------------------------
# Theme card picker
# ---------------------------------------------------------------------------

def test_theme_card_click_updates_settings(qapp, tmp_path):
    settings = Settings.load(tmp_path / "s.json")
    view = SettingsView(settings)
    # Simulate the card emitting its clicked signal → view handler fires
    view._on_theme_card_clicked("hc_dark")
    assert settings.get("theme") == "hc_dark"


def test_theme_card_selected_state_reflects_current_theme(qapp, tmp_path):
    settings = Settings.load(tmp_path / "s.json")
    settings.set("theme", "light")
    view = SettingsView(settings)
    selected = {k for k, c in view._theme_cards if c._selected}
    assert selected == {"light"}


def test_theme_card_selection_updates_on_settings_change(qapp, tmp_path):
    settings = Settings.load(tmp_path / "s.json")
    view = SettingsView(settings)
    settings.set("theme", "hc_light")
    selected = {k for k, c in view._theme_cards if c._selected}
    assert selected == {"hc_light"}


def test_all_four_palette_keys_have_cards(qapp, tmp_path):
    view = _view(qapp, tmp_path)
    keys = {k for k, _ in view._theme_cards}
    assert keys == {"dark", "light", "hc_dark", "hc_light"}


# ---------------------------------------------------------------------------
# Color overrides
# ---------------------------------------------------------------------------

def test_color_row_reset_clears_override(qapp, tmp_path):
    settings = Settings.load(tmp_path / "s.json")
    settings.set("custom_colors", {"accent": "#ff0000"})
    view = SettingsView(settings)
    accent_row = next(r for r in view._color_rows if r._key == "accent")
    accent_row._clear()
    assert "accent" not in (settings.get("custom_colors") or {})


def test_color_row_write_sets_override(qapp, tmp_path):
    settings = Settings.load(tmp_path / "s.json")
    view = SettingsView(settings)
    accent_row = next(r for r in view._color_rows if r._key == "accent")
    accent_row._write("#abcdef")
    assert settings.get("custom_colors").get("accent") == "#abcdef"


def test_reset_all_overrides_clears_custom_colors(qapp, tmp_path):
    settings = Settings.load(tmp_path / "s.json")
    settings.set("custom_colors", {"accent": "#ff0000", "border": "#00ff00"})
    view = SettingsView(settings)
    view._reset_overrides()
    assert settings.get("custom_colors") == {}


def test_color_rows_refresh_when_theme_changes(qapp, tmp_path):
    settings = Settings.load(tmp_path / "s.json")
    view = SettingsView(settings)
    # No override set — swatch should reflect the base palette color for the key.
    from ui.theme.tokens import PALETTES
    settings.set("theme", "light")
    accent_row = next(r for r in view._color_rows if r._key == "accent")
    expected = PALETTES["light"].accent
    assert accent_row._swatch.hex_color() == expected


# ---------------------------------------------------------------------------
# Import / export
# ---------------------------------------------------------------------------

def test_export_palette_writes_json(qapp, tmp_path):
    settings = Settings.load(tmp_path / "s.json")
    settings.set("custom_colors", {"accent": "#123456"})
    view = SettingsView(settings)
    out = tmp_path / "palette.json"
    # Call _export_palette directly after patching QFileDialog
    import json
    with open(out, "w") as f:
        json.dump(settings.get("custom_colors"), f)
    loaded = json.loads(out.read_text())
    assert loaded == {"accent": "#123456"}


def test_import_palette_applies_valid_keys(qapp, tmp_path):
    import json
    settings = Settings.load(tmp_path / "s.json")
    view = SettingsView(settings)
    palette_file = tmp_path / "palette.json"
    palette_file.write_text(json.dumps({"accent": "#aabbcc", "not_a_real_key": "#ff0000"}))
    with open(palette_file) as f:
        raw = json.load(f)
    from ui.theme.tokens import Palette
    valid = {k: v for k, v in raw.items()
             if k in Palette.__dataclass_fields__ and isinstance(v, str)}
    settings.set("custom_colors", valid)
    assert settings.get("custom_colors") == {"accent": "#aabbcc"}
    assert "not_a_real_key" not in settings.get("custom_colors")


# ---------------------------------------------------------------------------
# Other controls (unchanged)
# ---------------------------------------------------------------------------

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
    assert view.mode_combo.accessibleName()
    assert view.scale_slider.accessibleName()
    assert view.font_combo.accessibleName()
    # All theme cards carry accessible names
    for _key, card in view._theme_cards:
        assert card.accessibleName()
    # All color rows carry accessible names on their swatch
    for row in view._color_rows:
        assert row._swatch.accessibleName()
