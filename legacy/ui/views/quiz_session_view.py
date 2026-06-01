"""QuizSessionView — adaptive question widget for fill_blank, mcq, short_answer."""
from __future__ import annotations

import random
from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QProgressBar, QPushButton,
    QRadioButton, QTextEdit, QVBoxLayout, QWidget,
)

from services.accessibility.tts_service import TTSService
from services.quiz.test_session_controller import AnswerResult, TestSessionController
from ui.components.elapsed_timer import ElapsedTimer
from ui.components.tts_button import TtsButton


class QuizSessionView(QWidget):
    """Presents one question at a time and submits answers.

    session_finished(session_id) is emitted when the session completes or
    the user ends it early.
    """

    session_finished = pyqtSignal(int)   # session_id

    def __init__(self, tts: TTSService, parent=None) -> None:
        super().__init__(parent)
        self._tts = tts
        self._ctrl = TestSessionController()
        self._session_id: int | None = None
        self._current_q_id: int | None = None
        self._presented_at: datetime | None = None
        self._mcq_options: list[str] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Top bar: progress + timer
        top = QHBoxLayout()
        self._progress = QProgressBar()
        self._progress.setTextVisible(True)
        top.addWidget(self._progress)
        self._timer = ElapsedTimer()
        top.addWidget(self._timer)
        layout.addLayout(top)

        # Question label
        self._q_label = QLabel("–")
        self._q_label.setWordWrap(True)
        self._q_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._q_label.setMinimumHeight(80)
        self._q_label.setStyleSheet(
            "border: 1px solid #CCCCCC; border-radius: 6px; padding: 12px;"
            "font-size: 13pt;"
        )
        layout.addWidget(self._q_label)

        # TTS
        self._tts_btn = TtsButton(self._tts)
        layout.addWidget(self._tts_btn)

        # Answer area — swapped out per question type
        self._answer_area = QWidget()
        self._answer_layout = QVBoxLayout(self._answer_area)
        layout.addWidget(self._answer_area)

        # MCQ radio group (reused)
        self._radio_group = QButtonGroup(self)
        self._radio_btns: list[QRadioButton] = []

        # Fill-blank line edit
        self._fill_input = QLineEdit()
        self._fill_input.setPlaceholderText("Type your answer…")

        # Short-answer text edit
        self._sa_input = QTextEdit()
        self._sa_input.setPlaceholderText("Write your answer…")
        self._sa_input.setMaximumHeight(100)

        # Feedback label
        self._feedback = QLabel("")
        self._feedback.setWordWrap(True)
        layout.addWidget(self._feedback)

        # Submit / Next
        btn_row = QHBoxLayout()
        self._submit_btn = QPushButton("Submit")
        self._submit_btn.clicked.connect(self._submit)
        self._next_btn = QPushButton("Next →")
        self._next_btn.clicked.connect(self._next)
        self._next_btn.setVisible(False)
        self._end_btn = QPushButton("End Session")
        self._end_btn.clicked.connect(self._end_session)
        btn_row.addWidget(self._submit_btn)
        btn_row.addWidget(self._next_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._end_btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Session control
    # ------------------------------------------------------------------

    def start_session(self, deck_id: int, total_count: int) -> None:
        quiz = self._ctrl.start([deck_id], total_count, "deck")
        if quiz is None:
            QMessageBox.warning(self, "No Questions",
                                "No questions available for this deck.")
            return
        self._session_id = quiz.id
        self._progress.setMaximum(quiz.total_items)
        self._progress.setValue(0)
        self._load_next()

    def resume_session(self, session_id: int) -> None:
        quiz = self._ctrl.resume(session_id)
        if quiz is None:
            return
        self._session_id = quiz.id
        self._progress.setMaximum(quiz.total_items)
        self._progress.setValue(quiz.items_reviewed)
        self._load_next()

    # ------------------------------------------------------------------
    # Question flow
    # ------------------------------------------------------------------

    def _load_next(self) -> None:
        if self._session_id is None:
            return
        q = self._ctrl.get_next_question(self._session_id)
        if q is None:
            self._finish()
            return

        self._current_q_id = q.id
        self._presented_at = datetime.now()
        self._feedback.setText("")
        self._next_btn.setVisible(False)
        self._submit_btn.setVisible(True)
        self._timer.start()

        self._q_label.setText(q.question_text or "")
        self._tts_btn.set_text(q.question_text or "")

        # Clear answer area
        for i in reversed(range(self._answer_layout.count())):
            w = self._answer_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        if q.type == "mcq":
            self._show_mcq(q)
        elif q.type == "fill_blank":
            self._fill_input.clear()
            self._answer_layout.addWidget(self._fill_input)
            self._fill_input.setVisible(True)
        else:  # short_answer / verbatim
            self._sa_input.clear()
            self._answer_layout.addWidget(self._sa_input)
            self._sa_input.setVisible(True)

        self._update_progress()

    def _show_mcq(self, q) -> None:
        for btn in self._radio_btns:
            self._radio_group.removeButton(btn)
            btn.setParent(None)
        self._radio_btns = []

        options = [q.answer] + (q.distractors or [])
        random.shuffle(options)
        self._mcq_options = options

        for opt in options:
            rb = QRadioButton(opt)
            self._radio_group.addButton(rb)
            self._radio_btns.append(rb)
            self._answer_layout.addWidget(rb)

    def _get_user_answer(self) -> str:
        # Determine which input widget is active
        if self._fill_input.isVisible() and self._fill_input.parent() is not None:
            return self._fill_input.text().strip()
        if self._sa_input.isVisible() and self._sa_input.parent() is not None:
            return self._sa_input.toPlainText().strip()
        # MCQ
        for btn in self._radio_btns:
            if btn.isChecked():
                return btn.text()
        return ""

    def _submit(self) -> None:
        if self._session_id is None or self._current_q_id is None:
            return
        answer = self._get_user_answer()
        if not answer:
            self._feedback.setText("Please provide an answer.")
            return

        self._timer.stop()
        result: AnswerResult | None = self._ctrl.submit_answer(
            self._session_id,
            self._current_q_id,
            answer,
            self._presented_at or datetime.now(),
        )
        if result is None:
            self._feedback.setText("Error saving answer.")
            return

        if result.correct:
            self._feedback.setStyleSheet("color: green; font-weight: bold;")
            self._feedback.setText("Correct!")
        else:
            self._feedback.setStyleSheet("color: red;")
            score_str = (
                f"  (similarity {result.similarity_score:.0f}%)"
                if result.similarity_score is not None else ""
            )
            # Show correct answer
            db = __import__("models.base", fromlist=["get_session"]).get_session()
            try:
                from repositories.question_repository import QuestionRepository
                q = QuestionRepository(db).get(self._current_q_id)
                correct_ans = q.answer if q else "?"
            finally:
                db.close()
            self._feedback.setText(
                f"Incorrect{score_str}. Correct answer: {correct_ans}"
            )

        self._submit_btn.setVisible(False)
        if result.is_complete:
            self._next_btn.setText("See Results")
            self._next_btn.clicked.disconnect()
            self._next_btn.clicked.connect(self._finish)
        else:
            self._next_btn.setText("Next →")
        self._next_btn.setVisible(True)

    def _next(self) -> None:
        self._tts_btn.reset()
        self._load_next()

    def _finish(self) -> None:
        self._timer.stop()
        self._tts_btn.reset()
        sid = self._session_id
        self._session_id = None
        if sid is not None:
            self.session_finished.emit(sid)

    def _end_session(self) -> None:
        if self._session_id is None:
            return
        ans = QMessageBox.question(self, "End Session", "End test early?")
        if ans == QMessageBox.StandardButton.Yes:
            self._ctrl.discard(self._session_id)
            sid = self._session_id
            self._session_id = None
            self.session_finished.emit(sid)

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
