import pytest

from ui.a11y.contrast import AA_NORMAL, AAA_NORMAL, contrast_ratio
from ui.theme import tokens as tk
from ui.theme.qss.builder import build_qss

ALL_THEMES = ["dark", "light", "hc_dark", "hc_light"]


@pytest.mark.parametrize("name", ALL_THEMES)
def test_build_tokens_for_each_theme(name):
    tokens = tk.build_tokens(theme=name)
    assert tokens.palette.name == name
    qss = build_qss(tokens)
    assert tokens.palette.bg_base in qss
    assert "QPushButton" in qss


def test_unknown_theme_falls_back_to_dark():
    assert tk.build_tokens(theme="nope").palette.name == "dark"


def test_font_scale_is_clamped():
    assert tk.build_tokens(font_scale=5.0).typography.scale == 2.0
    assert tk.build_tokens(font_scale=0.1).typography.scale == 1.0


def test_font_scale_increases_effective_size():
    base = tk.build_tokens(font_scale=1.0).typography.size("body")
    scaled = tk.build_tokens(font_scale=2.0).typography.size("body")
    assert scaled > base


def test_density_mapping():
    assert tk.build_tokens(density="comfortable").density.min_target >= 44
    assert tk.build_tokens(density="compact").density.name == "compact"


def test_layout_axis_present_and_scales_with_density():
    comfortable = tk.build_tokens(density="comfortable").layout
    compact = tk.build_tokens(density="compact").layout
    # The layout axis tracks density and tightens the shell in compact mode.
    assert comfortable.name == "comfortable"
    assert compact.name == "compact"
    assert comfortable.topbar_height > 0
    assert compact.topbar_height < comfortable.topbar_height
    # Named content widths stay ordered narrow < focused < balanced < wide <= full.
    for layout in (comfortable, compact):
        assert layout.width_narrow < layout.width_focused
        assert layout.width_focused < layout.width_balanced < layout.width_wide
        assert layout.width_wide <= layout.width_full
        assert layout.deck_pane_width > 0
    # content_width() resolves known classes and falls back to balanced.
    assert comfortable.content_width("narrow") == comfortable.width_narrow
    assert comfortable.content_width("focused") == comfortable.width_focused
    assert comfortable.content_width("full") == comfortable.width_full
    assert comfortable.content_width("unknown") == comfortable.width_balanced


def test_unknown_density_layout_falls_back_to_comfortable():
    assert tk.build_tokens(density="nope").layout.name == "comfortable"


def test_custom_color_override_applies():
    tokens = tk.build_tokens(theme="dark", custom_colors={"accent": "#123456"})
    assert tokens.palette.accent == "#123456"


@pytest.mark.parametrize("name", ALL_THEMES)
def test_primary_text_meets_aa(name):
    # VIS-02: primary text must meet at least AA on base and surface.
    p = tk.PALETTES[name]
    assert contrast_ratio(p.text_primary, p.bg_base) >= AA_NORMAL
    assert contrast_ratio(p.text_primary, p.bg_surface) >= AA_NORMAL


@pytest.mark.parametrize("name", ["hc_dark", "hc_light"])
def test_high_contrast_themes_meet_aaa(name):
    # VIS-02: high-contrast themes target the stricter AAA ratio.
    p = tk.PALETTES[name]
    assert contrast_ratio(p.text_primary, p.bg_base) >= AAA_NORMAL


@pytest.mark.parametrize("name", ALL_THEMES)
def test_accent_text_pairing_is_legible(name):
    # Text drawn on the accent fill (e.g. default buttons) must be readable.
    p = tk.PALETTES[name]
    assert contrast_ratio(p.on_accent, p.accent) >= AA_NORMAL
