"""TtsButton — toggle button that speaks / stops the current text."""
from __future__ import annotations

from PyQt6.QtWidgets import QPushButton

from services.accessibility.tts_service import TTSService


class TtsButton(QPushButton):
    """A QPushButton that speaks a text string via TTSService.

    Call set_text() to update the phrase to be spoken before the user
    clicks.  While speaking the label changes to 'Stop'.
    """

    def __init__(self, tts: TTSService, parent=None) -> None:
        super().__init__("Speak", parent)
        self._tts = tts
        self._text = ""
        self.setToolTip("Read text aloud (TTS)")
        self.clicked.connect(self._toggle)

    def set_text(self, text: str) -> None:
        self._text = text

    def _toggle(self) -> None:
        if self._tts.is_speaking():
            self._tts.stop()
            self.setText("Speak")
        else:
            self._tts.speak(self._text)
            self.setText("Stop")

    def reset(self) -> None:
        self._tts.stop()
        self.setText("Speak")
