"""A temporary cram session that does not affect SRS scheduling."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from data.models import Card
from domain.cards.cram_service import CramService
from domain.notes.rendering import render_side

from ui.utils.layouts import apply_page_margins


class CramView(QWidget):
    finished = pyqtSignal()

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setObjectName("Page")
        self.setAccessibleName("Cram session")

        self._session = None
        self._queue: list[Card] = []
        self._index = 0
        self._revealed = False
        self._passes = 0
        self._fails = 0
        self._retried = 0

        root = QVBoxLayout(self)
        apply_page_margins(root, self._context)
        root.setSpacing(12)

        header = QHBoxLayout()
        self._progress = QLabel("")
        self._progress.setObjectName("SettingsHint")
        end_btn = QPushButton("End cram")
        end_btn.setAccessibleName("End cram session")
        end_btn.clicked.connect(self._finish)
        header.addWidget(self._progress)
        header.addStretch(1)
        header.addWidget(end_btn)
        root.addLayout(header)

        self._face = QTextBrowser()
        self._face.setObjectName("CardFace")
        self._face.setAccessibleName("Cram card")
        self._face.setOpenLinks(False)
        root.addWidget(self._face, 1)

        self._show_btn = QPushButton("Show answer")
        self._show_btn.setAccessibleName("Show answer")
        self._show_btn.clicked.connect(self._reveal)
        root.addWidget(self._show_btn)

        self._actions_row = QWidget()
        actions = QHBoxLayout(self._actions_row)
        actions.setContentsMargins(0, 0, 0, 0)
        self._pass_btn = QPushButton("Pass")
        self._pass_btn.setAccessibleName("Pass card")
        self._pass_btn.clicked.connect(lambda: self._record("pass"))
        self._fail_btn = QPushButton("Fail")
        self._fail_btn.setAccessibleName("Fail card")
        self._fail_btn.clicked.connect(lambda: self._record("fail"))
        self._retry_btn = QPushButton("Retry")
        self._retry_btn.setAccessibleName("Retry card")
        self._retry_btn.clicked.connect(lambda: self._record("retry"))
        actions.addWidget(self._pass_btn)
        actions.addWidget(self._fail_btn)
        actions.addWidget(self._retry_btn)
        root.addWidget(self._actions_row)

        self._empty = QLabel("")
        self._empty.setObjectName("PageSubtitle")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        root.addWidget(self._empty)

        reveal_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        reveal_shortcut.activated.connect(self._on_space)

    def start(self, deck_id: int) -> None:
        self._close_session()
        if self._context.db is None:
            return
        self._session = self._context.db.new_session()
        self._queue = CramService(self._session).build_queue(deck_id)
        self._index = 0
        self._passes = 0
        self._fails = 0
        self._retried = 0
        self._show_current()

    def start_multi(self, deck_ids: list[int]) -> None:
        """Start a cram session spanning multiple decks (e.g. a parent subtree)."""
        self._close_session()
        if self._context.db is None:
            return
        self._session = self._context.db.new_session()
        self._queue = CramService(self._session).build_queue_multi(deck_ids)
        self._index = 0
        self._passes = 0
        self._fails = 0
        self._retried = 0
        self._show_current()

    def _close_session(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None

    def _show_current(self) -> None:
        if self._index >= len(self._queue):
            self._show_complete()
            return
        self._revealed = False
        self._render(self._queue[self._index], reveal=False)
        self._face.setVisible(True)
        self._show_btn.setVisible(True)
        self._actions_row.setVisible(False)
        self._empty.setVisible(False)
        remaining = len(self._queue) - self._index
        self._progress.setText(f"{remaining} card{'s' if remaining != 1 else ''} left")

    def _render(self, card: Card, reveal: bool) -> None:
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
        self._actions_row.setVisible(True)
        self._pass_btn.setFocus()

    def _record(self, action: str) -> None:
        if not self._revealed or self._index >= len(self._queue):
            return
        card = self._queue.pop(self._index)
        if action == "retry":
            self._retried += 1
            insert_at = self._index + ((len(self._queue) + 1) // 2)
            insert_at = min(insert_at, len(self._queue))
            self._queue.insert(insert_at, card)
        elif action == "pass":
            self._passes += 1
        elif action == "fail":
            self._fails += 1
            self._queue.append(card)
        self._show_current()

    def _on_space(self) -> None:
        if self._face.isVisible() and not self._revealed and self._index < len(self._queue):
            self._reveal()

    def _show_complete(self) -> None:
        self._face.setVisible(False)
        self._show_btn.setVisible(False)
        self._actions_row.setVisible(False)
        self._empty.setVisible(True)
        self._empty.setText(
            f"🎉 All done. Pass: {self._passes}, Fail: {self._fails}, Retry: {self._retried}. "
            "This session did not change card scheduling."
        )

    def _finish(self) -> None:
        self._close_session()
        self.finished.emit()
