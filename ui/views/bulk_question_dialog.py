"""Bulk-add many test questions from pasted text, with a preview before saving.

The questions counterpart of :class:`ui.views.bulk_generate_dialog`. Paste lines
(short-answer pairs, multiple-choice, or true/false), preview the parsed
questions, untick any you don't want (duplicates are pre-flagged), then create
them in a chosen test deck. Every question is a normal, fully editable draft.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from app.events import AppEvent
from data.models.testing import MCQ, SHORT_ANSWER, TRUE_FALSE
from domain.decks.deck_service import DeckService
from domain.testing.bulk_question_service import (
    MCQ_MODE,
    SHORT,
    TF,
    GeneratedQuestionDraft,
    mark_duplicates,
    parse,
)
from domain.testing.question_service import QuestionService
from ui.utils.layouts import clear_layout

_MODES = [
    ("Short answer", SHORT),
    ("Multiple choice", MCQ_MODE),
    ("True / False", TF),
]
_HINTS = {
    SHORT: "One question per line:  prompt | accepted answer  "
           "(add alternatives with /, e.g.  Capital of France? | Paris / paris)",
    MCQ_MODE: "One question per line:  prompt | *Correct | Wrong | Wrong  "
              "(mark the right option with a leading *).",
    TF: "One statement per line:  statement | true   (or false / t / f / yes / no).",
}


class BulkQuestionDialog(QDialog):
    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setWindowTitle("Bulk add questions")
        self.setAccessibleName("Bulk add questions")
        self.resize(600, 620)
        self.created_count = 0

        self._decks: list[tuple[int, str]] = []
        if context.db is not None:
            with context.db.session() as session:
                self._decks = [(d.id, d.name) for d in DeckService(session).decks.by_type("test")]

        self._rows: list[tuple[QCheckBox, GeneratedQuestionDraft]] = []

        self._stack = QStackedWidget()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._stack)

        self._stack.addWidget(self._build_input_page())     # 0
        self._stack.addWidget(self._build_preview_page())   # 1

    # -- page 0: input -------------------------------------------------------

    def _build_input_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(8)

        intro = QLabel(
            "Paste your questions below, choose the type, then preview before "
            "adding. Every question stays fully editable afterwards."
        )
        intro.setObjectName("SettingsHint")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addWidget(self._field_label("Add to test deck"))
        self.deck_combo = QComboBox()
        self.deck_combo.setAccessibleName("Target test deck")
        self.deck_combo.addItems([name for _, name in self._decks])
        layout.addWidget(self.deck_combo)

        layout.addWidget(self._field_label("…or new test deck name (optional)"))
        self.new_deck_name = QLineEdit()
        self.new_deck_name.setAccessibleName("New test deck name")
        self.new_deck_name.setPlaceholderText("Leave blank to use the deck above")
        layout.addWidget(self.new_deck_name)

        layout.addWidget(self._field_label("Question type"))
        self.mode_combo = QComboBox()
        self.mode_combo.setAccessibleName("Question type")
        self.mode_combo.addItems([label for label, _ in _MODES])
        layout.addWidget(self.mode_combo)

        self._format_hint = QLabel()
        self._format_hint.setObjectName("SettingsHint")
        self._format_hint.setWordWrap(True)
        layout.addWidget(self._format_hint)
        self.mode_combo.currentIndexChanged.connect(self._update_format_hint)
        self._update_format_hint()

        layout.addWidget(self._field_label("Text"))
        self.text = QPlainTextEdit()
        self.text.setAccessibleName("Questions text")
        layout.addWidget(self.text, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setAccessibleName("Cancel bulk add")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        preview = QPushButton("Preview")
        preview.setAccessibleName("Preview questions")
        preview.clicked.connect(self._preview)
        buttons.addWidget(preview)
        layout.addLayout(buttons)
        return page

    def _update_format_hint(self) -> None:
        self._format_hint.setText(_HINTS[_MODES[self.mode_combo.currentIndex()][1]])

    # -- page 1: preview -----------------------------------------------------

    def _build_preview_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(8)

        self._preview_title = QLabel("Preview")
        self._preview_title.setObjectName("TopTitle")
        layout.addWidget(self._preview_title)

        self._preview_hint = QLabel()
        self._preview_hint.setObjectName("SettingsHint")
        self._preview_hint.setWordWrap(True)
        layout.addWidget(self._preview_hint)

        scroll = QScrollArea()
        scroll.setObjectName("Page")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        viewport = scroll.viewport()
        if viewport is not None:
            viewport.setObjectName("Page")
        self._list_container = QWidget()
        self._list_container.setObjectName("Page")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setSpacing(6)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._list_container)
        layout.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        back = QPushButton("← Back")
        back.setAccessibleName("Back to question input")
        back.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        buttons.addWidget(back)
        buttons.addStretch(1)
        self._create_btn = QPushButton("Create questions")
        self._create_btn.setAccessibleName("Create selected questions")
        self._create_btn.clicked.connect(self._create)
        buttons.addWidget(self._create_btn)
        layout.addLayout(buttons)
        return page

    def _preview(self) -> None:
        text = self.text.toPlainText()
        if not text.strip():
            QMessageBox.warning(self, "Bulk add questions", "Please paste some text first.")
            return
        new_name = self.new_deck_name.text().strip()
        if not new_name and not self._decks:
            QMessageBox.warning(
                self, "Bulk add questions",
                "Create a test deck first, or enter a new test deck name.",
            )
            return

        mode = _MODES[self.mode_combo.currentIndex()][1]
        drafts = parse(text, mode)
        if not drafts:
            QMessageBox.warning(
                self, "Bulk add questions",
                "No questions could be read from that text. Check the format hint.",
            )
            return

        if not new_name and self._context.db is not None:
            deck_id = self._decks[self.deck_combo.currentIndex()][0]
            with self._context.db.session() as session:
                mark_duplicates(session, deck_id, drafts)

        self._populate_preview(drafts)
        self._stack.setCurrentIndex(1)

    def _populate_preview(self, drafts: list[GeneratedQuestionDraft]) -> None:
        clear_layout(self._list_layout)
        self._rows = []
        dupes = sum(1 for d in drafts if d.duplicate)
        self._preview_hint.setText(
            f"{len(drafts)} question{'s' if len(drafts) != 1 else ''} found"
            + (f"  ·  {dupes} possible duplicate{'s' if dupes != 1 else ''} unticked"
               if dupes else "")
            + ".  Untick any you don't want."
        )
        for draft in drafts:
            self._list_layout.addWidget(self._preview_row(draft))

    def _preview_row(self, draft: GeneratedQuestionDraft) -> QWidget:
        row = QWidget()
        row.setObjectName("DeckRow")
        row.setAutoFillBackground(False)
        h = QHBoxLayout(row)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(10)

        check = QCheckBox()
        check.setChecked(not draft.duplicate)
        prompt = (draft.prompt or "").strip() or "(empty)"
        label_text = f"{prompt}   —   {draft.summary()}"
        check.setAccessibleName(f"Include question: {label_text}")
        h.addWidget(check)

        label = QLabel(label_text)
        label.setObjectName("DeckName")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        h.addWidget(label, 1)

        if draft.duplicate:
            chip = QLabel("duplicate")
            chip.setObjectName("SettingsHint")
            chip.setAccessibleName("Possible duplicate")
            h.addWidget(chip)

        self._rows.append((check, draft))
        return row

    def _create(self) -> None:
        chosen = [draft for check, draft in self._rows if check.isChecked()]
        if not chosen:
            QMessageBox.warning(self, "Bulk add questions", "Tick at least one question to add.")
            return
        if self._context.db is None:
            return

        new_name = self.new_deck_name.text().strip()
        created = 0
        try:
            with self._context.db.session() as session:
                if new_name:
                    deck_id = DeckService(session).create(new_name, deck_type="test").id
                else:
                    deck_id = self._decks[self.deck_combo.currentIndex()][0]

                qs = QuestionService(session)
                for draft in chosen:
                    if draft.qtype == MCQ and draft.options:
                        qs.create_mcq(deck_id, draft.prompt, draft.options)
                    elif draft.qtype == TRUE_FALSE:
                        qs.create_true_false(deck_id, draft.prompt, draft.answer)
                    else:
                        qs.create_text(deck_id, draft.prompt, draft.accepted, SHORT_ANSWER)
                    created += 1
        except Exception:
            QMessageBox.warning(self, "Bulk add questions", "Couldn't add the questions. Please try again.")
            return

        self.created_count = created
        self._context.events.publish(AppEvent.QUESTION_CREATED)
        self.accept()

    # -- helpers -------------------------------------------------------------

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        return label
