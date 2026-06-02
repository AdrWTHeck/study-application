"""Dev-only: render the shell headlessly to PNGs to eyeball the token system.

Run: python tools/_smoke_shell.py  (uses the offscreen Qt platform)
Outputs to tools/_preview/. Not part of the app or test suite.
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
from core.paths import get_app_paths  # noqa: E402
from core.settings import Settings  # noqa: E402
from ui.theme.theme_controller import ThemeController  # noqa: E402

app = QApplication([])
tmp = Path(tempfile.mkdtemp())
out = Path(__file__).resolve().parent / "_preview"
out.mkdir(parents=True, exist_ok=True)


def render(theme: str, mode: str, name: str, dest: Destination = Destination.DASHBOARD) -> None:
    settings = Settings.load(tmp / f"{name}.json")
    settings.update({"theme": theme, "mode": mode})
    controller = ThemeController(settings)
    controller.apply(app)
    window = MainWindow(settings, controller, get_app_paths(base=tmp / name))
    window.resize(1040, 720)
    window._navigate(dest)
    window.show()
    app.processEvents()
    path = out / f"{name}.png"
    window.grab().save(str(path))
    print("saved", path)
    window.close()


render("dark", "accessibility", "dark_accessibility")
render("hc_dark", "accessibility", "hc_dark")
render("light", "advanced", "light_advanced", Destination.CARDS)
print("done")
