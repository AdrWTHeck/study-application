"""Speak-focused-control mode (TTS-02).

When ``tts_ui_enabled`` is on, reads the accessible name of each widget as it
gains focus — a lightweight complement to a real screen reader for users who
want spoken UI feedback without one. Gated by the setting and observes changes
to it live.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QApplication, QWidget

from core.settings import Settings
from domain.accessibility.tts_service import TTSService


class FocusSpeaker:
    def __init__(self, app: QApplication, tts: TTSService, settings: Settings) -> None:
        self._tts = tts
        self._settings = settings
        self._enabled = bool(settings.get("tts_ui_enabled"))
        app.focusChanged.connect(self._on_focus_changed)
        settings.subscribe(self._on_setting_changed)

    def _on_setting_changed(self, key: str, value: object) -> None:
        if key == "tts_ui_enabled":
            self._enabled = bool(value)

    def _on_focus_changed(self, _old: QWidget | None, now: QWidget | None) -> None:
        if not self._enabled or now is None:
            return
        label = now.accessibleName()
        if not label and hasattr(now, "text"):
            try:
                label = now.text()
            except Exception:
                label = ""
        if label:
            self._tts.speak(label)
