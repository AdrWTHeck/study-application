"""Observable, JSON-backed application settings.

Defaults are **accessibility-first** (ONB-02): a fresh install behaves with the
accessibility mode, generous typography, and content TTS on, with no
configuration required. Observers are notified on every change so the live
theme/typography update (VIS-01, RDG-01/02) works without a restart.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

Observer = Callable[[str, Any], None]

# Accessibility-first defaults — see docs/ACCESSIBILITY_INTEGRATION.md.
DEFAULTS: dict[str, Any] = {
    "mode": "accessibility",                 # "accessibility" | "advanced"  (§2 dual mode)
    "theme": "dark",                         # dark | light | hc_dark | hc_light  (VIS-02)
    "font_scale": 1.0,                       # 1.0–2.0 global multiplier (VIS-01)
    "font_family": "Atkinson Hyperlegible",  # dyslexia-friendly default (RDG-01)
    "line_height": 1.5,                      # RDG-02
    "letter_spacing": 0.0,                   # RDG-02 (absolute px)
    "word_spacing": 0.0,                     # RDG-02 (absolute px)
    "tts_content_enabled": True,             # TTS-01
    "tts_ui_enabled": False,                 # TTS-02 (opt-in)
    "tts_rate": 150,
    "tts_voice_id": None,
    "onboarding_complete": False,            # ONB-01
    "short_answer_fuzzy_threshold": 80,      # Phase 4 grading
    "custom_colors": {},                     # palette overrides
}


class Settings:
    """In-memory settings with persistence and change notification."""

    def __init__(self, path: Path, data: dict[str, Any] | None = None) -> None:
        self._path = path
        self._data: dict[str, Any] = {**DEFAULTS, **(data or {})}
        self._observers: list[Observer] = []

    # -- construction -------------------------------------------------------

    @classmethod
    def load(cls, path: Path) -> "Settings":
        data: dict[str, Any] = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                logger.exception("Failed to read settings at %s; using defaults.", path)
        return cls(path, data)

    # -- access -------------------------------------------------------------

    def get(self, key: str) -> Any:
        return self._data.get(key, DEFAULTS.get(key))

    def as_dict(self) -> dict[str, Any]:
        return dict(self._data)

    # -- mutation -----------------------------------------------------------

    def set(self, key: str, value: Any) -> None:
        if self._data.get(key) == value:
            return
        self._data[key] = value
        self.save()
        self._notify(key, value)

    def update(self, values: dict[str, Any]) -> None:
        changed = {k: v for k, v in values.items() if self._data.get(k) != v}
        if not changed:
            return
        self._data.update(changed)
        self.save()
        for key, value in changed.items():
            self._notify(key, value)

    # -- observation --------------------------------------------------------

    def subscribe(self, callback: Observer) -> Callable[[], None]:
        """Register *callback*; returns an unsubscribe function."""
        self._observers.append(callback)

        def _unsubscribe() -> None:
            if callback in self._observers:
                self._observers.remove(callback)

        return _unsubscribe

    def _notify(self, key: str, value: Any) -> None:
        for callback in list(self._observers):
            try:
                callback(key, value)
            except Exception:
                logger.exception("Settings observer failed for key %r.", key)

    # -- persistence --------------------------------------------------------

    def save(self) -> None:
        try:
            self._path.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("Failed to save settings to %s.", self._path)
