"""CardReviewView — SM-2 flashcard review session."""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QMessageBox, QProgressBar,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from services.accessibility.tts_service import TTSService
from services.cards.audio_service import AudioService
from services.quiz.card_session_controller import CardSessionController
from services.srs.srs_base import CardRating
from ui.components.audio_player import AudioPlayer
from ui.components.elapsed_timer import ElapsedTimer
from ui.components.rating_buttons import RatingButtons
from ui.components.tts_button import TtsButton


class CardReviewView(QWidget):
    """Two-state flashcard widget: front → flip → back + rate.

    Emits session_finished() when all cards have been rated.
    """

    session_finished = pyqtSignal()

    def __init__(self, tts: TTSService, audio_svc: AudioService,
                 parent=None) -> None:
        super().__init__(parent)
        self._tts = tts
        self._audio_svc = audio_svc
        self._ctrl = CardSessionController()
        self._session_id: int | None = None
        self._current_card_id: int | None = None
        self._showing_front = True
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Progress bar + timer row
        top = QHBoxLayout()
        self._progress = QProgressBar()
        self._progress.setTextVisible(True)
        top.addWidget(self._progress)
        self._timer = ElapsedTimer()
        top.addWidget(self._timer)
        layout.addLayout(top)

        # Card face
        self._card_label = QLabel("No session active")
        self._card_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._card_label.setWordWrap(True)
        self._card_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._card_label.setMinimumHeight(180)
        self._card_label.setStyleSheet(
            "border: 2px solid #CCCCCC; border-radius: 8px; padding: 16px;"
            "font-size: 14pt;"
        )
        layout.addWidget(self._card_label)

        # Accessibility row
        acc = QHBoxLayout()
        self._tts_btn = TtsButton(self._tts)
        self._player = AudioPlayer(self._audio_svc)
        acc.addWidget(self._tts_btn)
        acc.addWidget(self._player)
        acc.addStretch()
        layout.addLayout(acc)

        # Flip button (visible on front side)
        self._flip_btn = QPushButton("Show Answer  ↵")
        self._flip_btn.setMinimumHeight(36)
        self._flip_btn.clicked.connect(self._flip)
        layout.addWidget(self._flip_btn)

        # Rating buttons (visible on back side)
        self._rating = RatingButtons()
        self._rating.rating_selected.connect(self._submit_rating)
        self._rating.setVisible(False)
        layout.addWidget(self._rating)

        # End session button
        self._end_btn = QPushButton("End Session")
        self._end_btn.clicked.connect(self._end_session)
        layout.addWidget(self._end_btn)

    # ------------------------------------------------------------------
    # Session control
    # ------------------------------------------------------------------

    def start_session(self, deck_id: int) -> None:
        quiz = self._ctrl.start(deck_id)
        if quiz is None:
            QMessageBox.information(self, "No Cards Due",
                                    "No cards are due for review right now.")
            self.session_finished.emit()
            return
        self._session_id = quiz.id
        self._progress.setMaximum(quiz.total_items)
        self._progress.setValue(0)
        self._next_card()

    def resume_session(self, session_id: int) -> None:
        quiz = self._ctrl.resume(session_id)
        if quiz is None:
            self.session_finished.emit()
            return
        self._session_id = quiz.id
        self._progress.setMaximum(quiz.total_items)
        self._progress.setValue(quiz.items_reviewed)
        self._next_card()

    # ------------------------------------------------------------------
    # Card flow
    # ------------------------------------------------------------------

    def _next_card(self) -> None:
        if self._session_id is None:
            return
        card = self._ctrl.get_next_card(self._session_id)
        if card is None:
            self._finish()
            return

        self._current_card_id = card.id
        self._showing_front = True
        self._card_label.setText(card.front_text or "(no front text)")
        self._tts_btn.set_text(card.front_text or "")
        self._player.set_path(card.audio_path)
        self._flip_btn.setVisible(True)
        self._rating.setVisible(False)
        self._rating.set_enabled(False)
        self._timer.start()

    def _flip(self) -> None:
        if self._session_id is None or self._current_card_id is None:
            return
        card = self._get_card(self._current_card_id)
        if card is None:
            return
        self._showing_front = False
        self._card_label.setText(
            f"<b>Q:</b> {card.front_text or ''}<hr>"
            f"<b>A:</b> {card.back_text or ''}"
        )
        self._tts_btn.set_text(card.back_text or "")
        self._flip_btn.setVisible(False)
        self._rating.setVisible(True)
        self._rating.set_enabled(True)

    def _submit_rating(self, rating: CardRating) -> None:
        if self._session_id is None or self._current_card_id is None:
            return
        self._timer.stop()
        self._rating.set_enabled(False)
        self._tts_btn.reset()
        ok = self._ctrl.submit_rating(
            self._session_id, self._current_card_id, rating
        )
        if not ok:
            QMessageBox.warning(self, "Error", "Failed to save rating.")
            return

        # Refresh progress from DB
        self._update_progress()

        # Check if session is now complete
        db = __import__("models.base", fromlist=["get_session"]).get_session()
        try:
            from repositories.quiz_session_repository import QuizSessionRepository
            quiz = QuizSessionRepository(db).get(self._session_id)
            if quiz and quiz.status == "complete":
                self._finish()
                return
        finally:
            db.close()

        self._next_card()

    def _update_progress(self) -> None:
        if self._session_id is None:
            return
        db = __import__("models.base", fromlist=["get_session"]).get_session()
        try:
            from repositories.quiz_session_repository import QuizSessionRepository
            quiz = QuizSessionRepository(db).get(self._session_id)
            if quiz:
                self._progress.setValue(quiz.items_reviewed)
        finally:
            db.close()

    def _finish(self) -> None:
        self._card_label.setText("Session complete!")
        self._flip_btn.setVisible(False)
        self._rating.setVisible(False)
        self._timer.stop()
        self._tts_btn.reset()
        self.session_finished.emit()

    def _end_session(self) -> None:
        if self._session_id is not None:
            ans = QMessageBox.question(self, "End Session",
                                       "End this session early?")
            if ans == QMessageBox.StandardButton.Yes:
                self._ctrl.discard(self._session_id)
                self._session_id = None
                self.session_finished.emit()

    @staticmethod
    def _get_card(card_id: int):
        db = __import__("models.base", fromlist=["get_session"]).get_session()
        try:
            from repositories.card_repository import CardRepository
            return CardRepository(db).get(card_id)
        finally:
            db.close()
