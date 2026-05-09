"""Study Application — entry point.

Adds the project root to sys.path so all absolute imports resolve correctly,
then runs the startup sequence.  Phase 5 will replace the placeholder with
the real PyQt6 MainWindow.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure the project root (study_app/) is on sys.path regardless of where
# the interpreter is invoked from.
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

from services.core.startup import run


def main() -> None:
    result = run()

    if not result.success:
        # Phase 5 will show a PyQt6 dialog here.
        print(
            "[ERROR] Database integrity check failed.\n"
            f"Most recent backup: {result.most_recent_backup}\n"
            "Replace study_app.db with the backup and restart, or delete the\n"
            "database to start fresh (all data will be lost)."
        )
        sys.exit(1)

    if result.pending_sessions:
        # Phase 5 will show a resume/discard dialog here.
        print(
            f"[INFO] {len(result.pending_sessions)} in-progress session(s) found.\n"
            "       Resume/discard UI will be implemented in Phase 5."
        )

    # Phase 5 — launch PyQt6 MainWindow here.
    print("[OK] Startup complete.  MainWindow will launch in Phase 5.")


if __name__ == "__main__":
    main()
