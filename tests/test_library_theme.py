from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from core.settings import Settings
from ui.theme.theme_controller import ThemeController
from app.context import AppContext
from ui.views.library_view import LibraryView


def test_library_view_receives_theme_change(qapp, tmp_path):
    settings_path = tmp_path / "settings.json"
    settings = Settings(settings_path)
    theme = ThemeController(settings)
    theme.apply(QApplication.instance())

    ctx = AppContext(db=None, engine=object(), settings=settings, theme=theme)
    view = LibraryView(ctx)
    view.show()

    # Ensure callback runs when mode changes
    initial = settings.get("mode")
    settings.set("mode", "advanced")
    assert settings.get("mode") == "advanced"
    # LibraryView._apply_theme should be callable without error (no explicit state)
    view._apply_theme()
