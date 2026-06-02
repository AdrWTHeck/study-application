"""AudioRecorder — Record/Stop buttons that call AudioService."""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from services.cards.audio_service import AudioService


class AudioRecorder(QWidget):
    """Record/Stop button pair for card audio.

    Emits recording_saved(path: str) when recording is successfully stopped
    and the WAV file has been flushed to disk.
    """

    recording_saved = pyqtSignal(str)   # absolute WAV path

    def __init__(self, audio_service: AudioService, parent=None) -> None:
        super().__init__(parent)
        self._svc = audio_service
        self._card_id: int | None = None
        self._current_path: str | None = None
        self._recording = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._record_btn = QPushButton("Record")
        self._record_btn.setFixedWidth(80)
        self._record_btn.clicked.connect(self._toggle)
        self._record_btn.setEnabled(False)

        self._status = QLabel("–")
        layout.addWidget(self._record_btn)
        layout.addWidget(self._status)

    def set_card_id(self, card_id: int) -> None:
        self._card_id = card_id
        self._record_btn.setEnabled(True)

    def _toggle(self) -> None:
        if self._recording:
            self._svc.stop_recording()
            self._recording = False
            self._record_btn.setText("Record")
            self._status.setText("Saved")
            if self._current_path:
                self.recording_saved.emit(self._current_path)
        else:
            if self._card_id is None:
                return
            self._current_path = self._svc.record(self._card_id)
            self._recording = True
            self._record_btn.setText("Stop")
            self._status.setText("Recording…")

    def stop_if_recording(self) -> str | None:
        """Programmatically stop and return the path (called when dialog closes)."""
        if self._recording:
            self._toggle()
        return self._current_path
