from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QApplication

from core.settings import Settings
from ui.theme.theme_controller import ThemeController
from app.context import AppContext
from ui.views.reader_view import ReaderView


def test_theme_controller_updates_qss_and_views(qapp, tmp_path):
    # Prepare settings and theme
    settings_path = tmp_path / "settings.json"
    settings = Settings(settings_path)
    theme = ThemeController(settings)
    # Apply initial theme to the running QApplication
    theme.apply(QApplication.instance())

    # Build a minimal AppContext with the theme and create a ReaderView.
    # Deliberately NOT shown: showing the reader would lazily create its
    # QWebEngineView (Chromium), which hard-crashes under the offscreen
    # platform ("Headless tests never show the widget" — reader_view.py).
    ctx = AppContext(db=None, engine=object(), settings=settings, theme=theme)
    view = ReaderView(ctx)

    # Toggle mode to trigger density change (comfortable -> compact)
    settings.set("mode", "advanced")
    qapp.processEvents()

    # After change, reader should receive the theme change callback.
    assert view._theme_applied_count > 0
    assert theme.tokens.density.name == "compact"
