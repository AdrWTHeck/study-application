"""CardFormView — QDialog for creating or editing a card."""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QTextEdit, QVBoxLayout,
)

from services.cards.audio_service import AudioService
from services.cards.card_service import CardService
from ui.components.audio_player import AudioPlayer
from ui.components.audio_recorder import AudioRecorder


class CardFormView(QDialog):
    """Modal dialog for creating or editing a flashcard.

    Pass card_id=None for creation.  Emits card_saved(card_id) on success.
    """

    card_saved = pyqtSignal(int)

    def __init__(
        self,
        deck_id: int,
        card_service: CardService,
        audio_service: AudioService,
        card_id: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._deck_id = deck_id
        self._card_id = card_id
        self._svc = card_service
        self._audio_svc = audio_service
        self._audio_path: str | None = None

        self.setWindowTitle("Edit Card" if card_id else "New Card")
        self.setMinimumWidth(420)
        self._build_ui()
        if card_id:
            self._load(card_id)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._front = QTextEdit()
        self._front.setPlaceholderText("Front (question / prompt)")
        self._front.setMaximumHeight(100)
        form.addRow("Front:", self._front)

        self._back = QTextEdit()
        self._back.setPlaceholderText("Back (answer / explanation)")
        self._back.setMaximumHeight(100)
        form.addRow("Back:", self._back)

        layout.addLayout(form)

        # Audio row
        self._player = AudioPlayer(AudioService(), self)
        self._recorder = AudioRecorder(self._audio_svc, self)
        self._recorder.recording_saved.connect(self._on_recording_saved)
        audio_row = QHBoxLayout()
        audio_row.addWidget(self._player)
        audio_row.addWidget(self._recorder)
        layout.addLayout(audio_row)

        self._error = QLabel("")
        self._error.setStyleSheet("color: red;")
        layout.addWidget(self._error)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load(self, card_id: int) -> None:
        db = __import__("models.base", fromlist=["get_session"]).get_session()
        try:
            from repositories.card_repository import CardRepository
            card = CardRepository(db).get(card_id)
            if card:
                self._front.setPlainText(card.front_text or "")
                self._back.setPlainText(card.back_text or "")
                self._audio_path = card.audio_path
                self._player.set_path(card.audio_path)
                self._recorder.set_card_id(card_id)
        finally:
            db.close()

    def _save(self) -> None:
        front = self._front.toPlainText().strip()
        back = self._back.toPlainText().strip()
        if not front or not back:
            self._error.setText("Both front and back are required.")
            return
        self._recorder.stop_if_recording()

        if self._card_id:
            ok = self._svc.edit(
                self._card_id,
                front_text=front,
                back_text=back,
                audio_path=self._audio_path,
            )
            saved_id = self._card_id if ok else None
        else:
            card = self._svc.create(front, back, self._deck_id, self._audio_path)
            saved_id = card.id if card else None

        if saved_id is None:
            self._error.setText("Failed to save card.")
            return
        self.card_saved.emit(saved_id)
        self.accept()

    def _on_recording_saved(self, path: str) -> None:
        self._audio_path = path
        self._player.set_path(path)
