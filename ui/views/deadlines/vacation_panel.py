"""Skip-day range manager panel."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from data.models.deadline import Deadline
from domain.deadlines.deadline_service import DeadlineService
from ui.views.deadlines.deadline_wizard import VacationDialog


class VacationPanel(QWidget):
    """Skip-day range manager — shown as a stacked page over the deadline list."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._deadline_id: int | None = None
        self._context: AppContext | None = None
        self._on_back = None
        self.setAccessibleDescription(
            "Manage vacation or skip-day ranges for this deadline."
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        header = QHBoxLayout()
        back = QPushButton("← Back")
        back.setAccessibleName("Back to deadlines list")
        back.clicked.connect(self._go_back)
        header.addWidget(back)

        self._title = QLabel("Skip days")
        self._title.setObjectName("PageTitle")
        header.addWidget(self._title, 1)
        layout.addLayout(header)

        self._empty_lbl = QLabel(
            "No skip days set yet.\n"
            "Add a range to exclude those days from your daily target."
        )
        self._empty_lbl.setObjectName("SettingsHint")
        self._empty_lbl.setWordWrap(True)
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_lbl)

        self._list = QListWidget()
        self._list.setAccessibleName("Skip day ranges")
        layout.addWidget(self._list, 1)

        add_btn = QPushButton("+ Add skip days")
        add_btn.setAccessibleName("Add vacation or skip-day range")
        add_btn.clicked.connect(self._add_vacation)
        layout.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        del_btn = QPushButton("Remove selected")
        del_btn.setAccessibleName("Remove selected skip day range")
        del_btn.clicked.connect(self._remove_vacation)
        layout.addWidget(del_btn, alignment=Qt.AlignmentFlag.AlignLeft)

    def load(
        self,
        context: AppContext,
        deadline_id: int,
        deadline_name: str,
        on_back,
    ) -> None:
        self._context = context
        self._deadline_id = deadline_id
        self._on_back = on_back
        self._title.setText(f"Skip days — {deadline_name}")
        self._refresh()

    def _refresh(self) -> None:
        self._list.clear()
        if self._context is None or self._deadline_id is None:
            self._list.setVisible(False)
            self._empty_lbl.setVisible(True)
            return

        with self._context.db.session() as session:
            vacations = DeadlineService(session).list_vacations(self._deadline_id)
            vacation_data = [(v.id, v.start_date, v.end_date, v.note) for v in vacations]

        empty = len(vacation_data) == 0
        self._list.setVisible(not empty)
        self._empty_lbl.setVisible(empty)

        for index, (vid, start, end, note) in enumerate(vacation_data, start=1):
            sl = f"{start.strftime('%a, %b')} {start.day}, {start.year}"
            el = f"{end.strftime('%a, %b')} {end.day}, {end.year}"
            label = f"{sl}  →  {el}"
            if note:
                label += f"   ({note})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, vid)
            desc = f"Skip day range {index} of {len(vacation_data)}: from {start} to {end}"
            if note:
                desc += f", label: {note}"
            item.setToolTip(desc)
            self._list.addItem(item)

    def _add_vacation(self) -> None:
        if self._context is None or self._deadline_id is None:
            return
        with self._context.db.session() as session:
            dl = session.get(Deadline, self._deadline_id)
            if dl is None:
                return
            deadline_name = dl.name

        dialog = VacationDialog(deadline_name, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        with self._context.db.session() as session:
            DeadlineService(session).add_vacation(
                self._deadline_id, dialog.start_date(), dialog.end_date(), dialog.note()
            )
        self._refresh()

    def _remove_vacation(self) -> None:
        item = self._list.currentItem()
        if item is None or self._context is None:
            return
        vid = item.data(Qt.ItemDataRole.UserRole)
        with self._context.db.session() as session:
            DeadlineService(session).remove_vacation(vid)
        self._refresh()

    def _go_back(self) -> None:
        if self._on_back:
            self._on_back()
