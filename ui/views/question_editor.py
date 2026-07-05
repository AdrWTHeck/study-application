"""Create/edit a question of any type (mcq / true-false / short / fill-blank).

A type selector flips a small stacked area to the right inputs. In edit mode the
type is locked and the fields are prefilled.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from data.models.testing import FILL_BLANK, MCQ, SHORT_ANSWER, TRUE_FALSE
from data.repositories.question_repository import QuestionRepository
from domain.testing.question_service import QuestionService

_TYPES = [
    ("Multiple choice", MCQ),
    ("True / False", TRUE_FALSE),
    ("Short answer", SHORT_ANSWER),
    ("Fill in the blank", FILL_BLANK),
]
_PAGE = {MCQ: 0, TRUE_FALSE: 1, SHORT_ANSWER: 2, FILL_BLANK: 2}


class QuestionEditorDialog(QDialog):
    def __init__(self, context: AppContext, deck_id: int,
                 question_id: int | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self._deck_id = deck_id
        self._question_id = question_id
        editing = question_id is not None
        self.setWindowTitle("Edit question" if editing else "Add question")
        self.setAccessibleName(self.windowTitle())
        self.resize(560, 600)

        existing = None
        if editing and context.db is not None:
            with context.db.session() as s:
                q = QuestionRepository(s).get(question_id)
                if q is not None:
                    existing = {
                        "type": q.type, "prompt": q.prompt, "explanation": q.explanation,
                        "options": [(o.text, o.is_correct) for o in q.options],
                        "answers": [a.accepted_text for a in q.answers],
                    }

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(8)

        root.addWidget(self._label("Type"))
        self.type_combo = QComboBox()
        self.type_combo.setAccessibleName("Question type")
        self.type_combo.addItems([name for name, _ in _TYPES])
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        root.addWidget(self.type_combo)

        root.addWidget(self._label("Prompt"))
        self.prompt = QPlainTextEdit()
        self.prompt.setFixedHeight(80)
        self.prompt.setAccessibleName("Prompt")
        root.addWidget(self.prompt)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_mcq_page())
        self._stack.addWidget(self._build_tf_page())
        self._stack.addWidget(self._build_text_page())
        root.addWidget(self._stack)

        root.addWidget(self._label("Explanation (optional)"))
        self.explanation = QLineEdit()
        self.explanation.setAccessibleName("Explanation")
        root.addWidget(self.explanation)

        root.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        if existing:
            self._prefill(existing)
            self.type_combo.setEnabled(False)
        self._on_type_changed()

    # -- pages --------------------------------------------------------------

    def _build_mcq_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label("Options (tick the correct one(s))"))
        self._option_rows: list[tuple[QLineEdit, QCheckBox]] = []
        for i in range(4):
            row = QHBoxLayout()
            edit = QLineEdit()
            edit.setAccessibleName(f"Option {i + 1}")
            check = QCheckBox("correct")
            check.setAccessibleName(f"Option {i + 1} correct")
            row.addWidget(edit, 1)
            row.addWidget(check)
            layout.addLayout(row)
            self._option_rows.append((edit, check))
        return page

    def _build_tf_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label("Correct answer"))
        self.tf_combo = QComboBox()
        self.tf_combo.addItems(["True", "False"])
        self.tf_combo.setAccessibleName("Correct answer")
        layout.addWidget(self.tf_combo)
        return page

    def _build_text_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label("Accepted answers (one per line)"))
        self.accepted = QPlainTextEdit()
        self.accepted.setAccessibleName("Accepted answers")
        layout.addWidget(self.accepted)
        return page

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        return label

    # -- behavior -----------------------------------------------------------

    def _current_type(self) -> str:
        return _TYPES[self.type_combo.currentIndex()][1]

    def _on_type_changed(self) -> None:
        self._stack.setCurrentIndex(_PAGE[self._current_type()])

    def _prefill(self, data: dict) -> None:
        for i, (_, value) in enumerate(_TYPES):
            if value == data["type"]:
                self.type_combo.setCurrentIndex(i)
                break
        self.prompt.setPlainText(data["prompt"])
        self.explanation.setText(data["explanation"])
        if data["type"] in (MCQ,):
            for (edit, check), (text, correct) in zip(self._option_rows, data["options"]):
                edit.setText(text)
                check.setChecked(correct)
        elif data["type"] == TRUE_FALSE:
            correct = next((t for t, c in data["options"] if c), "True")
            self.tf_combo.setCurrentText(correct)
        else:
            self.accepted.setPlainText("\n".join(data["answers"]))

    def _save(self) -> None:
        type_ = self._current_type()
        prompt = self.prompt.toPlainText().strip()
        explanation = self.explanation.text().strip()
        if not prompt:
            QMessageBox.warning(self, "Add question", "Please enter a prompt.")
            return

        if self._context.db is None:
            return
        try:
            with self._context.db.session() as session:
                svc = QuestionService(session)
                existing = QuestionRepository(session).get(self._question_id) if self._question_id else None

                if type_ == MCQ:
                    options = [(e.text().strip(), c.isChecked()) for e, c in self._option_rows if e.text().strip()]
                    if len(options) < 2 or not any(c for _, c in options):
                        QMessageBox.warning(self, "Add question", "Add at least two options and mark a correct one.")
                        return
                    if existing:
                        svc.update(existing, prompt=prompt, explanation=explanation, options=options)
                    else:
                        svc.create_mcq(self._deck_id, prompt, options, explanation)
                elif type_ == TRUE_FALSE:
                    answer = self.tf_combo.currentText() == "True"
                    if existing:
                        svc.update(existing, prompt=prompt, explanation=explanation,
                                   options=[("True", answer), ("False", not answer)])
                    else:
                        svc.create_true_false(self._deck_id, prompt, answer, explanation)
                else:
                    accepted = [line.strip() for line in self.accepted.toPlainText().splitlines() if line.strip()]
                    if not accepted:
                        QMessageBox.warning(self, "Add question", "Add at least one accepted answer.")
                        return
                    if existing:
                        svc.update(existing, prompt=prompt, explanation=explanation, accepted=accepted)
                    else:
                        svc.create_text(self._deck_id, prompt, accepted, type_=type_, explanation=explanation)
        except Exception:
            QMessageBox.warning(self, "Save question", "Couldn't save the question. Please try again.")
            return
        self.accept()
