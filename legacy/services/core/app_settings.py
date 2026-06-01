"""AppSettings singleton — observable configuration store (FR-INF-03).

UI components call register(callback) at init-time.
Any call to set(**kwargs) persists the change and notifies all subscribers.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable

from config.constants import (
    DICTIONARY_SHORTCUT_DEFAULT,
    FONT_SIZE_DEFAULT,
    TTS_DEFAULT_RATE,
)

logger = logging.getLogger(__name__)

# Keys that are allowed in settings.json.  Unknown keys from disk are ignored.
_PERSISTED_KEYS = frozenset({
    "font_size",
    "theme",
    "custom_colors",
    "tts_rate",
    "tts_voice_id",
    "dictionary_panel_visible",
    "dictionary_panel_floating",
    "dictionary_shortcut",
})


class AppSettings:
    """Observable singleton for user preferences."""

    _instance: AppSettings | None = None

    @classmethod
    def get_instance(cls) -> AppSettings:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------

    def __init__(self) -> None:
        self._settings_path: Path | None = None
        self._subscribers: list[Callable[[AppSettings], None]] = []

        # --- Defaults (FR-INF-04 / FR-5-01–5-07) ----------------------
        self.font_size: int = FONT_SIZE_DEFAULT
        self.theme: str = "default"            # "default" | "high_contrast_dark" | "high_contrast_light"
        self.custom_colors: dict | None = None
        self.tts_rate: int = TTS_DEFAULT_RATE
        self.tts_voice_id: str | None = None
        self.dictionary_panel_visible: bool = False
        self.dictionary_panel_floating: bool = True
        self.dictionary_shortcut: str = DICTIONARY_SHORTCUT_DEFAULT

        # Runtime-only flag set by startup.py (not persisted)
        self.webster_available: bool = True

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self, settings_path: Path) -> None:
        """Load from *settings_path*, creating it with defaults if absent."""
        self._settings_path = settings_path
        if not settings_path.exists():
            self._save_to_disk()
            return
        try:
            with open(settings_path, encoding="utf-8") as fh:
                data: dict = json.load(fh)
            for key, value in data.items():
                if key in _PERSISTED_KEYS and hasattr(self, key):
                    setattr(self, key, value)
        except Exception:
            logger.exception("Failed to load settings from %s; using defaults.", settings_path)

    def _save_to_disk(self) -> None:
        if self._settings_path is None:
            return
        data = {k: getattr(self, k) for k in _PERSISTED_KEYS}
        try:
            self._settings_path.write_text(
                json.dumps(data, indent=2), encoding="utf-8"
            )
        except Exception:
            logger.exception("Failed to write settings to %s.", self._settings_path)

    # ------------------------------------------------------------------
    # Observer interface
    # ------------------------------------------------------------------

    def register(self, callback: Callable[[AppSettings], None]) -> None:
        """Subscribe *callback* to settings changes.  Safe to call multiple times."""
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unregister(self, callback: Callable[[AppSettings], None]) -> None:
        try:
            self._subscribers.remove(callback)
        except ValueError:
            pass

    def set(self, **kwargs) -> None:
        """Update one or more settings, persist, then notify all subscribers."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                logger.warning("AppSettings.set: unknown key %r ignored.", key)
        self._save_to_disk()
        for cb in list(self._subscribers):
            try:
                cb(self)
            except Exception:
                logger.exception("AppSettings subscriber raised an exception.")
