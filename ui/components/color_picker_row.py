"""A compact palette-key override row: label · round swatch · hex input · Reset.

Writes directly to ``settings["custom_colors"][key]`` on every valid change so
the ThemeController observer fires and the live QSS updates instantly.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from core.settings import Settings
from ui.theme.tokens import PALETTES


class _CircularSwatch(QPushButton):
    """26 × 26 px round button showing a solid color; opens QColorDialog on click."""

    def __init__(self, hex_color: str = "#888888", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(26, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hex = hex_color
        self._paint()

    def set_hex(self, hex_color: str) -> None:
        if self._hex != hex_color:
            self._hex = hex_color
            self._paint()

    def hex_color(self) -> str:
        return self._hex

    def _paint(self) -> None:
        self.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {self._hex};"
            f"  border-radius: 13px;"
            f"  border: 1px solid rgba(128,128,128,0.4);"
            f"}}"
            f"QPushButton:hover {{"
            f"  border: 2px solid rgba(128,128,128,0.8);"
            f"}}"
        )


class ColorPickerRow(QWidget):
    """One palette-key override control.

    Shows the palette default when no override is active; shows the override
    when one is set.  Call :meth:`refresh` after an external settings change
    (e.g. the user switched to a different base theme).

    Signals
    -------
    changed(key, hex)  — emitted when a new color is applied
    cleared(key)       — emitted when the override is removed
    """

    changed = pyqtSignal(str, str)
    cleared = pyqtSignal(str)

    def __init__(
        self,
        label: str,
        key: str,
        settings: Settings,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._key = key
        self._settings = settings

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 3, 0, 3)
        row.setSpacing(10)

        lbl = QLabel(label)
        lbl.setObjectName("SettingsHint")
        lbl.setFixedWidth(160)
        row.addWidget(lbl)

        self._swatch = _CircularSwatch()
        self._swatch.setAccessibleName(f"Pick color for {label}")
        self._swatch.clicked.connect(self._open_dialog)
        row.addWidget(self._swatch)

        self._hex_input = QLineEdit()
        self._hex_input.setFixedWidth(88)
        self._hex_input.setPlaceholderText("default")
        self._hex_input.setAccessibleName(f"{label} hex value")
        self._hex_input.textEdited.connect(self._on_hex_edited)
        row.addWidget(self._hex_input)

        reset_btn = QPushButton("Reset")
        reset_btn.setFixedWidth(58)
        reset_btn.setAccessibleName(f"Reset {label} to theme default")
        reset_btn.clicked.connect(self._clear)
        row.addWidget(reset_btn)

        row.addStretch(1)
        self.refresh()

    # -- helpers -------------------------------------------------------------

    def _base_color(self) -> str:
        theme = self._settings.get("theme")
        pal = PALETTES.get(theme, PALETTES["dark"])
        return getattr(pal, self._key, "#888888")

    def _current_override(self) -> str | None:
        return (self._settings.get("custom_colors") or {}).get(self._key)

    # -- public --------------------------------------------------------------

    def refresh(self) -> None:
        """Re-read settings; update swatch + hex input without triggering signals."""
        override = self._current_override()
        self._swatch.set_hex(override or self._base_color())
        blocked = self._hex_input.blockSignals(True)
        self._hex_input.setText(override or "")
        self._hex_input.blockSignals(blocked)

    # -- private slots -------------------------------------------------------

    def _open_dialog(self) -> None:
        initial = QColor(self._swatch.hex_color())
        color = QColorDialog.getColor(initial, self, f"Choose color — {self._key}")
        if color.isValid():
            self._write(color.name())

    def _on_hex_edited(self, text: str) -> None:
        if QColor(text).isValid():
            self._write(text)

    def _write(self, hex_color: str) -> None:
        overrides = dict(self._settings.get("custom_colors") or {})
        overrides[self._key] = hex_color
        self._settings.set("custom_colors", overrides)
        self._swatch.set_hex(hex_color)
        self.changed.emit(self._key, hex_color)

    def _clear(self) -> None:
        overrides = dict(self._settings.get("custom_colors") or {})
        overrides.pop(self._key, None)
        self._settings.set("custom_colors", overrides)
        self.cleared.emit(self._key)
        self.refresh()
