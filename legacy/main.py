"""Study Application — entry point."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

from services.core.startup import run


def main() -> None:
    result = run()

    if not result.success:
        # Show error before Qt is even initialised (integrity failure is fatal)
        print(
            "[ERROR] Database integrity check failed.\n"
            f"Most recent backup: {result.most_recent_backup}\n"
            "Restore study_app.db from the backup or delete it to start fresh."
        )
        sys.exit(1)

    import traceback
    print("[DEBUG] Importing Qt...", flush=True)
    from PyQt6.QtWidgets import QApplication
    print("[DEBUG] Importing MainWindow...", flush=True)
    from ui.main_window import MainWindow
    print("[DEBUG] Importing StyleManager...", flush=True)
    from ui.theme.style_manager import StyleManager

    print("[DEBUG] Creating QApplication...", flush=True)
    app = QApplication(sys.argv)
    app.setApplicationName("Study App")

    print("[DEBUG] Creating StyleManager...", flush=True)
    style_mgr = StyleManager()
    style_mgr.set_app(app)

    settings = result.settings
    style_mgr.apply(settings)
    settings.register(style_mgr.apply)

    print("[DEBUG] Creating MainWindow...", flush=True)
    try:
        window = MainWindow(
            style_manager=style_mgr,
            pending_sessions=result.pending_sessions or [],
        )
    except Exception:
        traceback.print_exc()
        sys.exit(1)

    print("[DEBUG] Showing window...", flush=True)
    window.show()
    print("[DEBUG] Entering event loop...", flush=True)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
