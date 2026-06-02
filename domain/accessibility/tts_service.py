"""Offline text-to-speech via pyttsx3 (TTS-01 content, TTS-02 UI).

pyttsx3's runAndWait() blocks, so utterances run on a daemon thread; speaking
while busy interrupts the current utterance. Every method degrades silently when
pyttsx3 is unavailable, so TTS is never a hard dependency (offline-first).
"""
from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)


class TTSService:
    def __init__(self, autostart: bool = True) -> None:
        self._thread: threading.Thread | None = None
        self._speaking = False
        self._engine = None
        self._pending_rate: int | None = None
        self._pending_voice: str | None = None
        if autostart:
            self._init_engine()

    def _init_engine(self) -> None:
        try:
            import pyttsx3  # type: ignore[import-not-found]

            self._engine = pyttsx3.init()
        except Exception:
            logger.warning("pyttsx3 unavailable — TTS disabled.")

    @property
    def available(self) -> bool:
        return self._engine is not None

    # -- playback -----------------------------------------------------------

    def speak(self, text: str) -> None:
        if not self._engine or not text or not text.strip():
            return
        self.stop()
        self._speaking = True
        self._thread = threading.Thread(target=self._worker, args=(text,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._speaking = False
        if self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None

    def is_speaking(self) -> bool:
        return self._speaking and bool(self._thread and self._thread.is_alive())

    # -- configuration ------------------------------------------------------

    def set_rate(self, rate: int) -> None:
        self._pending_rate = rate
        if self._engine and not self.is_speaking():
            try:
                self._engine.setProperty("rate", rate)
            except Exception:
                pass

    def set_voice(self, voice_id: str) -> None:
        self._pending_voice = voice_id
        if self._engine and not self.is_speaking():
            try:
                self._engine.setProperty("voice", voice_id)
            except Exception:
                pass

    def get_available_voices(self) -> list[dict]:
        if not self._engine:
            return []
        try:
            voices = self._engine.getProperty("voices") or []
            return [{"id": v.id, "name": v.name} for v in voices]
        except Exception:
            return []

    # -- worker -------------------------------------------------------------

    def _worker(self, text: str) -> None:
        try:
            if self._pending_rate is not None:
                self._engine.setProperty("rate", self._pending_rate)
            if self._pending_voice is not None:
                self._engine.setProperty("voice", self._pending_voice)
            self._engine.say(text)
            self._engine.runAndWait()
        except Exception:
            logger.exception("TTS worker failed.")
        finally:
            self._speaking = False
