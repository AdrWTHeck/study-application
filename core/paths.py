"""Writable app-data path resolution.

PRV-01 / packaging: all writable data lives in a per-user app-data directory,
*never* beside the binary. In development (running from source) data stays
in-project under ``user_data/`` for convenience; when frozen by PyInstaller it
moves to the platform's per-user location.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "StudyApp"


def _project_root() -> Path:
    # core/paths.py -> core/ -> project root
    return Path(__file__).resolve().parent.parent


def assets_dir() -> Path:
    """Bundled, read-only asset directory (fonts, icons, seeds).

    Resolves correctly both from source and inside a PyInstaller one-folder build.
    """
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "assets"
    return _project_root() / "assets"


def _base_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        # Packaged build: use the per-user, writable location for the platform.
        if sys.platform == "win32":
            root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        elif sys.platform == "darwin":
            root = Path.home() / "Library" / "Application Support"
        else:
            root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        return root / APP_NAME
    # Development: keep everything in-project.
    return _project_root() / "user_data"


@dataclass(frozen=True)
class AppPaths:
    """Resolved, absolute locations for all writable data."""

    data_dir: Path
    db_path: Path
    settings_path: Path
    audio_dir: Path
    backups_dir: Path
    dictionary_path: Path

    def ensure(self) -> "AppPaths":
        for directory in (self.data_dir, self.audio_dir, self.backups_dir):
            directory.mkdir(parents=True, exist_ok=True)
        return self


def get_app_paths(base: Path | None = None) -> AppPaths:
    """Return resolved app paths, creating the directories if needed.

    ``base`` overrides the data directory (used by tests for isolation).
    """
    root = base or _base_data_dir()
    return AppPaths(
        data_dir=root,
        db_path=root / "study_app.db",
        settings_path=root / "settings.json",
        audio_dir=root / "audio",
        backups_dir=root / "backups",
        dictionary_path=root / "wiktionary.db",
    ).ensure()
