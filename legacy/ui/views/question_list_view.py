"""QuestionListView — browse questions, generate, start test session."""
from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from services.quiz.quiz_service import QuizService
from ui.components.deck_selector import DeckSelector


class _GenerateWorker(QThread):
    finished = pyqtSignal(int)

    def __init__(self, doc_id: int, deck_id: int) -> None:
        super().__init__()
        self._doc_id = doc_id
        self._deck_id = deck_id

    def run(self) -> None:
        self.finished.emit(
            QuizService().generate_for_document(self._doc_id, self._deck_id)
        )


class QuestionListView(QWidget):
    """Lists all questions for a test deck with CRUD and session launch.

    Emits start_session(deck_id, count) to begin a test.
    """

    start_session = pyqtSignal(int, int)   # deck_id, question count

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._svc = QuizService()
        self._deck_id: int = -1
        self._q_ids: list[int] = []
        self._worker: _GenerateWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._deck_sel = DeckSelector("test", label="Test Deck:")
        self._deck_sel.deck_changed.connect(self._on_deck_changed)
        layout.addWidget(self._deck_sel)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        for label, slot in [
            ("New",    self._new_question),
            ("Edit",   self._edit_question),
            ("Delete", self._delete_question),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)

        layout.addLayout(btn_row)

        self._start_btn = QPushButton("Start Test Session")
        self._start_btn.clicked.connect(self._start_session)
        layout.addWidget(self._start_btn)

        self._status = QLabel("")
        layout.addWidget(self._status)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _on_deck_changed(self, deck_id: int) -> None:
        self._deck_id = deck_id
        self._refresh()

    def _refresh(self) -> None:
        self._list.clear()
        self._q_ids = []
        if self._deck_id < 0:
            return
        for q in self._svc.get_questions_for_deck(self._deck_id):
            tag = q.type.replace("_", " ")
            self._list.addItem(
                QListWidgetItem(f"[{tag}] {(q.question_text or '')[:70]}")
            )
            self._q_ids.append(q.id)
        self._status.setText(f"{len(self._q_ids)} question(s)")

    def _selected_q_id(self) -> int | None:
        idx = self._list.currentRow()
        return self._q_ids[idx] if 0 <= idx < len(self._q_ids) else None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _new_question(self) -> None:
        if self._deck_id < 0:
            return
        from ui.views.question_form_view import QuestionFormView
        dlg = QuestionFormView(self._deck_id, self._svc, parent=self)
        dlg.question_saved.connect(lambda _: self._refresh())
        dlg.exec()

    def _edit_question(self) -> None:
        qid = self._selected_q_id()
        if qid is None:
            return
        from ui.views.question_form_view import QuestionFormView
        dlg = QuestionFormView(self._deck_id, self._svc,
                               question_id=qid, parent=self)
        dlg.question_saved.connect(lambda _: self._refresh())
        dlg.exec()

    def _delete_question(self) -> None:
        qid = self._selected_q_id()
        if qid is None:
            return
        ans = QMessageBox.question(self, "Delete Question",
                                   "Delete this question permanently?")
        if ans == QMessageBox.StandardButton.Yes:
            self._svc.delete_question(qid)
            self._refresh()

    def _start_session(self) -> None:
        if self._deck_id < 0 or not self._q_ids:
            QMessageBox.information(self, "No Questions",
                                    "Generate or add questions first.")
            return
        self.start_session.emit(self._deck_id, len(self._q_ids))

    def refresh_deck_list(self) -> None:
        self._deck_sel.refresh()
