"""Guided review — one card at a time (COG-01).

Shows the front, reveals the back on Space / "Show answer", then four rating
buttons (1–4). Learning cards due again within the session reappear at the end.
Content TTS reads the visible side when enabled. Holds one DB session open for
the duration of the session; commits after each answer.
"""
from __future__ import annotations

from datetime import timedelta

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut, QTextDocument
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from core.clock import now
from domain.cards.review_service import ReviewService
from domain.notes.rendering import render_side
from domain.srs.srs_base import Rating

_REQUEUE_WINDOW_MIN = 20
_RATINGS = [
    ("Again", Rating.AGAIN),
    ("Hard", Rating.HARD),
    ("Good", Rating.GOOD),
    ("Easy", Rating.EASY),
]


class ReviewView(QWidget):
    finished = pyqtSignal()

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setObjectName("Page")
        self.setAccessibleName("Review session")

        self._session = None
        self._review: ReviewService | None = None
        self._queue: list = []
        self._index = 0
        self._revealed = False

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 24, 40, 24)
        root.setSpacing(12)

        header = QHBoxLayout()
        self._progress = QLabel("")
        self._progress.setObjectName("SettingsHint")
        end_btn = QPushButton("End session")
        end_btn.setAccessibleName("End session")
        end_btn.clicked.connect(self._finish)
        header.addWidget(self._progress)
        header.addStretch(1)
        header.addWidget(end_btn)
        root.addLayout(header)

        self._face = QTextBrowser()
        self._face.setObjectName("CardFace")
        self._face.setAccessibleName("Card")
        self._face.setOpenLinks(False)
        root.addWidget(self._face, 1)

        self._speak_btn = QPushButton("🔊  Speak")
        self._speak_btn.setAccessibleName("Speak card")
        self._speak_btn.clicked.connect(self._speak)
        root.addWidget(self._speak_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self._show_btn = QPushButton("Show answer")
        self._show_btn.setAccessibleName("Show answer")
        self._show_btn.clicked.connect(self._reveal)
        root.addWidget(self._show_btn)

        self._ratings_row = QWidget()
        ratings = QHBoxLayout(self._ratings_row)
        ratings.setContentsMargins(0, 0, 0, 0)
        self._rating_buttons: list[QPushButton] = []
        for i, (label, rating) in enumerate(_RATINGS, start=1):
            button = QPushButton(f"{label} ({i})")
            button.setAccessibleName(label)
            button.setShortcut(str(i))
            button.clicked.connect(lambda _=False, r=rating: self._rate(r))
            ratings.addWidget(button)
            self._rating_buttons.append(button)
        root.addWidget(self._ratings_row)

        self._empty = QLabel("")
        self._empty.setObjectName("PageSubtitle")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        root.addWidget(self._empty)

        reveal_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        reveal_shortcut.activated.connect(self._on_space)

    # -- session lifecycle --------------------------------------------------

    def start(self, deck_id: int) -> None:
        self._close_session()
        if self._context.db is None:
            return
        self._session = self._context.db.new_session()
        self._review = ReviewService(self._session, self._context.engine)
        self._queue = self._review.build_queue(deck_id)
        self._index = 0
        self._show_current()

    def _close_session(self) -> None:
        if self._session is not None:
            try:
                self._session.commit()
            except Exception:
                self._session.rollback()
            self._session.close()
            self._session = None

    # -- display ------------------------------------------------------------

    def _show_current(self) -> None:
        if self._index >= len(self._queue):
            self._show_complete()
            return
        self._revealed = False
        self._render(self._queue[self._index], reveal=False)
        self._face.setVisible(True)
        self._speak_btn.setVisible(True)
        self._show_btn.setVisible(True)
        self._ratings_row.setVisible(False)
        self._empty.setVisible(False)
        remaining = len(self._queue) - self._index
        self._progress.setText(f"{remaining} card{'s' if remaining != 1 else ''} left")
        self._maybe_autospeak()

    def _render(self, card, reveal: bool) -> None:
        template = card.template
        if template is None:
            self._face.setHtml("<i>(no template)</i>")
            return
        values = card.note.values_by_field_name()
        css = card.note.note_type.css if card.note.note_type else ""
        html = render_side(
            template.back_html if reveal else template.front_html,
            values,
            css=css,
            reveal=reveal,
        )
        self._face.setHtml(html)

    def _reveal(self) -> None:
        if self._index >= len(self._queue):
            return
        self._revealed = True
        self._render(self._queue[self._index], reveal=True)
        self._show_btn.setVisible(False)
        self._ratings_row.setVisible(True)
        self._rating_buttons[2].setFocus()  # default focus on Good
        self._maybe_autospeak()

    def _rate(self, rating: Rating) -> None:
        if not self._revealed or self._index >= len(self._queue):
            return
        card = self._queue[self._index]
        self._review.answer(card, rating)
        self._session.commit()
        if (
            card.srs_state in ("learning", "relearning")
            and card.due is not None
            and card.due <= now() + timedelta(minutes=_REQUEUE_WINDOW_MIN)
        ):
            self._queue.append(card)
        self._index += 1
        self._show_current()

    def _on_space(self) -> None:
        if self._face.isVisible() and not self._revealed and self._index < len(self._queue):
            self._reveal()

    def _show_complete(self) -> None:
        for widget in (self._face, self._speak_btn, self._show_btn, self._ratings_row):
            widget.setVisible(False)
        self._empty.setVisible(True)
        self._empty.setText("🎉  All done for now.\nGreat work — come back when more cards are due.")

    # -- tts ----------------------------------------------------------------

    def _maybe_autospeak(self) -> None:
        if self._context.tts and self._context.settings.get("tts_content_enabled"):
            self._speak()

    def _speak(self) -> None:
        if not self._context.tts:
            return
        document = QTextDocument()
        document.setHtml(self._face.toHtml())
        self._context.tts.speak(document.toPlainText())

    def _finish(self) -> None:
        self._close_session()
        self.finished.emit()
