"""QuestionFormView — QDialog for creating or editing a question manually."""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QLabel, QLineEdit, QTextEdit, QVBoxLayout,
)

from services.quiz.quiz_service import QuizService

_TYPES = ["fill_blank", "mcq", "short_answer", "verbatim"]


class QuestionFormView(QDialog):
    """Modal dialog to create or edit a Question.

    Pass question_id=None to create a new question.
    Emits question_saved(question_id) on success.
    """

    question_saved = pyqtSignal(int)

    def __init__(
        self,
        deck_id: int,
        quiz_service: QuizService,
        question_id: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._deck_id = deck_id
        self._question_id = question_id
        self._svc = quiz_service
        self.setWindowTitle("Edit Question" if question_id else "New Question")
        self.setMinimumWidth(460)
        self._build_ui()
        if question_id:
            self._load(question_id)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._type_combo = QComboBox()
        self._type_combo.addItems(_TYPES)
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        form.addRow("Type:", self._type_combo)

        self._question = QTextEdit()
        self._question.setPlaceholderText("Question text (use ___ for fill-blank)")
        self._question.setMaximumHeight(80)
        form.addRow("Question:", self._question)

        self._answer = QTextEdit()
        self._answer.setPlaceholderText("Correct answer")
        self._answer.setMaximumHeight(80)
        form.addRow("Answer:", self._answer)

        self._distractor_label = QLabel("Distractors (one per line, MCQ only):")
        self._distractors = QTextEdit()
        self._distractors.setMaximumHeight(70)
        self._distractors.setPlaceholderText("Option 1\nOption 2\nOption 3")
        form.addRow(self._distractor_label, self._distractors)
        layout.addLayout(form)

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

        self._on_type_changed("fill_blank")

    def _load(self, question_id: int) -> None:
        db = __import__("models.base", fromlist=["get_session"]).get_session()
        try:
            from repositories.question_repository import QuestionRepository
            q = QuestionRepository(db).get(question_id)
            if q:
                idx = _TYPES.index(q.type) if q.type in _TYPES else 0
                self._type_combo.setCurrentIndex(idx)
                self._question.setPlainText(q.question_text or "")
                self._answer.setPlainText(q.answer or "")
                if q.distractors:
                    self._distractors.setPlainText("\n".join(q.distractors))
        finally:
            db.close()

    def _on_type_changed(self, q_type: str) -> None:
        is_mcq = q_type == "mcq"
        self._distractor_label.setVisible(is_mcq)
        self._distractors.setVisible(is_mcq)

    def _save(self) -> None:
        q_type = self._type_combo.currentText()
        question_text = self._question.toPlainText().strip()
        answer = self._answer.toPlainText().strip()

        if not question_text or not answer:
            self._error.setText("Question and answer are required.")
            return

        distractors: list[str] | None = None
        if q_type == "mcq":
            lines = [l.strip() for l in self._distractors.toPlainText().splitlines()
                     if l.strip()]
            if len(lines) < 2:
                self._error.setText("MCQ requires at least 2 distractors.")
                return
            distractors = lines

        if self._question_id:
            db = __import__("models.base", fromlist=["get_session"]).get_session()
            try:
                from repositories.question_repository import QuestionRepository
                q = QuestionRepository(db).get(self._question_id)
                if q:
                    q.question_text = question_text
                    q.answer = answer
                    q.type = q_type
                    q.distractors = distractors
                    db.commit()
            finally:
                db.close()
            saved_id = self._question_id
        else:
            q = self._svc.save_manual_question(
                self._deck_id, question_text, answer, q_type, distractors
            )
            saved_id = q.id if q else None

        if saved_id is None:
            self._error.setText("Failed to save question.")
            return
        self.question_saved.emit(saved_id)
        self.accept()
