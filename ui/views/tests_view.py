"""The Tests page: test-deck browser → question list → quiz → results.

Quiz presents one question at a time (COG-01); answers are graded via the
testing services. Timing is recorded for stats but never enforced (KBD-03).
Results offer a one-tap retest of the incorrect questions, plus a score history.
"""
from __future__ import annotations

import html
import time
from collections.abc import Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCloseEvent, QColor, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from app.events import AppEvent
from app.navigation import Destination
from ui.components.answer_button import AnswerOptionButton
from ui.components.bar_chart import BarChart
from ui.components.folder_tree import FolderTreeWidget
from ui.components.progress_ring import ProgressRing
from ui.utils.layouts import _resolve_tokens, apply_page_margins, clear_layout
from data.models.testing import OPTION_TYPES
from domain.decks.deck_service import DeckService
from domain.search.search_service import SearchService
from domain.testing.question_service import QuestionService
from domain.testing.quiz_service import QuizService
from domain.testing.related_cards import RelatedCardsService
from ui.views.comprehensive_test import ComprehensiveTestView, DeckMultiSelectDialog
from ui.views.question_editor import QuestionEditorDialog

_BROWSER, _QUESTIONS, _QUIZ, _RESULTS, _COMPREHENSIVE = 0, 1, 2, 3, 4
_TYPE_LABEL = {
    "mcq": "Multiple choice",
    "true_false": "True/False",
    "short_answer": "Short answer",
    "fill_blank": "Fill blank",
}


