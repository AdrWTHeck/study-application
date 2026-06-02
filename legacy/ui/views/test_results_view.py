"""TestResultsView — score summary, per-deck chart, wrong answers, drill-down."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout, QWidget,
)

from services.quiz.test_session_controller import TestSessionController
from ui.components.score_bar_chart import ScoreBarChart


class TestResultsView(QWidget):
    """Displays the outcome of a completed test session.

    Emits drill_down_started(session_id) if the user launches a drill-down.
    Emits back_requested() to return to the question list.
    """

    drill_down_started = pyqtSignal(int)   # new drill-down session_id
    back_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._ctrl = TestSessionController()
        self._session_id: int | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Score header
        self._score_label = QLabel("–")
        self._score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._score_label.setStyleSheet("font-size: 28pt; font-weight: bold;")
        layout.addWidget(self._score_label)

        self._summary_label = QLabel("")
        self._summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._summary_label)

        # Per-deck bar chart (comprehensive tests only)
        self._chart_group = QGroupBox("Per-Deck Scores")
        chart_layout = QVBoxLayout(self._chart_group)
        self._chart = ScoreBarChart()
        self._chart.setMinimumHeight(160)
        chart_layout.addWidget(self._chart)
        layout.addWidget(self._chart_group)

        # Wrong answers list
        wrong_group = QGroupBox("Incorrect Answers")
        wrong_layout = QVBoxLayout(wrong_group)
        self._wrong_list = QListWidget()
        self._wrong_list.setAlternatingRowColors(True)
        wrong_layout.addWidget(self._wrong_list)
        layout.addWidget(wrong_group)

        # Actions
        btn_row = QHBoxLayout()
        self._drill_btn = QPushButton("Drill Down (re-test wrong answers)")
        self._drill_btn.clicked.connect(self._drill_down)
        self._back_btn = QPushButton("Back to Questions")
        self._back_btn.clicked.connect(self.back_requested.emit)
        btn_row.addWidget(self._drill_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._back_btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def show_results(self, session_id: int) -> None:
        self._session_id = session_id
        data = self._ctrl.get_results(session_id)
        if data is None:
            self._score_label.setText("N/A")
            return

        score = data.get("score") or 0.0
        total = data.get("total_items") or 0
        reviewed = data.get("items_reviewed") or 0
        t_sec = data.get("total_time_seconds") or 0.0
        avg = data.get("avg_time_per_question") or 0.0

        self._score_label.setText(f"{score:.1f}%")

        mins, secs = divmod(int(t_sec), 60)
        self._summary_label.setText(
            f"{reviewed}/{total} answered  •  "
            f"Total time: {mins}:{secs:02d}  •  "
            f"Avg per question: {avg:.1f}s"
        )

        # Per-deck chart (comprehensive only)
        deck_scores: dict | None = data.get("deck_scores")
        if deck_scores:
            # Look up deck names
            deck_labels: dict[str, float] = {}
            db = __import__("models.base", fromlist=["get_session"]).get_session()
            try:
                from repositories.deck_repository import DeckRepository
                repo = DeckRepository(db)
                for did_str, sc in deck_scores.items():
                    deck = repo.get(int(did_str))
                    label = deck.name[:12] if deck else did_str
                    deck_labels[label] = sc
            finally:
                db.close()
            self._chart.set_data(deck_labels)
            self._chart_group.setVisible(True)
        else:
            self._chart_group.setVisible(False)

        # Wrong answers
        self._wrong_list.clear()
        wrong_ids: list[int] = data.get("wrong_question_ids") or []
        if wrong_ids:
            db = __import__("models.base", fromlist=["get_session"]).get_session()
            try:
                from repositories.question_repository import QuestionRepository
                repo = QuestionRepository(db)
                for qid in wrong_ids:
                    q = repo.get(qid)
                    if q:
                        self._wrong_list.addItem(
                            QListWidgetItem(
                                f"Q: {(q.question_text or '')[:60]}\n"
                                f"A: {(q.answer or '')[:60]}"
                            )
                        )
            finally:
                db.close()

        self._drill_btn.setEnabled(bool(wrong_ids))

    # ------------------------------------------------------------------
    # Drill-down
    # ------------------------------------------------------------------

    def _drill_down(self) -> None:
        if self._session_id is None:
            return
        drill = self._ctrl.start_drill_down(self._session_id)
        if drill:
            self.drill_down_started.emit(drill.id)
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Drill Down",
                                    "No wrong answers to drill on.")
