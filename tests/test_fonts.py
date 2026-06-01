from PyQt6.QtGui import QFontDatabase

from ui.theme.fonts import load_application_fonts, resolve_family


def test_missing_dir_returns_empty(qapp, tmp_path):
    assert load_application_fonts(tmp_path / "nope") == set()


def test_ignores_non_font_files(qapp, tmp_path):
    fonts_dir = tmp_path / "fonts"
    fonts_dir.mkdir()
    (fonts_dir / "notes.txt").write_text("not a font", encoding="utf-8")
    assert load_application_fonts(fonts_dir) == set()


def test_resolve_family_never_returns_garbage(qapp):
    # Either the (unavailable) preferred name in a no-font environment, or a
    # genuinely available fallback — never an empty/invalid result.
    family = resolve_family("Definitely Not A Real Font 123")
    assert isinstance(family, str) and family
    assert family == "Definitely Not A Real Font 123" or family in set(QFontDatabase.families())
