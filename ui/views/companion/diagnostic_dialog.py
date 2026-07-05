"""Diagnostic sweep dialog — confidence self-rating before and after a session.

Shows a short list of note fronts and asks: "Could you explain this without
looking?" with a 4-point confidence scale. Non-graded; purely a study signal.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from data.models.companion import DiagnosticItem
from core.clock import now
from domain.companion.diagnostic_service import DiagnosticService

_CONFIDENCE_LABELS = ["Not sure", "Somewhat unsure", "Somewhat confident", "Confident"]
_MAX_ITEMS = 10  # cap to keep the dialog quick


@dataclass
class DiagnosticResult:
    session_key: str
    items: list[DiagnosticItem] = field(default_factory=list)
    avg_confidence: float | None = None


class DiagnosticDialog(QDialog):
    """Asks the user to rate their confidence on a sample of due cards.

    Pass ``phase="before"`` at session start or ``phase="after"`` at the end.
    When ``phase="after"`` also pass ``session_key`` to match the before items.
    """

    def __init__(
        self,
        context: AppContext,
        phase: str = "before",
        session_key: str | None = None,
        deck_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._phase = phase
        self._session_key = session_key or str(uuid.uuid4())
        self._deck_id = deck_id
        self._note_rows: list[tuple[str, int | None, QButtonGroup]] = []  # (text, note_id, group)

        self.setWindowTitle("Session diagnostic" if phase == "before" else "End-of-session check")
        self.setMinimumWidth(480)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        heading = QLabel(
            "Before your session — could you explain these without looking?"
            if phase == "before"
            else "After your session — how confident do you feel now?"
        )
        heading.setObjectName("PageSubtitle")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        hint = QLabel(
            "This is just for you. It does not affect your cards or scores."
        )
        hint.setObjectName("SettingsHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_body = QWidget()
        scroll_layout = QVBoxLayout(scroll_body)
        scroll_layout.setSpacing(16)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(scroll_body)

        notes = self._load_notes()
        for note_id, front_text in notes:
            self._add_note_row(scroll_layout, front_text, note_id)

        if not notes:
            scroll_layout.addWidget(
                QLabel("No due cards found — nothing to rate right now.")
            )

        layout.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    # -- helpers ------------------------------------------------------------

    def _load_notes(self) -> list[tuple[int | None, str]]:
        """Return up to _MAX_ITEMS (note_id, front_text) pairs for due cards."""
        if self._context.db is None:
            return []
        try:
            with self._context.db.session() as session:
                return DiagnosticService(session).due_card_fronts(self._deck_id, _MAX_ITEMS)
        except Exception:
            return []

    def _add_note_row(
        self,
        layout: QVBoxLayout,
        text: str,
        note_id: int | None,
    ) -> None:
        container = QWidget()
        container.setObjectName("DashboardCard")
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(12, 10, 12, 10)
        vbox.setSpacing(6)

        lbl = QLabel(text[:120] + ("…" if len(text) > 120 else ""))
        lbl.setObjectName("FieldLabel")
        lbl.setWordWrap(True)
        vbox.addWidget(lbl)

        group = QButtonGroup(container)
        btn_row_widget = QWidget()
        from PyQt6.QtWidgets import QHBoxLayout
        btn_row = QHBoxLayout(btn_row_widget)
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)

        for i, label in enumerate(_CONFIDENCE_LABELS):
            rb = QRadioButton(label)
            rb.setAccessibleName(f"{label} — confidence option {i}")
            group.addButton(rb, i)
            btn_row.addWidget(rb)

        btn_row.addStretch(1)
        vbox.addWidget(btn_row_widget)

        self._note_rows.append((text, note_id, group))
        layout.addWidget(container)

    # -- results ------------------------------------------------------------

    @property
    def session_key(self) -> str:
        return self._session_key

    def collect_items(self) -> list[DiagnosticItem]:
        """Build DiagnosticItem objects from the current ratings."""
        items: list[DiagnosticItem] = []
        for prompt_text, note_id, group in self._note_rows:
            rating = group.checkedId()  # -1 if nothing selected
            confidence = rating if rating >= 0 else None
            item = DiagnosticItem(
                session_key=self._session_key,
                note_id=note_id,
                prompt_text=prompt_text,
                created_at=now(),
            )
            if self._phase == "before":
                item.before_confidence = confidence
            else:
                item.after_confidence = confidence
            items.append(item)
        return items

    def avg_confidence(self) -> float | None:
        rated = [
            group.checkedId()
            for _, _, group in self._note_rows
            if group.checkedId() >= 0
        ]
        return sum(rated) / len(rated) if rated else None
