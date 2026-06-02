from app.onboarding import OnboardingDialog
from core.settings import Settings


def test_finish_marks_onboarding_complete(qapp, tmp_path):
    settings = Settings.load(tmp_path / "s.json")
    dialog = OnboardingDialog(settings)
    assert settings.get("onboarding_complete") is False
    dialog._finish()
    assert settings.get("onboarding_complete") is True


def test_mode_selection_writes_setting(qapp, tmp_path):
    settings = Settings.load(tmp_path / "s.json")
    dialog = OnboardingDialog(settings)
    dialog.mode_advanced.setChecked(True)
    assert settings.get("mode") == "advanced"


def test_theme_and_scale_apply_live(qapp, tmp_path):
    settings = Settings.load(tmp_path / "s.json")
    dialog = OnboardingDialog(settings)
    dialog.theme_combo.setCurrentIndex(2)  # hc_dark
    dialog.scale_slider.setValue(160)
    assert settings.get("theme") == "hc_dark"
    assert settings.get("font_scale") == 1.6


def test_step_navigation(qapp, tmp_path):
    settings = Settings.load(tmp_path / "s.json")
    dialog = OnboardingDialog(settings)
    assert dialog._stack.currentIndex() == 0
    dialog._next()
    assert dialog._stack.currentIndex() == 1
    dialog._back()
    assert dialog._stack.currentIndex() == 0
