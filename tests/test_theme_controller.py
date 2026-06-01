from core.settings import Settings
from ui.theme.theme_controller import ThemeController


def test_apply_sets_stylesheet_and_font(qapp, tmp_path):
    settings = Settings.load(tmp_path / "s.json")
    controller = ThemeController(settings)
    controller.apply(qapp)
    assert qapp.styleSheet()  # non-empty global stylesheet


def test_mode_change_swaps_density_live(qapp, tmp_path):
    settings = Settings.load(tmp_path / "s.json")
    controller = ThemeController(settings)
    controller.apply(qapp)
    assert controller.tokens.density.name == "comfortable"  # accessibility default
    settings.set("mode", "advanced")  # observer triggers a live re-apply
    assert controller.tokens.density.name == "compact"


def test_changed_signal_emits_on_apply(qapp, tmp_path):
    settings = Settings.load(tmp_path / "s.json")
    controller = ThemeController(settings)
    fired = []
    controller.changed.connect(lambda: fired.append(1))
    controller.apply(qapp)
    assert fired