class TestsView(QWidget):
    __test__ = False  # not a pytest test class despite the name

    def __init__(
        self,
        context: AppContext,
        navigate: Callable[[Destination], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._navigate = navigate
        self.setObjectName("Page")
        self.setAccessibleName("Tests")
        self._deck_id: int | None = None
        self._deck_title = ""
        self._related_card_ids: list[int] = []

        # quiz state
        self._qsession = None
        self._quiz: QuizService | None = None
        self._quiz_row = None
        self._questions: list = []
        self._index = 0
        self._q_started = 0.0
        self._last_session_id: int | None = None
        self._answer_shortcuts: list[QShortcut] = []

        # Whole-session timer (display only; never enforced — KBD-03).
        self._session_started = 0.0
        self._session_timer = QTimer(self)
        self._session_timer.setInterval(1000)
        self._session_timer.timeout.connect(self._update_session_clock)

        self._stack = QStackedWidget()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._stack)

        self._stack.addWidget(self._build_browser())      # 0
        self._stack.addWidget(self._build_questions())    # 1
        self._stack.addWidget(self._build_quiz())         # 2
        self._stack.addWidget(self._build_results())      # 3

        self._comprehensive = ComprehensiveTestView(self._context)
        self._comprehensive.finished.connect(self._on_comprehensive_finished)
        self._stack.addWidget(self._comprehensive)        # 4

        self.refresh()

    # ===================================================================
    # Browser
    # ===================================================================

    def _build_browser(self) -> QWidget:
        page = QWidget()
        page.setObjectName("Page")

        layout = QVBoxLayout(page)
        apply_page_margins(layout, self._context)
        layout.setSpacing(12)

        header = QHBoxLayout()

        title = QLabel("Test decks")
        title.setObjectName("TopTitle")

        new_btn = QPushButton("New test deck")
        new_btn.setAccessibleName("New test deck")
        new_btn.clicked.connect(self._new_deck)

        bulk_btn = QPushButton("Bulk add")
        bulk_btn.setAccessibleName("Bulk add questions from text")
        bulk_btn.clicked.connect(self._bulk_add)

        comp_btn = QPushButton("Comprehensive test")
        comp_btn.setAccessibleName("Comprehensive test across decks")
        comp_btn.clicked.connect(self._start_comprehensive)

        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(comp_btn)
        header.addWidget(bulk_btn)
        header.addWidget(new_btn)

        layout.addLayout(header)

        # Collapsible test-deck tree
        self._test_tree = FolderTreeWidget(context=self._context)
        self._test_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._test_tree.customContextMenuRequested.connect(self._on_test_tree_context_menu)
        self._test_tree.item_selected.connect(self._on_test_tree_selected)
        layout.addWidget(self._test_tree, 1)

        self._no_test_decks_label = QLabel("")
        self._no_test_decks_label.setObjectName("PageSubtitle")
        self._no_test_decks_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_test_decks_label.setVisible(False)
        layout.addWidget(self._no_test_decks_label)

        # Action bar
        bar = QHBoxLayout()
        bar.addStretch(1)
        self._t_questions_btn = QPushButton("Questions")
        self._t_questions_btn.setAccessibleName("Open questions for selected test deck")
        self._t_questions_btn.setEnabled(False)
        self._t_questions_btn.clicked.connect(self._open_selected_questions)
        self._t_take_btn = QPushButton("Take test")
        self._t_take_btn.setAccessibleName("Take test for selected deck")
        self._t_take_btn.setEnabled(False)
        self._t_take_btn.clicked.connect(self._take_selected_test)
        bar.addWidget(self._t_questions_btn)
        bar.addWidget(self._t_take_btn)
        layout.addLayout(bar)

        return page

    def refresh(self) -> None:
        if self._context.db is None:
            self._test_tree.setVisible(False)
            self._no_test_decks_label.setText("No database available.")
            self._no_test_decks_label.setVisible(True)
            self._t_questions_btn.setEnabled(False)
            self._t_take_btn.setEnabled(False)
            return

        with self._context.db.session() as s:
            decks = sorted(DeckService(s).decks.by_type("test"), key=lambda d: d.name.lower())
            q_repo = QuestionService(s).questions
            counts = {d.id: q_repo.count_for_deck(d.id) for d in decks}

        if not decks:
            self._test_tree.setVisible(False)
            self._no_test_decks_label.setText("No test decks yet. Create one to add questions.")
            self._no_test_decks_label.setVisible(True)
            self._t_questions_btn.setEnabled(False)
            self._t_take_btn.setEnabled(False)
            return

        items = [
            {
                "path": d.name,
                "data": {
                    "id": d.id,
                    "name": d.name,
                    "fav": d.is_favorite,
                    "default": d.is_default,
                    "count": counts[d.id],
                },
                "fav": d.is_favorite,
                "badges": [("count", counts[d.id])],
            }
            for d in decks
        ]
        self._no_test_decks_label.setVisible(False)
        self._test_tree.setVisible(True)
        self._test_tree.populate(items)
        self._t_questions_btn.setEnabled(False)
        self._t_take_btn.setEnabled(False)

    def _on_test_tree_selected(self, data) -> None:
        is_leaf = data is not None
        self._t_questions_btn.setEnabled(is_leaf)
        self._t_take_btn.setEnabled(is_leaf and data["count"] > 0)

    def _on_test_tree_context_menu(self, pos) -> None:
        item = self._test_tree.itemAt(pos)
        if item is None:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None:
            return  # no menu for virtual parent nodes
        self._deck_menu(data["id"], data["name"], data["fav"], data["default"],
                        self._test_tree.mapToGlobal(pos))

    def _open_selected_questions(self) -> None:
        data = self._test_tree.selected_data()
        if data is not None:
            self._open_questions(data["id"], data["name"])

    def _take_selected_test(self) -> None:
        data = self._test_tree.selected_data()
        if data is not None:
            self._take_test(data["id"], data["name"])

    def _deck_menu(self, deck_id, name, fav, is_default, global_pos) -> None:
        menu = QMenu(self)
        menu.addAction(
            "Unfavorite" if fav else "Favorite",
            lambda: self._with_decks(lambda s: s.set_favorite(deck_id, not fav)),
        )
        menu.addAction("Rename…", lambda: self._rename_deck(deck_id, name))

        if not is_default:
            menu.addSeparator()
            menu.addAction("Delete", lambda: self._delete_deck(deck_id, name))

        menu.exec(global_pos)

    def _with_decks(self, fn) -> None:
        if self._context.db is None:
            return

        with self._context.db.session() as s:
            fn(DeckService(s))

        self.refresh()

    def _new_deck(self) -> None:
        name, ok = QInputDialog.getText(self, "New test deck", "Name:")
        if ok and name.strip():
            self._with_decks(lambda s: s.create(name.strip(), deck_type="test"))

    def _bulk_add(self) -> None:
        from ui.views.bulk_question_dialog import BulkQuestionDialog

        if self._context.db is None:
            return
        if BulkQuestionDialog(self._context, self).exec():
            self.refresh()

    def _start_comprehensive(self) -> None:
        if self._context.db is None:
            return

        self._close_session()

        dialog = DeckMultiSelectDialog(self._context, self)
        if dialog.exec() and dialog.selected_ids:
            self._comprehensive.start(dialog.selected_ids)
            self._stack.setCurrentIndex(_COMPREHENSIVE)

    def _on_comprehensive_finished(self) -> None:
        self._stack.setCurrentIndex(_BROWSER)
        self.refresh()

    def _rename_deck(self, deck_id, current) -> None:
        name, ok = QInputDialog.getText(self, "Rename deck", "New name:", text=current)
        if ok and name.strip():
            self._with_decks(lambda s: s.rename(deck_id, name.strip()))

    def _delete_deck(self, deck_id, name) -> None:
        confirm = QMessageBox.question(
            self,
            "Delete deck",
            f"Delete “{name}” and its questions?",
        )

        if confirm == QMessageBox.StandardButton.Yes:
            self._with_decks(lambda s: s.delete(deck_id))

    # ===================================================================
    # Questions list
    # ===================================================================

    def _build_questions(self) -> QWidget:
        page = QWidget()
        page.setObjectName("Page")

        layout = QVBoxLayout(page)
        apply_page_margins(layout, self._context)
        layout.setSpacing(12)

        header = QHBoxLayout()

        back = QPushButton("← Test decks")
        back.clicked.connect(lambda: self._stack.setCurrentIndex(_BROWSER) or self.refresh())

        self._q_title = QLabel("")
        self._q_title.setObjectName("TopTitle")
        self._q_title.setWordWrap(True)
        self._q_title.setAutoFillBackground(False)

        add = QPushButton("Add question")
        add.clicked.connect(self._add_question)

        self._q_take_btn = QPushButton("Take test")
        self._q_take_btn.clicked.connect(lambda: self._take_test(self._deck_id, self._deck_title))
        self._q_take_btn.setEnabled(False)

        header.addWidget(back)
        header.addSpacing(8)
        header.addWidget(self._q_title, 1)
        header.addWidget(add)
        header.addWidget(self._q_take_btn)

        layout.addLayout(header)

        self._q_list = self._scroll_list()
        layout.addWidget(self._q_list[0], 1)

        return page

    def _open_questions(self, deck_id, name) -> None:
        self._deck_id = deck_id
        self._deck_title = name or ""
        self._q_title.setText(self._deck_title)
        self._refresh_questions()
        self._stack.setCurrentIndex(_QUESTIONS)

    def _refresh_questions(self) -> None:
        self._clear(self._q_list[1])

        if hasattr(self, "_q_take_btn"):
            self._q_take_btn.setEnabled(False)

        if self._context.db is None or self._deck_id is None:
            return

        with self._context.db.session() as s:
            rows = [
                (q.id, q.prompt, q.type, q.is_generated_draft)
                for q in QuestionService(s).questions.for_deck(self._deck_id)
            ]

        if hasattr(self, "_q_take_btn"):
            self._q_take_btn.setEnabled(bool(rows))

        if not rows:
            empty = QLabel("No questions yet. Add one.")
            empty.setObjectName("PageSubtitle")
            empty.setAutoFillBackground(False)
            self._q_list[1].addWidget(empty)
            return

        for qid, prompt, qtype, draft in rows:
            self._q_list[1].addWidget(self._question_row(qid, prompt, qtype, draft))

    def _question_row(self, qid, prompt, qtype, draft) -> QWidget:
        row = QWidget()
        row.setObjectName("DeckRow")
        row.setAutoFillBackground(False)
        row.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        row.customContextMenuRequested.connect(
            lambda pos, q=qid, w=row: self._question_menu(q, w, pos)
        )

        h = QHBoxLayout(row)
        h.setContentsMargins(16, 10, 16, 10)
        h.setSpacing(12)

        text = (prompt or "").strip() or "(no prompt)"
        if draft:
            text += "   • draft"

        label = QLabel(text)
        label.setObjectName("DeckName")
        label.setWordWrap(True)
        label.setAutoFillBackground(False)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        h.addWidget(label, 1)

        kind = QLabel(_TYPE_LABEL.get(qtype, qtype))
        kind.setObjectName("SettingsHint")
        kind.setAutoFillBackground(False)
        h.addWidget(kind)

        edit = QPushButton("Edit")
        edit.clicked.connect(lambda _=False, q=qid: self._edit_question(q))
        h.addWidget(edit)

        return row

    def _question_menu(self, qid, anchor, pos) -> None:
        menu = QMenu(self)
        menu.addAction("Edit", lambda: self._edit_question(qid))
        menu.addAction("Delete", lambda: self._delete_question(qid))
        menu.exec(anchor.mapToGlobal(pos))

    def _add_question(self) -> None:
        if self._deck_id is None:
            return

        if QuestionEditorDialog(self._context, self._deck_id, parent=self).exec():
            self._refresh_questions()

    def _edit_question(self, qid) -> None:
        if self._deck_id is None:
            return

        dialog = QuestionEditorDialog(
            self._context,
            self._deck_id,
            question_id=qid,
            parent=self,
        )

        if dialog.exec():
            self._refresh_questions()

    def _delete_question(self, qid) -> None:
        if self._context.db is None:
            return

        with self._context.db.session() as s:
            svc = QuestionService(s)
            q = svc.questions.get(qid)
            if q is not None:
                svc.delete(q)

        self._refresh_questions()

    # ===================================================================
    # Quiz
    # ===================================================================

    def _build_quiz(self) -> QWidget:
        page = QWidget()
        page.setObjectName("Page")

        layout = QVBoxLayout(page)
        apply_page_margins(layout, self._context)
        layout.setSpacing(12)

        progress_row = QHBoxLayout()
        self._quiz_progress = QLabel("")
        self._quiz_progress.setObjectName("SettingsHint")
        self._quiz_progress.setAutoFillBackground(False)
        progress_row.addWidget(self._quiz_progress)
        progress_row.addStretch(1)
        self._quiz_clock = QLabel("⏱ 00:00")
        self._quiz_clock.setObjectName("SettingsHint")
        self._quiz_clock.setAutoFillBackground(False)
        self._quiz_clock.setAccessibleName("Elapsed session time")
        progress_row.addWidget(self._quiz_clock)
        layout.addLayout(progress_row)

        self._quiz_prompt = QTextBrowser()
        self._quiz_prompt.setObjectName("CardFace")
        self._quiz_prompt.setAccessibleName("Question")
        self._quiz_prompt.setOpenExternalLinks(False)
        self._quiz_prompt.setAutoFillBackground(False)
        _vp = self._quiz_prompt.viewport()
        if _vp is not None:
            _vp.setAutoFillBackground(False)
        layout.addWidget(self._quiz_prompt, 2)

        speak = QPushButton("🔊 Speak question")
        speak.clicked.connect(self._speak_question)
        layout.addWidget(speak, alignment=Qt.AlignmentFlag.AlignLeft)

        # Themed infinite-scroll answer area.
        # This prevents the default white QScrollArea viewport from appearing.
        (
            self._answer_scroll,
            self._answer_container,
            self._answer_layout,
        ) = self._themed_scroll_area(
            layout_margins=(0, 0, 0, 0),
            spacing=8,
        )
        self._answer_scroll.setAccessibleName("Answer choices")
        layout.addWidget(self._answer_scroll, 1)

        return page

    def _ensure_session(self):
        if self._context.db is None:
            return None

        if self._qsession is None:
            self._qsession = self._context.db.new_session()

        return self._qsession

    def _take_test(self, deck_id, name) -> None:
        if self._context.db is None or deck_id is None:
            return

        # Close any old quiz session before starting a new full test.
        self._close_session()

        self._deck_id = deck_id
        self._deck_title = name or ""

        session = self._ensure_session()
        if session is None:
            return

        self._quiz = QuizService(session)
        questions = self._quiz.questions_for(deck_id)

        if not questions:
            QMessageBox.information(self, "Take test", "This deck has no questions yet.")
            self._close_session()
            return

        self._start_quiz(deck_id, questions)

    def _start_quiz(self, deck_id, questions) -> None:
        if self._quiz is None or deck_id is None or not questions:
            return

        self._quiz_row = self._quiz.start(deck_id)
        self._questions = list(questions)
        self._index = 0
        self._session_started = time.monotonic()
        self._session_timer.start()
        self._update_session_clock()
        self._stack.setCurrentIndex(_QUIZ)
        self._show_question()

    def _update_session_clock(self) -> None:
        if self._session_started <= 0:
            return
        elapsed = int(time.monotonic() - self._session_started)
        m, s = divmod(elapsed, 60)
        self._quiz_clock.setText(f"⏱ {m:02d}:{s:02d}")

    def _show_question(self) -> None:
        if self._index >= len(self._questions):
            self._finish_quiz()
            return

        question = self._questions[self._index]

        self._quiz_progress.setText(
            f"Question {self._index + 1} of {len(self._questions)}"
        )
        self._quiz_prompt.setText(question.prompt or "")

        self._clear(self._answer_layout)
        self._clear_answer_shortcuts()

        if question.type in OPTION_TYPES:
            hint = QLabel("Click an answer or press its number.")
            hint.setObjectName("SettingsHint")
            self._answer_layout.addWidget(hint)
            for i, option in enumerate(question.options, 1):
                button = AnswerOptionButton(i, option.text)
                button.clicked.connect(lambda _=False, text=option.text: self._submit(text))
                self._answer_layout.addWidget(button)
                # Number shortcut (1–9) selects this option.
                if i <= 9:
                    self._add_answer_shortcut(str(i), option.text)
            # True/False also responds to T / F.
            if question.type == "true_false":
                for opt in question.options:
                    low = (opt.text or "").strip().lower()
                    if low == "true":
                        self._add_answer_shortcut("t", opt.text)
                    elif low == "false":
                        self._add_answer_shortcut("f", opt.text)
        else:
            field = QLineEdit()
            field.setAccessibleName("Your answer")
            field.setPlaceholderText("Type your answer and press Enter")
            field.returnPressed.connect(lambda: self._submit(field.text()))

            submit = QPushButton("Submit")
            submit.clicked.connect(lambda: self._submit(field.text()))

            self._answer_layout.addWidget(field)
            self._answer_layout.addWidget(submit, alignment=Qt.AlignmentFlag.AlignLeft)

        self._answer_layout.addStretch(1)
        self._q_started = time.monotonic()

    def _add_answer_shortcut(self, key: str, response: str) -> None:
        shortcut = QShortcut(QKeySequence(key), self)
        shortcut.activated.connect(lambda r=response: self._submit(r))
        self._answer_shortcuts.append(shortcut)

    def _clear_answer_shortcuts(self) -> None:
        for shortcut in self._answer_shortcuts:
            shortcut.setParent(None)
            shortcut.deleteLater()
        self._answer_shortcuts = []

    def _submit(self, response: str) -> None:
        if (
            self._quiz is None
            or self._quiz_row is None
            or self._qsession is None
            or self._index >= len(self._questions)
        ):
            return

        elapsed_ms = int((time.monotonic() - self._q_started) * 1000)
        threshold = int(self._context.settings.get("short_answer_fuzzy_threshold"))

        try:
            self._quiz.record(
                self._quiz_row,
                self._questions[self._index],
                response,
                time_ms=elapsed_ms,
                fuzzy_threshold=threshold,
            )
            self._qsession.commit()
        except Exception as exc:  # noqa: BLE001
            self._qsession.rollback()
            QMessageBox.warning(
                self,
                "Could not save answer",
                f"Your answer could not be saved:\n{exc}",
            )
            return

        self._index += 1
        self._show_question()

    def _speak_question(self) -> None:
        if self._context.tts and self._index < len(self._questions):
            question = self._questions[self._index]
            self._context.tts.speak(question.prompt or "")

    def _finish_quiz(self) -> None:
        self._session_timer.stop()
        if self._quiz is None or self._quiz_row is None or self._qsession is None:
            self._close_session()
            self._stack.setCurrentIndex(_BROWSER)
            return

        try:
            self._quiz.finish(self._quiz_row)
            self._qsession.commit()
        except Exception as exc:  # noqa: BLE001
            self._qsession.rollback()
            QMessageBox.warning(
                self,
                "Could not finish quiz",
                f"The quiz could not be finished:\n{exc}",
            )
            self._close_session()
            self._stack.setCurrentIndex(_BROWSER)
            return

        self._last_session_id = self._quiz_row.id
        self._context.events.publish(AppEvent.QUIZ_COMPLETED, self._last_session_id)
        self._show_results()

    # ===================================================================
    # Results
    # ===================================================================

    def _build_results(self) -> QWidget:
        page = QWidget()
        page.setObjectName("Page")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 20, 40, 20)
        layout.setSpacing(12)

        self._results_header = QLabel("")
        self._results_header.setObjectName("TopTitle")
        self._results_header.setAutoFillBackground(False)
        layout.addWidget(self._results_header)

        # Partitioned dashboard: a scrollable grid of themed metric cards.
        scroll, _container, self._results_grid_wrap = self._themed_scroll_area(
            layout_margins=(0, 0, 0, 0), spacing=14,
        )
        self._results_grid = QGridLayout()
        self._results_grid.setHorizontalSpacing(14)
        self._results_grid.setVerticalSpacing(14)
        self._results_grid.setColumnStretch(0, 1)
        self._results_grid.setColumnStretch(1, 1)
        self._results_grid_wrap.addLayout(self._results_grid)
        self._results_grid_wrap.addWidget(self._build_related_section())
        self._results_grid_wrap.addStretch(1)
        layout.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        self._retry_btn = QPushButton("Retry incorrect")
        self._retry_btn.clicked.connect(self._retry_incorrect)

        self._related_btn = QPushButton("Review related cards")
        self._related_btn.setAccessibleName("Scroll to related cards to review")
        self._related_btn.setObjectName("GhostButton")
        self._related_btn.clicked.connect(self._scroll_to_related)
        self._related_btn.setVisible(False)

        done = QPushButton("Done")
        done.setObjectName("PrimaryButton")
        done.clicked.connect(self._done_results)

        buttons.addWidget(self._retry_btn)
        buttons.addWidget(self._related_btn)
        buttons.addStretch(1)
        buttons.addWidget(done)
        layout.addLayout(buttons)
        self._results_scroll = scroll
        return page

    def _scroll_to_related(self) -> None:
        self._results_scroll.ensureWidgetVisible(self._related_header)
        self._related_header.setFocus()

    def _build_related_section(self) -> QWidget:
        """Inline 'related cards to review' section on the results page.

        Surfaces automatically (no separate page, no per-card selection) — this
        is a study aid, never a scheduling change, per AUT-01/docs/RELATED_CARDS.md.
        """
        section = QWidget()
        box = QVBoxLayout(section)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(8)

        self._related_header = QLabel("Related cards to review")
        self._related_header.setObjectName("SettingsSection")
        self._related_header.setVisible(False)
        box.addWidget(self._related_header)

        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(8)
        list_widget.setVisible(False)
        self._related_list = (list_widget, list_layout)
        box.addWidget(list_widget)

        self._nudge_btn = QPushButton("Bring related cards forward")
        self._nudge_btn.setAccessibleName("Bring related cards forward in my next review")
        self._nudge_btn.clicked.connect(self._nudge_related)
        self._nudge_btn.setVisible(False)
        box.addWidget(self._nudge_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        return section

    # -- result cards -------------------------------------------------------

    def _result_card(self, title: str, *, min_height: int = 120):
        """A themed result card with a mono eyebrow title. Returns (card, body)."""
        card = QWidget()
        card.setObjectName("ResultCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setMinimumHeight(min_height)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        outer = QVBoxLayout(card)
        outer.setContentsMargins(14, 12, 14, 14)
        outer.setSpacing(8)
        outer.setAlignment(Qt.AlignmentFlag.AlignTop)

        header = QLabel(title.upper())
        header.setObjectName("Eyebrow")
        header.setAccessibleName(title)
        outer.addWidget(header)

        body = QVBoxLayout()
        body.setSpacing(8)
        body.setAlignment(Qt.AlignmentFlag.AlignTop)
        outer.addLayout(body)
        return card, body

    def _show_results(self) -> None:
        if self._quiz is None or self._last_session_id is None or self._deck_id is None:
            self._close_session()
            self._stack.setCurrentIndex(_BROWSER)
            return

        sid = self._last_session_id
        results = self._quiz.results_for(sid)
        answered = len(results)
        correct = sum(1 for r in results if r.is_correct)
        score = self._quiz.session_score(sid)
        self._results_header.setText(f"Results — {self._deck_title}")

        incorrect = self._quiz.incorrect_questions(sid)
        self._retry_btn.setEnabled(bool(incorrect))
        self._retry_btn.setText(f"Retry incorrect ({len(incorrect)})")

        pal = self._context.palette
        tokens = _resolve_tokens(self._context)

        clear_layout(self._results_grid)
        row = 0

        # Score ring — colour band by score, detail text carries the numbers.
        score_card, score_body = self._result_card("Score")
        ring = ProgressRing(diameter=tokens.density.space(22))
        if score >= 80:
            band = pal.success
        elif score >= 50:
            band = pal.state_learning
        else:
            band = pal.danger
        ring.set_value(score, f"{correct} of {answered} correct", QColor(band))
        ring_row = QHBoxLayout()
        ring_row.addStretch(1)
        ring_row.addWidget(ring)
        ring_row.addStretch(1)
        score_body.addLayout(ring_row)

        # Correct / missed stat boxes under the ring.
        boxes = QHBoxLayout()
        boxes.setSpacing(10)
        boxes.addWidget(self._score_stat_box(correct, "correct", "good"))
        boxes.addWidget(self._score_stat_box(answered - correct, "missed", "bad"))
        score_body.addLayout(boxes)
        self._results_grid.addWidget(score_card, row, 0)

        # Accuracy by type + weakest-area insight.
        acc = self._quiz.accuracy_by_type(sid)
        type_card, type_body = self._result_card("Accuracy by question type")
        if acc:
            chart = BarChart()
            chart.set_data([
                (_TYPE_LABEL.get(k, k), (100.0 * cc / tt) if tt else 0.0)
                for k, (cc, tt) in acc.items()
            ])
            type_body.addWidget(chart)
            insight = self._insight_box(acc)
            if insight is not None:
                type_body.addWidget(insight)
        else:
            type_body.addWidget(self._muted("No per-type data for this attempt."))
        self._results_grid.addWidget(type_card, row, 1)
        row += 1

        # Timing card.
        total_s = self._quiz.session_duration_ms(sid) / 1000.0
        tm, ts = divmod(int(total_s), 60)
        avg_s = (total_s / answered) if answered else 0.0
        timing_card, timing_body = self._result_card("Timing")
        timing_body.addWidget(self._metric(f"{tm}m {ts:02d}s", "total time"))
        timing_body.addWidget(self._muted(f"{avg_s:.1f}s average per question"))
        self._results_grid.addWidget(timing_card, row, 0)

        # Recent scores trend (bar chart).
        history = self._quiz.history(self._deck_id)
        if len(history) > 1:
            trend_card, trend_body = self._result_card("Recent scores")
            chart = BarChart()
            chart.set_data([
                (f"#{i+1}", sc) for i, (_sid, _fin, sc) in enumerate(history[-6:])
            ])
            trend_body.addWidget(chart)
            self._results_grid.addWidget(trend_card, row, 1)
        row += 1

        # Slowest questions (larger, spans columns).
        slowest = self._quiz.slowest_questions(sid, limit=5)
        if slowest:
            slow_card, slow_body = self._result_card("Questions that took the longest", min_height=80)
            for question, ms in slowest:
                prompt = (question.prompt or "(no prompt)").strip()
                if len(prompt) > 110:
                    prompt = prompt[:110] + "…"
                slow_body.addWidget(self._muted(f"{ms / 1000:.1f}s  —  {prompt}", wrap=True))
            self._results_grid.addWidget(slow_card, row, 0, 1, 2)
            row += 1

        # Answer review (larger, spans columns).
        review = self._quiz.answer_review(sid)
        if review:
            review_card, review_body = self._result_card("Answer review", min_height=80)
            for i, ans in enumerate(review, 1):
                review_body.addWidget(self._answer_review_row(i, ans))
            self._results_grid.addWidget(review_card, row, 0, 1, 2)
            row += 1

        self._show_related()
        self._related_btn.setVisible(self._related_header.isVisibleTo(self))
        self._stack.setCurrentIndex(_RESULTS)

    def _score_stat_box(self, count: int, caption: str, tone: str) -> QWidget:
        box = QWidget()
        box.setObjectName("ScoreStatBox")
        box.setProperty("tone", tone)
        box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        v = QVBoxLayout(box)
        v.setContentsMargins(12, 8, 12, 8)
        v.setSpacing(0)
        value = QLabel(str(count))
        value.setObjectName("ScoreStatValue")
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cap = QLabel(caption)
        cap.setObjectName("ScoreStatCaption")
        cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(value)
        v.addWidget(cap)
        box.setAccessibleName(f"{count} {caption}")
        return box

    def _insight_box(self, acc: dict) -> QWidget | None:
        """Accent callout naming the weakest question type (skipped when clean)."""
        weakest = None
        weakest_pct = 100.0
        for qtype, (cc, tt) in acc.items():
            if tt <= 0 or cc >= tt:
                continue
            pct = 100.0 * cc / tt
            if pct < weakest_pct:
                weakest_pct = pct
                weakest = qtype
        if weakest is None:
            return None
        box = QWidget()
        box.setObjectName("InsightBox")
        box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        v = QVBoxLayout(box)
        v.setContentsMargins(12, 8, 12, 8)
        v.setSpacing(2)
        title = QLabel("📌  Weakest area")
        title.setObjectName("InsightTitle")
        text = QLabel(
            f"{_TYPE_LABEL.get(weakest, weakest)} questions — {weakest_pct:.0f}% correct. "
            "Worth a focused review."
        )
        text.setObjectName("InsightText")
        text.setWordWrap(True)
        v.addWidget(title)
        v.addWidget(text)
        box.setAccessibleName(f"Weakest area: {_TYPE_LABEL.get(weakest, weakest)}, {weakest_pct:.0f} percent correct")
        return box

    def _answer_review_row(self, number: int, ans) -> QWidget:
        row = QWidget()
        # Misses get the red-edged card treatment; the ✓/✗ mark carries the
        # distinction in text as well (VIS-03).
        row.setObjectName("DeckRow" if ans.is_correct else "MissedCard")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        box = QVBoxLayout(row)
        box.setContentsMargins(12, 8, 12, 8)
        box.setSpacing(2)
        mark = "✓" if ans.is_correct else "✗"
        t = f"  ·  {ans.time_ms / 1000:.1f}s" if ans.time_ms else ""
        head = QLabel(f"{mark}  Q{number}. {ans.prompt or '(no prompt)'}{t}")
        head.setObjectName("DeckName")
        head.setWordWrap(True)
        box.addWidget(head)
        yours = QLabel(f"Your answer: {ans.user_response or '(blank)'}")
        yours.setObjectName("AnswerQuote")
        yours.setProperty("tone", "" if ans.is_correct else "yours")
        yours.setWordWrap(True)
        box.addWidget(yours)
        if not ans.is_correct and ans.correct_answer:
            right = QLabel(f"Correct answer: {ans.correct_answer}")
            right.setObjectName("AnswerQuote")
            right.setProperty("tone", "correct")
            right.setWordWrap(True)
            box.addWidget(right)
        if ans.explanation:
            why = QLabel(f"Why: {ans.explanation}")
            why.setObjectName("AnswerQuote")
            why.setProperty("tone", "why")
            why.setWordWrap(True)
            box.addWidget(why)
        return row

    def _metric(self, value: str, caption: str) -> QWidget:
        host = QWidget()
        v = QVBoxLayout(host)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        big = QLabel(value)
        big.setObjectName("StatCardValue")
        v.addWidget(big)
        v.addWidget(self._muted(caption))
        return host

    def _muted(self, text: str, *, wrap: bool = False) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SettingsHint")
        label.setWordWrap(wrap)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    # ===================================================================
    # Related cards (docs/RELATED_CARDS.md) — surfaces automatically on the
    # results page after a miss; the only opt-in action is the single "bring
    # forward" button, confirmed before it touches scheduling (AUT-01).
    # ===================================================================

    def _show_related(self) -> None:
        """Populate the inline related-cards section from the latest struggles.

        Pure surfacing — this never reschedules anything on its own. Only
        `_nudge_related`, after an explicit confirmation, is allowed to do that.
        """
        self._clear(self._related_list[1])
        self._related_card_ids = []
        self._related_header.setVisible(False)
        self._related_list[0].setVisible(False)
        self._nudge_btn.setVisible(False)
        self._nudge_btn.setEnabled(True)

        if (self._context.db is None or self._last_session_id is None
                or not self._context.settings.get("related_cards_enabled")):
            return

        with self._context.db.session() as s:
            search = SearchService(self._context.db)
            search.ensure_built()
            struggles = RelatedCardsService(s, search).suggestions_for_session(
                self._last_session_id
            )

        if not struggles:
            return

        self._related_card_ids = RelatedCardsService.all_card_ids(struggles)

        intro = self._muted(
            "These cards share material with a question you found tricky.", wrap=True,
        )
        self._related_list[1].addWidget(intro)
        for struggle in struggles:
            self._related_list[1].addWidget(self._struggle_group(struggle))

        self._related_header.setVisible(True)
        self._related_list[0].setVisible(True)
        if self._related_card_ids:
            n = len(self._related_card_ids)
            self._nudge_btn.setText(f"Bring {n} related card{'s' if n != 1 else ''} forward")
            self._nudge_btn.setVisible(True)

    def _struggle_group(self, struggle) -> QWidget:
        group = QWidget()
        group.setObjectName("DeckRow")
        group.setAutoFillBackground(False)
        box = QVBoxLayout(group)
        box.setContentsMargins(16, 10, 16, 10)
        box.setSpacing(6)

        head = (struggle.prompt or "").strip() or "(no prompt)"
        if struggle.miss_count > 1:
            head += f"  ·  missed {struggle.miss_count} times"
        prompt = QLabel(head)
        prompt.setObjectName("DeckName")
        prompt.setWordWrap(True)
        box.addWidget(prompt)

        for card in struggle.related:
            box.addLayout(self._related_row(card))
        return group

    def _related_row(self, card) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        source = "  ·  from this question's card" if card.is_source else ""
        label = QLabel(f"{card.preview or '(empty note)'} — in “{card.deck_name}”{source}")
        label.setObjectName("SettingsHint")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(label, 1)

        open_btn = QPushButton("Open in Cards")
        open_btn.setAccessibleName(f"Open {card.deck_name} in Cards")
        open_btn.clicked.connect(lambda _=False: self._open_related_in_cards())
        row.addWidget(open_btn)
        return row

    def _open_related_in_cards(self) -> None:
        # Deep-linking to the specific deck is possible-later-work (see
        # docs/RELATED_CARDS.md); for now this matches the Search view's
        # behaviour of jumping to the section.
        if self._navigate is not None:
            self._navigate(Destination.CARDS)

    def _nudge_related(self) -> None:
        """Opt-in reschedule of every related card surfaced this session.

        Never automatic (AUT-01): requires the button press above plus this
        plain-language confirmation before touching any due date.
        """
        if not self._related_card_ids or self._context.db is None:
            return

        confirmed = QMessageBox.question(
            self, "Bring cards forward",
            "This only moves these cards earlier in your queue — it doesn't "
            "change how well you've learned them. Continue?",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return

        with self._context.db.session() as s:
            moved = RelatedCardsService(s, SearchService(self._context.db)).nudge_cards_due_now(
                self._related_card_ids
            )

        QMessageBox.information(
            self, "Done",
            f"{moved} related card{'s' if moved != 1 else ''} will appear in your next review.",
        )
        self._nudge_btn.setEnabled(False)

    def _retry_incorrect(self) -> None:
        if self._quiz is None or self._last_session_id is None or self._deck_id is None:
            return

        incorrect = self._quiz.incorrect_questions(self._last_session_id)
        if not incorrect:
            return

        self._start_quiz(self._deck_id, incorrect)

    def _done_results(self) -> None:
        self._close_session()
        self._stack.setCurrentIndex(_BROWSER)
        self.refresh()

    # ===================================================================
    # Helpers
    # ===================================================================

    def _themed_scroll_area(
        self,
        *,
        layout_margins: tuple[int, int, int, int] = (0, 0, 0, 0),
        spacing: int = 8,
    ) -> tuple[QScrollArea, QWidget, QVBoxLayout]:
        """Create a scroll area that follows the app theme.

        QScrollArea often shows a default white viewport unless the scroll area,
        viewport, and inner container are all made theme-aware. Use this helper
        for list-like areas and future answer formats that need vertical scroll.
        """
        scroll = QScrollArea()
        scroll.setObjectName("Page")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setAutoFillBackground(False)

        viewport = scroll.viewport()
        if viewport is not None:
            viewport.setObjectName("Page")
            viewport.setAutoFillBackground(False)

        container = QWidget()
        container.setObjectName("Page")
        container.setAutoFillBackground(False)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(*layout_margins)
        layout.setSpacing(spacing)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(container)
        return scroll, container, layout

    def _scroll_list(self) -> tuple[QScrollArea, QVBoxLayout]:
        scroll, _container, layout = self._themed_scroll_area(
            layout_margins=(0, 0, 0, 0),
            spacing=8,
        )
        return scroll, layout

    def _clear(self, layout) -> None:
        clear_layout(layout)

    def _close_session(self) -> None:
        self._session_timer.stop()
        self._session_started = 0.0
        self._clear_answer_shortcuts()
        if self._qsession is not None:
            try:
                self._qsession.commit()
            except Exception:
                self._qsession.rollback()
            finally:
                self._qsession.close()

        self._qsession = None
        self._quiz = None
        self._quiz_row = None
        self._questions = []
        self._index = 0
        self._q_started = 0.0

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        self._close_session()
        super().closeEvent(event)