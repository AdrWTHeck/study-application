"""Text-to-speech service — Phase 5."""
from __future__ import annotations


class TTSService:
    def speak(self, text: str) -> None: raise NotImplementedError
    def stop(self) -> None: raise NotImplementedError
    def is_speaking(self) -> bool: raise NotImplementedError
    def set_rate(self, rate: int) -> None: raise NotImplementedError
    def set_voice(self, voice_id: str) -> None: raise NotImplementedError
    def get_available_voices(self) -> list[dict]: raise NotImplementedError
