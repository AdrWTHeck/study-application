"""Dialogs for note flags: manage the flag set (Settings) and assign flags to a
note (notes browser)."""
from __future__ import annotations

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from domain.notes.flag_service import FlagService
from ui.utils.layouts import clear_layout


class FlagEditorDialog(QDialog):
    """Add / rename / recolor / delete the customizable note flags."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setWindowTitle("Note flags")
        self.setAccessibleName("Note flags editor")
        self.resize(460, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        intro = QLabel("Flags mark a card's status (e.g. Incomplete, Wrong). "
                       "Rename them, change colors, or add your own.")
        intro.setObjectName("SettingsHint")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        container = QWidget()
        self._list = QVBoxLayout(container)
        self._list.setSpacing(6)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        add_btn = QPushButton("Add flag")
        add_btn.setAccessibleName("Add flag")
        add_btn.clicked.connect(self._add)
        close_btn = QPushButton("Close")
        close_btn.setAccessibleName("Close flag editor")
        close_btn.clicked.connect(self.accept)
        footer = QHBoxLayout()
        footer.addWidget(add_btn)
        footer.addStretch(1)
        footer.addWidget(close_btn)
        layout.addLayout(footer)

        self._refresh()

    def _refresh(self) -> None:
        clear_layout(self._list)
        if self._context.db is None:
            return
        with self._context.db.session() as s:
            flags = [(f.id, f.name, f.color, f.is_builtin) for f in FlagService(s).list_flags()]
        for flag_id, name, color, is_builtin in flags:
            self._list.addWidget(self._row(flag_id, name, color, is_builtin))
        self._list.addStretch(1)

    def _row(self, flag_id: int, name: str, color: str, is_builtin: bool) -> QWidget:
        row = QWidget()
        row.setObjectName("DeckRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 8, 12, 8)
        swatch = QPushButton()
        swatch.setFixedSize(22, 22)
        swatch.setStyleSheet(f"background-color: {color}; border-radius: 4px;")
        swatch.setAccessibleName(f"{name} color")
        swatch.clicked.connect(lambda _=False, fid=flag_id, c=color: self._recolor(fid, c))
        name_label = QLabel(name)
        name_label.setObjectName("DeckName")
        rename = QPushButton("Rename")
        rename.setAccessibleName(f"Rename {name}")
        rename.clicked.connect(lambda _=False, fid=flag_id, n=name: self._rename(fid, n))
        layout.addWidget(swatch)
        layout.addWidget(name_label, 1)
        layout.addWidget(rename)
        if not is_builtin:
            delete = QPushButton("Delete")
            delete.setAccessibleName(f"Delete {name}")
            delete.clicked.connect(lambda _=False, fid=flag_id: self._delete(fid))
            layout.addWidget(delete)
        return row

    def _mutate(self, fn) -> None:
        """Run a flag mutation inside a guarded session, then refresh."""
        if self._context.db is None:
            return
        try:
            with self._context.db.session() as s:
                fn(s)
        except Exception:
            QMessageBox.warning(self, "Note flags", "Couldn't update the flag. Please try again.")
            return
        self._refresh()

    def _add(self) -> None:
        name, ok = QInputDialog.getText(self, "Add flag", "Flag name:")
        if not (ok and name.strip()):
            return
        color = QColorDialog.getColor(QColor("#868e96"), self, "Flag color")
        self._mutate(lambda s: FlagService(s).create_flag(
            name.strip(), color.name() if color.isValid() else "#868e96"))

    def _rename(self, flag_id: int, current: str) -> None:
        name, ok = QInputDialog.getText(self, "Rename flag", "New name:", text=current)
        if ok and name.strip():
            self._mutate(lambda s: FlagService(s).update_flag(flag_id, name=name.strip()))

    def _recolor(self, flag_id: int, current: str) -> None:
        color = QColorDialog.getColor(QColor(current), self, "Flag color")
        if color.isValid():
            self._mutate(lambda s: FlagService(s).update_flag(flag_id, color=color.name()))

    def _delete(self, flag_id: int) -> None:
        if QMessageBox.question(self, "Delete flag", "Delete this flag?") == QMessageBox.StandardButton.Yes:
            self._mutate(lambda s: FlagService(s).delete_flag(flag_id))


class FlagAssignDialog(QDialog):
    """Toggle which flags are applied to a single note."""

    def __init__(self, context: AppContext, note_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self._note_id = note_id
        self.setWindowTitle("Set flags")
        self.setAccessibleName("Set note flags")
        self.resize(360, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        self._checks: dict[int, QCheckBox] = {}

        assigned: set[int] = set()
        flags: list[tuple[int, str]] = []
        if context.db is not None:
            with context.db.session() as s:
                service = FlagService(s)
                assigned = {f.id for f in service.flags_for_note(note_id)}
                flags = [(f.id, f.name) for f in service.list_flags()]
        for flag_id, name in flags:
            check = QCheckBox(name)
            check.setChecked(flag_id in assigned)
            check.setAccessibleName(name)
            self._checks[flag_id] = check
            layout.addWidget(check)
        layout.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        chosen = [fid for fid, check in self._checks.items() if check.isChecked()]
        if self._context.db is None:
            return
        try:
            with self._context.db.session() as s:
                FlagService(s).set_note_flags(self._note_id, chosen)
        except Exception:
            QMessageBox.warning(self, "Set flags", "Couldn't save the flags. Please try again.")
            return
        self.accept()
