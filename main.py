"""Study App — Accessibility-First Redesign of Anki. Entry point.

Boot order: resolve writable paths → load settings → create the Qt app → apply
the accessibility-first theme → show the window. (Onboarding routing and the DB
bootstrap are wired in as their Phase 1 pieces land.)
"""
from __future__ import annotations

import logging
import sys


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(name)s: %(message)s",
    )

    from PyQt6.QtWidgets import QApplication, QMessageBox

    from app.main_window import MainWindow
    from core.paths import assets_dir, get_app_paths
    from core.settings import Settings
    from core.startup import run_startup
    from domain.accessibility.tts_service import TTSService
    from ui.a11y.speech import FocusSpeaker
    from ui.theme.fonts import load_application_fonts
    from ui.theme.theme_controller import ThemeController

    paths = get_app_paths()
    settings = Settings.load(paths.settings_path)

    app = QApplication(sys.argv)
    app.setApplicationName("StudyApp")
    app.setApplicationDisplayName("StudyApp")

    load_application_fonts(assets_dir() / "fonts")
    theme = ThemeController(settings)
    theme.apply(app)

    startup = run_startup(paths)
    if not startup.success:
        QMessageBox.critical(
            None,
            "StudyApp — database problem",
            "The study database failed its integrity check and could not be opened.\n\n"
            f"Most recent backup: {startup.most_recent_backup or 'none found'}\n\n"
            "Restore a backup from the backups folder, then relaunch.",
        )
        return 1

    tts = TTSService()
    tts.set_rate(int(settings.get("tts_rate")))
    # Kept referenced for the app's lifetime so the focus→speech hook stays live.
    focus_speaker = FocusSpeaker(app, tts, settings)  # noqa: F841

    if not settings.get("onboarding_complete"):
        from app.onboarding import OnboardingDialog

        OnboardingDialog(settings, tts).exec()

    window = MainWindow(settings, theme, paths, startup.db, tts)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
