"""Bulk-add many cards from pasted text, with a preview before saving.

Paste lines (front/back pairs, Q&A blocks, or cloze markup), preview the parsed
cards, untick any you don't want (duplicates are pre-flagged), then create them.
Every card is saved as a normal, fully editable note (learner autonomy, AUT-01).
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
from sqlalchemy import select

from app.context import AppContext
from app.events import AppEvent
from data.models import NoteType
from domain.cards.bulk_generation_service import (
    CLOZE,
    PAIRS,
    QA,
    GeneratedCardDraft,
    mark_duplicates,
    parse,
)
from domain.decks.deck_service import DeckService
from domain.notes.note_service import NoteService
from ui.utils.layouts import clear_layout

_MODES = [
    ("Front / back pairs", PAIRS),
    ("Q&A blocks (Q: / A:)", QA),
    ("Cloze ({{c1::…}})", CLOZE),
]


class BulkGenerateDialog(QDialog):
    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setWindowTitle("Bulk add cards")
        self.setAccessibleName("Bulk add cards")
        self.resize(600, 620)
        self.created_count = 0

        self._decks: list[tuple[int, str]] = []
        if context.db is not None:
            with context.db.session() as session:
                self._decks = [(d.id, d.name) for d in DeckService(session).decks.by_type("card")]

        self._rows: list[tuple[QCheckBox, GeneratedCardDraft]] = []

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
            "Paste your cards below, choose how they're laid out, then preview "
            "before adding. Every card stays fully editable afterwards."
        )
        intro.setObjectName("SettingsHint")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addWidget(self._field_label("Add to deck"))
        self.deck_combo = QComboBox()
        self.deck_combo.setAccessibleName("Target deck")
        self.deck_combo.addItems([name for _, name in self._decks])
        layout.addWidget(self.deck_combo)

        layout.addWidget(self._field_label("…or new deck name (optional)"))
        self.new_deck_name = QLineEdit()
        self.new_deck_name.setAccessibleName("New deck name")
        self.new_deck_name.setPlaceholderText("Leave blank to use the deck above")
        layout.addWidget(self.new_deck_name)

        layout.addWidget(self._field_label("Card layout"))
        self.mode_combo = QComboBox()
        self.mode_combo.setAccessibleName("Card layout")
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
        self.text.setAccessibleName("Cards text")
        layout.addWidget(self.text, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setAccessibleName("Cancel bulk add")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        preview = QPushButton("Preview")
        preview.setAccessibleName("Preview cards")
        preview.clicked.connect(self._preview)
        buttons.addWidget(preview)
        layout.addLayout(buttons)
        return page

    def _update_format_hint(self) -> None:
        hints = {
            PAIRS: "One card per line. Separate front and back with a tab, a "
                   "vertical bar │, or a comma.  e.g.  Mitochondria | powerhouse",
            QA: "Use Q: for the question line and A: for the answer line.",
            CLOZE: "One cloze card per line containing {{c1::hidden text}}.",
        }
        layout_key = _MODES[self.mode_combo.currentIndex()][1]
        self._format_hint.setText(hints[layout_key])

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
        back.setAccessibleName("Back to card input")
        back.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        buttons.addWidget(back)
        buttons.addStretch(1)
        self._create_btn = QPushButton("Create cards")
        self._create_btn.setAccessibleName("Create selected cards")
        self._create_btn.clicked.connect(self._create)
        buttons.addWidget(self._create_btn)
        layout.addLayout(buttons)
        return page

    def _preview(self) -> None:
        text = self.text.toPlainText()
        if not text.strip():
            QMessageBox.warning(self, "Bulk add cards", "Please paste some text first.")
            return
        new_name = self.new_deck_name.text().strip()
        if not new_name and not self._decks:
            QMessageBox.warning(
                self, "Bulk add cards",
                "Create a deck first, or enter a new deck name.",
            )
            return

        mode = _MODES[self.mode_combo.currentIndex()][1]
        drafts = parse(text, mode)
        if not drafts:
            QMessageBox.warning(
                self, "Bulk add cards",
                "No cards could be read from that text. Check the layout and format hint.",
            )
            return

        # Flag duplicates against the chosen *existing* deck (skip for a new deck).
        if not new_name and self._context.db is not None:
            deck_id = self._decks[self.deck_combo.currentIndex()][0]
            with self._context.db.session() as session:
                mark_duplicates(session, deck_id, drafts)
        else:
            mark_duplicates_within_batch(drafts)

        self._populate_preview(drafts)
        self._stack.setCurrentIndex(1)

    def _populate_preview(self, drafts: list[GeneratedCardDraft]) -> None:
        clear_layout(self._list_layout)
        self._rows = []
        dupes = sum(1 for d in drafts if d.duplicate)
        self._preview_hint.setText(
            f"{len(drafts)} card{'s' if len(drafts) != 1 else ''} found"
            + (f"  ·  {dupes} possible duplicate{'s' if dupes != 1 else ''} unticked"
               if dupes else "")
            + ".  Untick any you don't want."
        )
        for draft in drafts:
            self._list_layout.addWidget(self._preview_row(draft))

    def _preview_row(self, draft: GeneratedCardDraft) -> QWidget:
        row = QWidget()
        row.setObjectName("DeckRow")
        row.setAutoFillBackground(False)
        h = QHBoxLayout(row)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(10)

        check = QCheckBox()
        check.setChecked(not draft.duplicate)  # duplicates start unticked
        front = (draft.front or "").strip() or "(empty)"
        label_text = front if draft.kind == "cloze" else f"{front}  →  {draft.back or '—'}"
        check.setAccessibleName(f"Include card: {label_text}")
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
            QMessageBox.warning(self, "Bulk add cards", "Tick at least one card to add.")
            return
        if self._context.db is None:
            return

        new_name = self.new_deck_name.text().strip()
        created = 0
        try:
            with self._context.db.session() as session:
                if new_name:
                    deck_id = DeckService(session).create(new_name).id
                else:
                    deck_id = self._decks[self.deck_combo.currentIndex()][0]

                type_ids = {
                    nt.name: nt.id
                    for nt in session.scalars(
                        select(NoteType).where(NoteType.name.in_(("Basic", "Cloze")))
                    )
                }
                notes = NoteService(session, self._context.engine)
                for draft in chosen:
                    if draft.kind == "cloze" and "Cloze" in type_ids:
                        notes.create_note(
                            deck_id, type_ids["Cloze"], {"Text": draft.front}, draft.tags
                        )
                        created += 1
                    elif "Basic" in type_ids:
                        notes.create_note(
                            deck_id, type_ids["Basic"],
                            {"Front": draft.front, "Back": draft.back}, draft.tags,
                        )
                        created += 1
        except Exception:
            QMessageBox.warning(self, "Bulk add cards", "Couldn't add the cards. Please try again.")
            return

        self.created_count = created
        self._context.events.publish(AppEvent.CARD_CREATED)
        self.accept()

    # -- helpers -------------------------------------------------------------

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        return label


def mark_duplicates_within_batch(drafts: list[GeneratedCardDraft]) -> None:
    """Flag only intra-batch duplicates (used when targeting a brand-new deck)."""
    seen: set[str] = set()
    for draft in drafts:
        key = " ".join((draft.front or "").lower().split())
        draft.duplicate = key in seen
        seen.add(key)
