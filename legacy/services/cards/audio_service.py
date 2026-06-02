"""Audio recording and playback via sounddevice + soundfile."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from config.constants import AUDIO_FORMAT, AUDIO_MAX_DURATION_SECONDS
from services.core.startup import AUDIO_DIR

logger = logging.getLogger(__name__)

_CHANNELS = 1
_SAMPLE_RATE = 44100
_DTYPE = "int16"


class AudioService:
    """Non-blocking audio recorder backed by sounddevice.

    Record lifecycle:
        path = svc.record(card_id)   # starts background thread
        ...user speaks...
        svc.stop_recording()         # flushes WAV to *path*

    Playback is synchronous (blocks until the file finishes).
    All methods degrade gracefully when sounddevice/soundfile are unavailable.
    """

    def __init__(self) -> None:
        self._recording = False
        self._thread: threading.Thread | None = None
        self._current_path: str | None = None

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(self, card_id: int) -> str:
        """Start background recording; return the path where the WAV will be saved."""
        if self._recording:
            self.stop_recording()

        filename = f"card_{card_id}_{int(time.time())}.{AUDIO_FORMAT}"
        path = str(AUDIO_DIR / filename)
        self._current_path = path
        self._recording = True

        self._thread = threading.Thread(
            target=self._record_worker, args=(path,), daemon=True
        )
        self._thread.start()
        return path

    def stop_recording(self) -> None:
        """Signal the recording thread to stop and wait for the WAV to flush."""
        self._recording = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._thread = None

    def delete_audio(self, audio_path: str) -> None:
        """Remove an audio file from disk; silently ignores missing files."""
        try:
            p = Path(audio_path)
            if p.exists():
                p.unlink()
                logger.debug("Deleted audio file %r.", audio_path)
        except OSError:
            logger.exception("Failed to delete audio file %r.", audio_path)

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def playback(self, audio_path: str) -> None:
        """Play a WAV file synchronously (blocks until playback finishes)."""
        try:
            import sounddevice as sd  # type: ignore[import]
            import soundfile as sf    # type: ignore[import]
        except ImportError:
            logger.warning("sounddevice/soundfile not installed; playback unavailable.")
            return

        try:
            data, samplerate = sf.read(audio_path, dtype=_DTYPE)
            sd.play(data, samplerate)
            sd.wait()
        except Exception:
            logger.exception("Playback failed for %r.", audio_path)

    # ------------------------------------------------------------------
    # Internal recording worker
    # ------------------------------------------------------------------

    def _record_worker(self, path: str) -> None:
        try:
            import sounddevice as sd  # type: ignore[import]
            import soundfile as sf    # type: ignore[import]
        except ImportError:
            logger.warning("sounddevice/soundfile not installed; recording unavailable.")
            self._recording = False
            return

        max_frames = AUDIO_MAX_DURATION_SECONDS * _SAMPLE_RATE
        frames: list = []

        try:
            with sd.InputStream(
                samplerate=_SAMPLE_RATE,
                channels=_CHANNELS,
                dtype=_DTYPE,
            ) as stream:
                while self._recording and len(frames) < max_frames:
                    chunk, _ = stream.read(1024)
                    frames.extend(chunk)
        except Exception:
            logger.exception("Error during audio recording.")

        if frames:
            try:
                import numpy as np
                sf.write(path, np.array(frames, dtype=_DTYPE),
                         _SAMPLE_RATE, subtype="PCM_16")
                logger.debug("Audio saved to %r (%d frames).", path, len(frames))
            except Exception:
                logger.exception("Failed to write audio file %r.", path)
