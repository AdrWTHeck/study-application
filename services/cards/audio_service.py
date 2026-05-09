"""Audio recording/playback — Phase 4."""
from __future__ import annotations


class AudioService:
    def record(self, card_id: int) -> str: raise NotImplementedError
    def stop_recording(self) -> None: raise NotImplementedError
    def delete_audio(self, audio_path: str) -> None: raise NotImplementedError
