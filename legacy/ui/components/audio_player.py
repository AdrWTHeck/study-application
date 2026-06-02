"""AudioPlayer — play/stop button for a card's WAV file."""
from __future__ import annotations

import threading

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from services.cards.audio_service import AudioService


class AudioPlayer(QWidget):
    """Shows a Play/Stop button next to a filename label.

    Playback runs in a daemon thread so the UI stays responsive.
    """

    def __init__(self, audio_service: AudioService, parent=None) -> None:
        super().__init__(parent)
        self._svc = audio_service
        self._path: str | None = None
        self._thread: threading.Thread | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._play_btn = QPushButton("Play")
        self._play_btn.setFixedWidth(60)
        self._play_btn.setEnabled(False)
        self._play_btn.clicked.connect(self._toggle)

        self._label = QLabel("No audio")
        layout.addWidget(self._play_btn)
        layout.addWidget(self._label)

    def set_path(self, path: str | None) -> None:
        self._path = path
        if path:
            import os
            self._label.setText(os.path.basename(path))
            self._play_btn.setEnabled(True)
        else:
            self._label.setText("No audio")
            self._play_btn.setEnabled(False)

    def _toggle(self) -> None:
        if self._thread and self._thread.is_alive():
            self._play_btn.setText("Play")
            return  # let it finish; no stop API on playback
        if not self._path:
            return
        self._play_btn.setText("Stop")
        self._thread = threading.Thread(
            target=self._play_worker, daemon=True
        )
        self._thread.start()

    def _play_worker(self) -> None:
        try:
            self._svc.playback(self._path)
        finally:
            self._play_btn.setText("Play")
