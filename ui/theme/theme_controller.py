"""Bridges settings → tokens → the live Qt application.

Holds the active :class:`Tokens`, recomposes them whenever a relevant setting
changes, and re-applies the global font + stylesheet so theme, font scale,
density (mode), and dyslexia/spacing options update without a restart
(VIS-01, RDG-01/02, ONB-02). Emits :attr:`changed` so views can react to
density-dependent values (e.g. sidebar width).
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from core.settings import Settings
from ui.theme import tokens as tk
from ui.theme.fonts import resolve_family
from ui.theme.qss_builder import build_qss

# Mode (the user-facing dual-mode switch) drives density.
_MODE_DENSITY = {"accessibility": "comfortable", "advanced": "compact"}

# Settings that require recomposing tokens + re-applying styles.
_RELEVANT = frozenset({
    "mode", "theme", "font_scale", "font_family",
    "line_height", "letter_spacing", "word_spacing", "custom_colors",
})


class ThemeController(QObject):
    changed = pyqtSignal()

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings
        self._tokens = self._compose()
        self._unsubscribe = settings.subscribe(self._on_setting_changed)

    @property
    def tokens(self) -> tk.Tokens:
        return self._tokens

    def _compose(self) -> tk.Tokens:
        s = self._settings
        density = _MODE_DENSITY.get(s.get("mode"), "comfortable")
        return tk.build_tokens(
            theme=s.get("theme"),
            font_scale=float(s.get("font_scale")),
            font_family=s.get("font_family"),
            line_height=float(s.get("line_height")),
            letter_spacing=float(s.get("letter_spacing")),
            word_spacing=float(s.get("word_spacing")),
            density=density,
            custom_colors=s.get("custom_colors"),
        )

    def apply(self, app: QApplication) -> None:
        """Recompose tokens and push the font + stylesheet to *app*."""
        self._tokens = self._compose()
        t = self._tokens.typography

        font = QFont(resolve_family(t.family), t.size("body"))
        if t.letter_spacing:
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, t.letter_spacing)
        if t.word_spacing:
            font.setWordSpacing(t.word_spacing)
        app.setFont(font)
        app.setStyleSheet(build_qss(self._tokens))
        self.changed.emit()

    def _on_setting_changed(self, key: str, _value: object) -> None:
        if key in _RELEVANT:
            app = QApplication.instance()
            if app is not None:
                self.apply(app)
