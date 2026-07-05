"""Boot smoke: the full startup path builds the DB, seeds, constructs the main
window, and every view renders without raising."""
from app.main_window import MainWindow
from app.navigation import Destination
from core.paths import get_app_paths
from core.settings import Settings
from core.startup import run_startup
from ui.theme.theme_controller import ThemeController


def test_app_boots_and_every_view_constructs(qapp, tmp_path):
    paths = get_app_paths(base=tmp_path / "user_data")
    settings = Settings.load(paths.settings_path)
    theme = ThemeController(settings)
    theme.apply(qapp)

    startup = run_startup(paths)
    assert startup.success and startup.db is not None

    window = MainWindow(settings, theme, paths, startup.db)
    # Every primary destination + Settings must navigate without raising.
    for dest in Destination:
        window._navigate(dest)
    assert window._stack.count() >= len(list(Destination))


def test_app_boots_in_advanced_mode(qapp, tmp_path):
    paths = get_app_paths(base=tmp_path / "user_data")
    settings = Settings.load(paths.settings_path)
    settings.set("mode", "advanced")
    theme = ThemeController(settings)
    theme.apply(qapp)
    startup = run_startup(paths)
    window = MainWindow(settings, theme, paths, startup.db)
    for dest in Destination:
        window._navigate(dest)
    assert startup.success
