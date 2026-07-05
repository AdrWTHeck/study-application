"""Guided review — one card at a time.

Shows the front, reveals the back on Space / "Show answer", then four rating
buttons. Learning cards due again within the session reappear at the end.
Content TTS reads the visible side when enabled. Holds one DB session open for
the duration of the session and commits after each answer.
"""
from __future__ import annotations

from datetime import timedelta

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QKeySequence, QShortcut, QTextDocument
from PyQt6.QtWidgets import (
    QGridLayout,
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
from domain.deadlines.deadline_service import DeadlineService
from domain.notes.rendering import render_side
from domain.srs.preview import preview_intervals
from domain.srs.srs_base import Rating

from ui.components.session_dots import SessionDots
from ui.utils.layouts import _resolve_tokens, apply_page_margins

_REQUEUE_WINDOW_MIN = 20

_RATINGS = [
    ("Again", Rating.AGAIN),
    ("Hard", Rating.HARD),
    ("Good", Rating.GOOD),
    ("Easy", Rating.EASY),
]

_RATING_KEYS = {
    Rating.AGAIN: "again",
    Rating.HARD: "hard",
    Rating.GOOD: "good",
    Rating.EASY: "easy",
}


class RatingButton(QPushButton):
    """Rating button with the rating name over a mono interval hint.

    Child labels are transparent to the mouse (same pattern as
    ``ui.components.answer_button.AnswerOptionButton``) so the whole surface
    is one click target.
    """

    def __init__(self, label: str, rating: Rating, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rating_name = label
        self.setObjectName("RatingButton")
        self.setProperty("rating", _RATING_KEYS[rating])
        self.setAccessibleName(label)
        self.setShortcut(str(index))

        column = QVBoxLayout(self)
        column.setContentsMargins(4, 4, 4, 4)
        column.setSpacing(0)
        column.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name = QLabel(f"{label} ({index})")
        self._name.setObjectName("RatingLabel")
        self._name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._hint = QLabel("")
        self._hint.setObjectName("RatingInterval")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        column.addWidget(self._name)
        column.addWidget(self._hint)

    def set_interval(self, text: str) -> None:
        self._hint.setText(text)
        if text:
            self.setAccessibleName(f"{self._rating_name} — next review in {text}")
        else:
            self.setAccessibleName(self._rating_name)


class ReviewView(QWidget):
    finished = pyqtSignal()

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setObjectName("Page")
        self.setAccessibleName("Review session")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._session = None
        self._review: ReviewService | None = None
        self._queue: list = []
        self._index = 0
        self._revealed = False
        self._deck_id: int | None = None
        self._deck_name: str = ""
        self._stats: dict[Rating, int] = {}
        self._reviewed_count = 0

        tokens = _resolve_tokens(context)
        gap = tokens.layout.gap
        narrow = tokens.layout.content_width("narrow")
        palette = tokens.palette

        root = QVBoxLayout(self)
        apply_page_margins(root, self._context)
        root.setSpacing(gap)

        # -- session header: back · deck · dots · counter · engine ---------
        header_host = QWidget()
        header_host.setObjectName("SessionHeader")
        header_host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header = QHBoxLayout(header_host)
        header.setContentsMargins(0, 0, 0, gap // 2)
        header.setSpacing(gap)

        self._end_btn = QPushButton("← End session")
        self._end_btn.setObjectName("GhostButton")
        self._end_btn.setAccessibleName("End session")
        self._end_btn.clicked.connect(self._finish)
        header.addWidget(self._end_btn)

        self._deck_label = QLabel("Review")
        self._deck_label.setObjectName("FieldLabel")
        header.addWidget(self._deck_label)

        header.addStretch(1)

        self._dots = SessionDots()
        self._dots.set_colors(QColor(palette.accent), QColor(palette.focus))
        header.addWidget(self._dots)

        self._progress = QLabel("")
        self._progress.setObjectName("SessionCounter")
        header.addWidget(self._progress)

        engine_name = str(getattr(self._context.engine, "name", "") or "")
        self._engine_tag = QLabel(engine_name.upper())
        self._engine_tag.setObjectName("SessionEngineTag")
        self._engine_tag.setAccessibleName(f"Scheduler: {engine_name.upper()}")
        self._engine_tag.setVisible(bool(engine_name))
        header.addWidget(self._engine_tag)

        root.addWidget(header_host)

        # -- centered study column (card capped at the narrow width) -------
        column_host = QWidget()
        column_host.setMaximumWidth(narrow)
        column = QVBoxLayout(column_host)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(gap)

        center = QHBoxLayout()
        center.addStretch(1)
        center.addWidget(column_host, 1)
        center.addStretch(1)
        root.addLayout(center, 1)

        self._face = QTextBrowser()
        self._face.setObjectName("CardFace")
        self._face.setAccessibleName("Card")
        self._face.setOpenLinks(False)
        self._face.setAutoFillBackground(False)
        self._face.viewport().setAutoFillBackground(False)
        column.addWidget(self._face, 1)

        self._speak_btn = QPushButton("🔊  Speak")
        self._speak_btn.setAccessibleName("Speak card")
        self._speak_btn.clicked.connect(self._speak)
        column.addWidget(self._speak_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self._show_btn = QPushButton("Show answer")
        self._show_btn.setAccessibleName("Show answer")
        self._show_btn.clicked.connect(self._reveal)
        column.addWidget(self._show_btn)

        self._ratings_row = QWidget()
        self._ratings_row.setObjectName("Page")
        self._ratings_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        ratings = QGridLayout(self._ratings_row)
        ratings.setContentsMargins(0, 0, 0, 0)
        ratings.setSpacing(gap // 2)

        self._rating_buttons: list[RatingButton] = []
        for index, (label, rating) in enumerate(_RATINGS, start=1):
            button = RatingButton(label, rating, index)
            button.clicked.connect(lambda _=False, r=rating: self._rate(r))
            ratings.addWidget(button, 0, index - 1)
            ratings.setColumnStretch(index - 1, 1)
            self._rating_buttons.append(button)

        column.addWidget(self._ratings_row)

        # -- session-complete summary card ----------------------------------
        self._summary = self._build_summary_card()
        self._summary.setVisible(False)
        column.addWidget(self._summary)

        self._empty = QLabel("")
        self._empty.setObjectName("PageSubtitle")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        column.addWidget(self._empty)

        reveal_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        reveal_shortcut.activated.connect(self._on_space)

    def _build_summary_card(self) -> QWidget:
        card = QWidget()
        card.setObjectName("SummaryCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        box = QVBoxLayout(card)
        box.setContentsMargins(24, 24, 24, 24)
        box.setSpacing(12)
        box.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        title = QLabel("✓  Session complete")
        title.setObjectName("TopTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(title)

        stats = QHBoxLayout()
        stats.setSpacing(24)
        stats.addStretch(1)
        self._summary_reviewed, reviewed_block = self._summary_stat("Cards reviewed")
        self._summary_streak, streak_block = self._summary_stat("Day streak")
        stats.addLayout(reviewed_block)
        stats.addLayout(streak_block)
        stats.addStretch(1)
        box.addLayout(stats)

        pills = QHBoxLayout()
        pills.setSpacing(8)
        pills.addStretch(1)
        self._summary_pills: dict[Rating, QLabel] = {}
        for label, rating in _RATINGS:
            pill = QLabel(f"{label} 0")
            pill.setObjectName("RatingPill")
            pill.setProperty("rating", _RATING_KEYS[rating])
            pills.addWidget(pill)
            self._summary_pills[rating] = pill
        pills.addStretch(1)
        box.addLayout(pills)

        self._summary_deadline = QLabel("")
        self._summary_deadline.setObjectName("SettingsHint")
        self._summary_deadline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._summary_deadline.setWordWrap(True)
        box.addWidget(self._summary_deadline)

        done = QPushButton("Done")
        done.setObjectName("PrimaryButton")
        done.setAccessibleName("Finish session")
        done.clicked.connect(self._finish)
        box.addWidget(done, alignment=Qt.AlignmentFlag.AlignHCenter)
        return card

    @staticmethod
    def _summary_stat(caption: str) -> tuple[QLabel, QVBoxLayout]:
        value = QLabel("0")
        value.setObjectName("SummaryStatValue")
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cap = QLabel(caption)
        cap.setObjectName("SummaryStatCaption")
        cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        block = QVBoxLayout()
        block.setSpacing(0)
        block.addWidget(value)
        block.addWidget(cap)
        return value, block

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def start(self, deck_id: int, deck_name: str | None = None) -> None:
        self._close_session()

        if self._context.db is None:
            self._show_empty("No database available.")
            return

        self._deck_id = deck_id
        self._deck_name = deck_name or ""
        self._deck_label.setText(self._deck_name or "Review")
        self._reset_stats()
        self._session = self._context.db.new_session()
        try:
            new_limit = int(self._context.settings.get("new_cards_per_session"))
        except (TypeError, ValueError):
            new_limit = 20
        self._review = ReviewService(self._session, self._context.engine, new_limit=new_limit)

        try:
            self._queue = self._review.build_queue(deck_id)
        except Exception as exc:  # noqa: BLE001
            self._close_session()
            self._show_empty(f"Could not start review:\n{exc}")
            return

        self._index = 0
        self._revealed = False
        self._show_current()

    def start_multi(self, deck_ids: list[int], deck_names: list[str] | None = None) -> None:
        """Start a review session spanning multiple decks (e.g. a parent subtree)."""
        self._close_session()

        if self._context.db is None:
            self._show_empty("No database available.")
            return

        self._deck_id = deck_ids[0] if len(deck_ids) == 1 else None
        self._deck_name = ", ".join(deck_names) if deck_names else ""
        self._deck_label.setText(self._deck_name or "Review")
        self._reset_stats()
        self._session = self._context.db.new_session()
        try:
            new_limit = int(self._context.settings.get("new_cards_per_session"))
        except (TypeError, ValueError):
            new_limit = 20
        self._review = ReviewService(self._session, self._context.engine, new_limit=new_limit)

        try:
            self._queue = self._review.build_queue_multi(deck_ids)
        except Exception as exc:  # noqa: BLE001
            self._close_session()
            self._show_empty(f"Could not start review:\n{exc}")
            return

        self._index = 0
        self._revealed = False
        self._show_current()

    def _reset_stats(self) -> None:
        self._stats = {rating: 0 for _label, rating in _RATINGS}
        self._reviewed_count = 0

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

        card = self._queue[self._index]
        self._render(card, reveal=False)

        self._face.setVisible(True)
        self._speak_btn.setVisible(True)
        self._show_btn.setVisible(True)
        self._ratings_row.setVisible(False)
        self._summary.setVisible(False)
        self._empty.setVisible(False)

        current, total = self._index + 1, len(self._queue)
        self._progress.setText(f"{current} of {total}")
        self._progress.setAccessibleName(f"Card {current} of {total}")
        self._dots.set_progress(current, total)

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
            values,
            css=css,
            reveal=reveal,
        )
        self._face.setHtml(html)

    def _reveal(self) -> None:
        if self._index >= len(self._queue):
            return

        self._revealed = True
        card = self._queue[self._index]
        self._render(card, reveal=True)

        # Informed choice (AUT): show what each rating would schedule.
        try:
            hints = preview_intervals(self._context.engine, card)
        except Exception:  # noqa: BLE001 — hints are optional decoration
            hints = {}
        for button, (_label, rating) in zip(self._rating_buttons, _RATINGS):
            button.set_interval(hints.get(rating, ""))

        self._show_btn.setVisible(False)
        self._ratings_row.setVisible(True)

        if len(self._rating_buttons) >= 3:
            self._rating_buttons[2].setFocus()

        self._maybe_autospeak()

    def _rate(self, rating: Rating) -> None:
        if (
            not self._revealed
            or self._index >= len(self._queue)
            or self._review is None
            or self._session is None
        ):
            return

        card = self._queue[self._index]

        try:
            self._review.answer(card, rating)
            self._session.commit()
        except Exception as exc:  # noqa: BLE001
            self._session.rollback()
            self._show_empty(f"Could not save review answer:\n{exc}")
            return

        self._reviewed_count += 1
        self._stats[rating] = self._stats.get(rating, 0) + 1

        if (
            card.srs_state in ("learning", "relearning")
            and card.due is not None
            and card.due <= now() + timedelta(minutes=_REQUEUE_WINDOW_MIN)
        ):
            self._queue.append(card)

        self._index += 1
        self._show_current()

    def _on_space(self) -> None:
        if (
            self._face.isVisible()
            and not self._revealed
            and self._index < len(self._queue)
        ):
            self._reveal()

    def _show_empty(self, message: str) -> None:
        self._face.setVisible(False)
        self._speak_btn.setVisible(False)
        self._show_btn.setVisible(False)
        self._ratings_row.setVisible(False)
        self._summary.setVisible(False)
        self._empty.setVisible(True)
        self._empty.setText(message)
        self._progress.setText("")
        self._dots.set_progress(0, 0)

    def _show_complete(self) -> None:
        # Nothing was reviewed (e.g. empty queue) — keep the simple message.
        if self._reviewed_count == 0:
            self._show_empty(
                "🎉  All done for now.\nGreat work — come back when more cards are due."
            )
            self._progress.setText("Complete")
            return

        streak = 0
        if self._context.db is not None:
            try:
                from domain.dashboard.stats_service import StatsService

                with self._context.db.session() as session:
                    streak = StatsService(session).streak()
            except Exception:
                streak = 0

        self._summary_reviewed.setText(str(self._reviewed_count))
        self._summary_reviewed.setAccessibleName(f"{self._reviewed_count} cards reviewed")
        self._summary_streak.setText(str(streak))
        self._summary_streak.setAccessibleName(f"{streak} day streak")
        for label, rating in _RATINGS:
            count = self._stats.get(rating, 0)
            pill = self._summary_pills[rating]
            pill.setText(f"{label} {count}")
            pill.setAccessibleName(f"{label}: {count}")

        self._summary_deadline.setText(self._deadline_message())
        self._summary_deadline.setVisible(bool(self._summary_deadline.text()))

        self._face.setVisible(False)
        self._speak_btn.setVisible(False)
        self._show_btn.setVisible(False)
        self._ratings_row.setVisible(False)
        self._empty.setVisible(False)
        self._summary.setVisible(True)
        self._progress.setText("Complete")
        self._dots.set_progress(0, 0)

    def _deadline_message(self) -> str:
        if self._context.db is None or self._deck_id is None:
            return ""
        try:
            with self._context.db.session() as session:
                deadline = DeadlineService(session).deadline_for_deck(self._deck_id)
        except Exception:
            return ""
        if deadline is None or deadline.is_past:
            return ""
        if deadline.total_remaining == 0:
            return f"{deadline.name}: All caught up!"
        if deadline.daily_target is not None:
            n = deadline.total_remaining
            return (
                f"{deadline.name}: {n} card{'s' if n != 1 else ''} remaining"
                f" · {deadline.daily_target}/day to stay on track"
            )
        return ""

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