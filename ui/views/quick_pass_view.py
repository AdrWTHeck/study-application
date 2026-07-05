"""Quick pass — a fast recall check over the cards that are *due*.

Shows the front, reveals the back on Space / "Show answer", then two buttons:

  * **Yes — got it** leaves the card completely untouched (no scheduler change,
    no review log); it just advances to the next card.
  * **No — missed it** sends the card back through FSRS as ``Rating.AGAIN`` (a
    lapse, so it returns sooner) via the same ``ReviewService.answer`` the full
    review uses.

So the pass only *acts* on misses. It pulls **due cards only** (``new_limit=0``),
never brand-new never-seen cards. Holds one DB session open for the duration and
commits after each "No".
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
from app.events import AppEvent
from core.clock import now
from domain.cards.review_service import ReviewService
from domain.notes.rendering import render_side
from domain.srs.srs_base import Rating
from ui.utils.layouts import apply_page_margins

_REQUEUE_WINDOW_MIN = 20


class QuickPassView(QWidget):
    finished = pyqtSignal()

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setObjectName("Page")
        self.setAccessibleName("Quick pass")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._session = None
        self._review: ReviewService | None = None
        self._queue: list = []
        self._index = 0
        self._revealed = False

        root = QVBoxLayout(self)
        apply_page_margins(root, self._context)
        root.setSpacing(12)

        header = QHBoxLayout()
        self._progress = QLabel("")
        self._progress.setObjectName("SettingsHint")
        header.addWidget(self._progress)
        header.addStretch(1)
        self._end_btn = QPushButton("End")
        self._end_btn.setAccessibleName("End quick pass")
        self._end_btn.clicked.connect(self._finish)
        header.addWidget(self._end_btn)
        root.addLayout(header)

        self._face = QTextBrowser()
        self._face.setObjectName("CardFace")
        self._face.setAccessibleName("Card")
        self._face.setOpenLinks(False)
        self._face.setAutoFillBackground(False)
        self._face.viewport().setAutoFillBackground(False)
        root.addWidget(self._face, 1)

        self._speak_btn = QPushButton("🔊  Speak")
        self._speak_btn.setAccessibleName("Speak card")
        self._speak_btn.clicked.connect(self._speak)
        root.addWidget(self._speak_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self._show_btn = QPushButton("Show answer")
        self._show_btn.setAccessibleName("Show answer")
        self._show_btn.clicked.connect(self._reveal)
        root.addWidget(self._show_btn)

        # Yes/No row (hidden until the answer is revealed).
        self._answer_row = QWidget()
        self._answer_row.setObjectName("Page")
        self._answer_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        answer = QHBoxLayout(self._answer_row)
        answer.setContentsMargins(0, 0, 0, 0)
        answer.setSpacing(8)

        self._yes_btn = QPushButton("Yes — got it (1)")
        self._yes_btn.setAccessibleName("Yes, I got it — leave this card unchanged")
        self._yes_btn.setShortcut("1")
        self._yes_btn.clicked.connect(lambda: self._mark(got_it=True))
        self._no_btn = QPushButton("No — missed it (2)")
        self._no_btn.setAccessibleName("No, I missed it — send this card back")
        self._no_btn.setShortcut("2")
        self._no_btn.clicked.connect(lambda: self._mark(got_it=False))
        answer.addWidget(self._yes_btn)
        answer.addWidget(self._no_btn)
        root.addWidget(self._answer_row)

        self._empty = QLabel("")
        self._empty.setObjectName("PageSubtitle")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        root.addWidget(self._empty)

        reveal_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        reveal_shortcut.activated.connect(self._on_space)

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def start(self, deck_id: int) -> None:
        self._start_queue(lambda review: review.build_queue(deck_id))

    def start_multi(self, deck_ids: list[int]) -> None:
        self._start_queue(lambda review: review.build_queue_multi(deck_ids))

    def _start_queue(self, build) -> None:
        self._close_session()
        if self._context.db is None:
            self._show_empty("No database available.")
            return

        self._session = self._context.db.new_session()
        # new_limit=0 → build_queue returns due cards only (no brand-new cards).
        self._review = ReviewService(self._session, self._context.engine, new_limit=0)
        try:
            self._queue = build(self._review)
        except Exception as exc:  # noqa: BLE001
            self._close_session()
            self._show_empty(f"Could not start quick pass:\n{exc}")
            return

        self._index = 0
        self._revealed = False
        self._show_current()

    def _close_session(self) -> None:
        if self._session is not None:
            try:
                self._session.commit()
            except Exception:
                self._session.rollback()
            finally:
                self._session.close()
        self._session = None
        self._review = None

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def _show_current(self) -> None:
        if self._index >= len(self._queue):
            self._show_complete()
            return

        self._revealed = False
        self._render(self._queue[self._index], reveal=False)

        self._face.setVisible(True)
        self._speak_btn.setVisible(True)
        self._show_btn.setVisible(True)
        self._answer_row.setVisible(False)
        self._empty.setVisible(False)

        remaining = len(self._queue) - self._index
        self._progress.setText(f"{remaining} card{'s' if remaining != 1 else ''} left")
        self._maybe_autospeak()

    def _render(self, card, reveal: bool) -> None:
        template = getattr(card, "template", None)
        if template is None:
            self._face.setHtml("<i>(no template)</i>")
            return
        note = getattr(card, "note", None)
        if note is None:
            self._face.setHtml("<i>(missing note)</i>")
            return
        values = note.values_by_field_name()
        css = note.note_type.css if note.note_type else ""
        html = render_side(
            template.back_html if reveal else template.front_html,
            values, css=css, reveal=reveal,
        )
        self._face.setHtml(html)

    def _reveal(self) -> None:
        if self._index >= len(self._queue):
            return
        self._revealed = True
        self._render(self._queue[self._index], reveal=True)
        self._show_btn.setVisible(False)
        self._answer_row.setVisible(True)
        self._yes_btn.setFocus()
        self._maybe_autospeak()

    def _mark(self, got_it: bool) -> None:
        if (
            not self._revealed
            or self._index >= len(self._queue)
            or self._review is None
            or self._session is None
        ):
            return

        card = self._queue[self._index]

        if got_it:
            # Yes = leave the card completely untouched (no engine call, no log).
            self._index += 1
            self._show_current()
            return

        # No = send it back through FSRS as a lapse.
        try:
            self._review.answer(card, Rating.AGAIN)
            self._session.commit()
        except Exception as exc:  # noqa: BLE001
            self._session.rollback()
            self._show_empty(f"Could not save the answer:\n{exc}")
            return

        # A lapsed card due again soon reappears later in this pass.
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

    def _show_empty(self, message: str) -> None:
        self._face.setVisible(False)
        self._speak_btn.setVisible(False)
        self._show_btn.setVisible(False)
        self._answer_row.setVisible(False)
        self._empty.setVisible(True)
        self._empty.setText(message)
        self._progress.setText("")

    def _show_complete(self) -> None:
        self._show_empty("🎉  Quick pass complete.\nThe ones you missed will come back sooner.")
        self._progress.setText("Complete")

    # ------------------------------------------------------------------
    # TTS
    # ------------------------------------------------------------------

    def _maybe_autospeak(self) -> None:
        if self._context.tts and self._context.settings.get("tts_content_enabled"):
            self._speak()

    def _speak(self) -> None:
        if not self._context.tts:
            return
        document = QTextDocument()
        document.setHtml(self._face.toHtml())
        text = document.toPlainText().strip()
        if text:
            self._context.tts.speak(text)

    def _finish(self) -> None:
        self._close_session()
        self._context.events.publish(AppEvent.CARD_REVIEWED)
        self.finished.emit()
