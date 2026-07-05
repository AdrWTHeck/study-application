"""Right-side compact deadline priority list, grouped by state."""
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from domain.deadlines.deadline_service import DeadlineSummary
from ui.utils.layouts import clear_layout
from ui.views.deadlines.view_models import ForecastWorkItem


def _priority_meta(summary: DeadlineSummary, work: ForecastWorkItem | None) -> str:
    if summary.is_past:
        remaining = summary.total_remaining
        if remaining > 0:
            return f"Past  ·  {remaining} card{'s' if remaining != 1 else ''} incomplete"
        return "Past  ·  completed"

    days = summary.days_left
    days_str = "Due today" if days == 0 else f"{days}d left"

    if not summary.deck_names:
        return f"{days_str}  ·  no decks linked"
    if summary.total_remaining == 0:
        return f"{days_str}  ·  all done"
    if work and work.assigned_today > 0:
        return f"{days_str}  ·  {work.completed_today} / {work.assigned_today} today"
    return days_str


class DeadlinePriorityCard(QWidget):
    """Compact deadline card for the priority panel."""

    def __init__(
        self,
        summary: DeadlineSummary,
        work_item: ForecastWorkItem | None,
        on_edit: Callable,
        on_delete: Callable,
        on_vacations: Callable,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DeadlinePriorityCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setAccessibleName(f"Deadline: {summary.name}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)

        name_lbl = QLabel(summary.name)
        name_lbl.setObjectName("PriorityCardName")
        name_lbl.setWordWrap(True)
        # Expanding width, Minimum height so the wrapped name reserves its own
        # vertical space and never slides under the action buttons.
        name_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        top_row.addWidget(name_lbl, 1)

        # The action column (focus chip + menu) is fixed-width and top-aligned so
        # it stays pinned to the top-right as the name wraps to multiple lines.
        if summary.focus:
            chip = QLabel("★")
            chip.setObjectName("StateBadgeNew")
            chip.setAccessibleName("Focus deadline")
            top_row.addWidget(chip, 0, Qt.AlignmentFlag.AlignTop)

        menu_btn = QPushButton("…")
        menu_btn.setObjectName("PriorityCardMenu")
        menu_btn.setAccessibleName(f"Options for {summary.name}")
        # Fixed width keeps it compact; min height keeps it a comfortable target
        # (COG/touch) without clipping the glyph at large font scales.
        menu_btn.setFixedWidth(36)
        menu_btn.setMinimumHeight(28)
        menu_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        menu = QMenu(menu_btn)
        menu.addAction("Edit details", on_edit)
        menu.addAction("Manage skip days", on_vacations)
        menu.addSeparator()
        menu.addAction("Delete", on_delete)
        menu_btn.setMenu(menu)
        top_row.addWidget(menu_btn, 0, Qt.AlignmentFlag.AlignTop)

        layout.addLayout(top_row)

        meta = _priority_meta(summary, work_item)
        meta_lbl = QLabel(meta)
        meta_lbl.setObjectName("PriorityCardMeta")
        meta_lbl.setWordWrap(True)
        meta_lbl.setAccessibleName(meta)
        layout.addWidget(meta_lbl)

        if summary.deck_names:
            deck_text = "  ·  ".join(
                f"{icon}  {name}" if icon else name
                for icon, name in zip(summary.deck_icons, summary.deck_names)
            )
            decks_lbl = QLabel(deck_text)
            decks_lbl.setObjectName("PriorityCardDecks")
            decks_lbl.setWordWrap(True)
            layout.addWidget(decks_lbl)


class DeadlinePriorityPanel(QWidget):
    """Right-side compact deadline priority list."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DeadlinePriorityPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 24)
        self._layout.setSpacing(0)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._on_edit: Callable | None = None
        self._on_delete: Callable | None = None
        self._on_vacations: Callable | None = None

    def set_callbacks(
        self,
        on_edit: Callable,
        on_delete: Callable,
        on_vacations: Callable,
    ) -> None:
        self._on_edit = on_edit
        self._on_delete = on_delete
        self._on_vacations = on_vacations

    def refresh(
        self,
        all_summaries: list[DeadlineSummary],
        work_items: list[ForecastWorkItem],
    ) -> None:
        clear_layout(self._layout)

        title = QLabel("Priority")
        title.setObjectName("ForecastTitle")
        self._layout.addWidget(title)
        self._layout.addSpacing(14)

        work_map = {w.deadline_id: w for w in work_items}

        needs_work: list[DeadlineSummary] = []
        complete: list[DeadlineSummary] = []
        needs_setup: list[DeadlineSummary] = []
        upcoming: list[DeadlineSummary] = []
        past: list[DeadlineSummary] = []

        for s in all_summaries:
            if s.is_past:
                past.append(s)
            elif not s.deck_names:
                needs_setup.append(s)
            elif s.total_remaining == 0:
                complete.append(s)
            else:
                w = work_map.get(s.deadline_id)
                assigned = w.assigned_today if w else 0
                done = w.completed_today if w else 0
                if assigned > 0 and done < assigned:
                    needs_work.append(s)
                else:
                    upcoming.append(s)

        any_shown = False
        for group_label, summaries in (
            ("Needs work", needs_work),
            ("Complete", complete),
            ("Needs setup", needs_setup),
            ("Upcoming", upcoming),
            ("Past", past),
        ):
            if not summaries:
                continue
            any_shown = True
            grp = QLabel(group_label)
            grp.setObjectName("PriorityGroupLabel")
            self._layout.addWidget(grp)
            self._layout.addSpacing(6)
            for s in summaries:
                self._layout.addWidget(self._make_card(s, work_map.get(s.deadline_id)))
                self._layout.addSpacing(6)
            self._layout.addSpacing(10)

        if not any_shown:
            empty = QLabel("No deadlines yet.")
            empty.setObjectName("ForecastWorkTotal")
            self._layout.addWidget(empty)

        self._layout.addStretch(1)

    def _make_card(
        self,
        summary: DeadlineSummary,
        work: ForecastWorkItem | None,
    ) -> DeadlinePriorityCard:
        did = summary.deadline_id
        name = summary.name
        return DeadlinePriorityCard(
            summary=summary,
            work_item=work,
            on_edit=lambda _=False, d=did: self._on_edit(d) if self._on_edit else None,
            on_delete=lambda _=False, d=did, n=name: (
                self._on_delete(d, n) if self._on_delete else None
            ),
            on_vacations=lambda _=False, d=did, n=name: (
                self._on_vacations(d, n) if self._on_vacations else None
            ),
        )
