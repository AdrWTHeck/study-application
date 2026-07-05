"""Comprehensive test: quiz across several test decks at once, then a per-deck
bar graph revealing the weakest area.

Self-contained (its own quiz loop + results) so it doesn't entangle the main
TestsView quiz flow. Reuses QuizService for gathering, grading, and the per-deck
breakdown.
"""
from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from ui.utils.layouts import apply_page_margins, clear_layout
from data.models.testing import OPTION_TYPES
from domain.decks.deck_service import DeckService
from domain.testing.quiz_service import QuizService
from ui.components.bar_chart import BarChart


class DeckMultiSelectDialog(QDialog):
    """Pick which test decks to include in a comprehensive test."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Comprehensive test")
        self.setAccessibleName("Choose test decks")
        self.resize(380, 440)
        self.selected_ids: list[int] = []

        layout = QVBoxLayout(self)
        intro = QLabel("Choose the test decks to combine. You'll see your weakest area at the end.")
        intro.setObjectName("SettingsHint")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._checks: dict[int, QCheckBox] = {}
        decks: list[tuple[int, str]] = []
        if context.db is not None:
            with context.db.session() as session:
                decks = [(d.id, d.name) for d in DeckService(session).decks.by_type("test")]
        for deck_id, name in decks:
            check = QCheckBox(name)
            check.setAccessibleName(name)
            self._checks[deck_id] = check
            layout.addWidget(check)
        layout.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Start")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        self.selected_ids = [did for did, check in self._checks.items() if check.isChecked()]
        self.accept()


class ComprehensiveTestView(QWidget):
    finished = pyqtSignal()

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setObjectName("Page")
        self.setAccessibleName("Comprehensive test")

        self._session = None
        self._quiz: QuizService | None = None
        self._quiz_row = None
        self._questions: list = []
        self._index = 0

        root = QVBoxLayout(self)
        apply_page_margins(root, self._context)
        root.setSpacing(12)

        header = QHBoxLayout()
        self._progress = QLabel("")
        self._progress.setObjectName("SettingsHint")
        self._end_btn = QPushButton("End")
        self._end_btn.setAccessibleName("End comprehensive test")
        self._end_btn.clicked.connect(self._done)
        header.addWidget(self._progress)
        header.addStretch(1)
        header.addWidget(self._end_btn)
        root.addLayout(header)

        self._prompt = QTextBrowser()
        self._prompt.setObjectName("CardFace")
        self._prompt.setAccessibleName("Question")
        root.addWidget(self._prompt, 1)

        self._answer_container = QWidget()
        self._answer_layout = QVBoxLayout(self._answer_container)
        self._answer_layout.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._answer_container)

        # Results (hidden during the quiz).
        self._results = QWidget()
        results_layout = QVBoxLayout(self._results)
        results_layout.setContentsMargins(0, 0, 0, 0)
        self._results_heading = QLabel("")
        self._results_heading.setObjectName("PageTitle")
        self._results_heading.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._weakest = QLabel("")
        self._weakest.setObjectName("PageSubtitle")
        self._weakest.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._chart = BarChart()
        results_layout.addWidget(self._results_heading)
        results_layout.addWidget(self._weakest)
        results_layout.addSpacing(12)
        results_layout.addWidget(self._chart)
        results_layout.addStretch(1)
        self._results.setVisible(False)
        root.addWidget(self._results, 1)

    # -- lifecycle ----------------------------------------------------------

    def start(self, deck_ids: list[int]) -> None:
        self._close_session()
        if self._context.db is None or not deck_ids:
            return
        self._session = self._context.db.new_session()
        self._quiz = QuizService(self._session)
        self._questions = self._quiz.gather_questions(deck_ids)
        self._results.setVisible(False)
        self._prompt.setVisible(True)
        self._answer_container.setVisible(True)
        if not self._questions:
            self._prompt.setHtml("<i>The selected decks have no questions.</i>")
            self._clear(self._answer_layout)
            return
        self._quiz_row = self._quiz.start(deck_ids[0], {"comprehensive": True, "decks": deck_ids})
        self._index = 0
        self._show_question()

    def _close_session(self) -> None:
        if self._session is not None:
            try:
                self._session.commit()
            except Exception:
                self._session.rollback()
            self._session.close()
            self._session = None

    # -- quiz ---------------------------------------------------------------

    def _show_question(self) -> None:
        if self._index >= len(self._questions):
            self._finish()
            return
        question = self._questions[self._index]
        self._progress.setText(f"Question {self._index + 1} of {len(self._questions)}")
        self._prompt.setText(question.prompt or "")
        self._clear(self._answer_layout)
        if question.type in OPTION_TYPES:
            for option in question.options:
                button = QPushButton(option.text)
                button.setAccessibleName(option.text)
                button.clicked.connect(lambda _=False, text=option.text: self._submit(text))
                self._answer_layout.addWidget(button)
        else:
            field = QLineEdit()
            field.setAccessibleName("Your answer")
            field.setPlaceholderText("Type your answer and press Enter")
            field.returnPressed.connect(lambda: self._submit(field.text()))
            submit = QPushButton("Submit")
            submit.clicked.connect(lambda: self._submit(field.text()))
            self._answer_layout.addWidget(field)
            self._answer_layout.addWidget(submit, alignment=Qt.AlignmentFlag.AlignLeft)

    def _submit(self, response: str) -> None:
        if self._index >= len(self._questions):
            return
        if self._quiz is None or self._session is None or self._quiz_row is None:
            return
        threshold = int(self._context.settings.get("short_answer_fuzzy_threshold"))
        try:
            self._quiz.record(self._quiz_row, self._questions[self._index], response, fuzzy_threshold=threshold)
            self._session.commit()
        except Exception:
            self._session.rollback()
            QMessageBox.warning(self, "Save failed", "Couldn't record that answer. Please try again.")
            return
        self._index += 1
        self._show_question()

    def _finish(self) -> None:
        if self._quiz is None or self._session is None or self._quiz_row is None:
            return
        try:
            self._quiz.finish(self._quiz_row)
            self._session.commit()
        except Exception:
            self._session.rollback()
            QMessageBox.warning(self, "Save failed", "Couldn't save your results.")
            return
        breakdown = self._quiz.breakdown_by_deck(self._quiz_row.id)
        score = self._quiz.session_score(self._quiz_row.id)
        self._results_heading.setText(f"Comprehensive score: {score:.0f}%")
        if breakdown:
            self._weakest.setText(f"Weakest area: {breakdown[0].deck} ({breakdown[0].pct:.0f}%)")
            self._chart.set_data([(b.deck, b.pct) for b in breakdown])
        self._prompt.setVisible(False)
        self._answer_container.setVisible(False)
        self._results.setVisible(True)
        self._end_btn.setText("Done")
        self._progress.setText("Complete")

    def _done(self) -> None:
        self._close_session()
        self.finished.emit()

    @staticmethod
    def _clear(layout) -> None:
        clear_layout(layout)
