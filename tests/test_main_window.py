from app.main_window import MainWindow
from app.navigation import Destination
from core.paths import get_app_paths
from core.settings import Settings
from ui.theme.theme_controller import ThemeController


def _make_window(qapp, tmp_path):
    settings = Settings.load(tmp_path / "s.json")
    controller = ThemeController(settings)
    controller.apply(qapp)
    paths = get_app_paths(base=tmp_path / "data")
    return MainWindow(settings, controller, paths)


def test_window_builds_with_all_destinations(qapp, tmp_path):
    window = _make_window(qapp, tmp_path)
    for dest in Destination:
        assert dest in window._pages
        assert dest in window._nav_buttons


def test_navigation_updates_active_state_and_title(qapp, tmp_path):
    window = _make_window(qapp, tmp_path)
    window._navigate(Destination.CARDS)
    assert window._nav_buttons[Destination.CARDS].property("active") is True
    assert window._nav_buttons[Destination.DASHBOARD].property("active") is False
    assert window._title.text() == "Cards"


def test_nav_buttons_have_accessible_names(qapp, tmp_path):
    window = _make_window(qapp, tmp_path)
    for dest, button in window._nav_buttons.items():
        assert button.accessibleName()  # SR-01: every control is named
