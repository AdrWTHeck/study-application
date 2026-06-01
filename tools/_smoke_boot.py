"""Dev-only end-to-end boot check (offscreen): exercises the full main() wiring —
startup, theme, TTS, focus-speaker, window, navigation, and a live re-theme —
without launching a real window. Run: python tools/_smoke_boot.py
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication  # noqa: E402

from app.main_window import MainWindow  # noqa: E402
from app.navigation import Destination  # noqa: E402
from core.paths import assets_dir, get_app_paths  # noqa: E402
from core.settings import Settings  # noqa: E402
from core.startup import run_startup  # noqa: E402
from domain.accessibility.tts_service import TTSService  # noqa: E402
from ui.a11y.speech import FocusSpeaker  # noqa: E402
from ui.theme.fonts import load_application_fonts  # noqa: E402
from ui.theme.theme_controller import ThemeController  # noqa: E402

tmp = Path(tempfile.mkdtemp())
paths = get_app_paths(base=tmp)
settings = Settings.load(paths.settings_path)
settings.set("onboarding_complete", True)

app = QApplication([])
load_application_fonts(assets_dir() / "fonts")
theme = ThemeController(settings)
theme.apply(app)

startup = run_startup(paths)
assert startup.success, "startup failed integrity check"

tts = TTSService(autostart=False)
focus_speaker = FocusSpeaker(app, tts, settings)  # noqa: F841

window = MainWindow(settings, theme, paths, startup.db, tts)
window.show()
app.processEvents()

window._navigate(Destination.SETTINGS)
app.processEvents()
settings.set("theme", "hc_dark")   # live re-theme while shown
settings.set("mode", "advanced")   # live density swap
app.processEvents()

print("BOOT OK — theme:", theme.tokens.palette.name, "| density:", theme.tokens.density.name)
