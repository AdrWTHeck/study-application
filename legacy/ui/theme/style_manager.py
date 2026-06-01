"""Stylesheet generation from AppSettings — registered as an observer."""
from __future__ import annotations

from config.constants import FONT_SIZE_MAX, FONT_SIZE_MIN

# ---------------------------------------------------------------------------
# Colour palettes
# ---------------------------------------------------------------------------

_LIGHT = {
    "window": "#F5F5F5", "text": "#1A1A1A",
    "button": "#E8E8E8", "button_text": "#1A1A1A",
    "selection": "#0078D7", "selection_text": "#FFFFFF",
    "border": "#CCCCCC", "alt": "#EBEBEB",
    "input": "#FFFFFF", "disabled": "#AAAAAA",
}
_HC_DARK = {
    "window": "#000000", "text": "#FFFFFF",
    "button": "#1A1A1A", "button_text": "#FFFFFF",
    "selection": "#FFFF00", "selection_text": "#000000",
    "border": "#FFFFFF", "alt": "#111111",
    "input": "#000000", "disabled": "#555555",
}
_HC_LIGHT = {
    "window": "#FFFFFF", "text": "#000000",
    "button": "#FFFFFF", "button_text": "#000000",
    "selection": "#000080", "selection_text": "#FFFFFF",
    "border": "#000000", "alt": "#EEEEEE",
    "input": "#FFFFFF", "disabled": "#666666",
}

_PALETTES = {
    "default": _LIGHT,
    "high_contrast_dark": _HC_DARK,
    "high_contrast_light": _HC_LIGHT,
}


def _sheet(font_size: int, p: dict) -> str:
    fs = max(FONT_SIZE_MIN, min(FONT_SIZE_MAX, font_size))
    return f"""
* {{ font-size: {fs}pt; color: {p['text']}; }}
QMainWindow, QDialog, QWidget {{ background-color: {p['window']}; }}
QPushButton {{
    background-color: {p['button']}; color: {p['button_text']};
    border: 1px solid {p['border']}; border-radius: 4px;
    padding: 4px 12px; min-height: 26px;
}}
QPushButton:hover {{ background-color: {p['selection']}; color: {p['selection_text']}; }}
QPushButton:disabled {{ color: {p['disabled']}; border-color: {p['disabled']}; }}
QPushButton#veryHardBtn {{ background-color: #C62828; color: #FFFFFF; border-color: #B71C1C; }}
QPushButton#hardBtn   {{ background-color: #EF6C00; color: #FFFFFF; border-color: #E65100; }}
QPushButton#goodBtn   {{ background-color: #2E7D32; color: #FFFFFF; border-color: #1B5E20; }}
QPushButton#easyBtn   {{ background-color: #1565C0; color: #FFFFFF; border-color: #0D47A1; }}
QPushButton#veryHardBtn:hover, QPushButton#hardBtn:hover,
QPushButton#goodBtn:hover, QPushButton#easyBtn:hover {{ opacity: 0.85; }}
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {{
    background-color: {p['input']}; color: {p['text']};
    border: 1px solid {p['border']}; border-radius: 3px; padding: 2px 4px;
}}
QListWidget, QTableWidget {{
    background-color: {p['input']}; color: {p['text']};
    alternate-background-color: {p['alt']}; border: 1px solid {p['border']};
}}
QListWidget::item:selected, QTableWidget::item:selected {{
    background-color: {p['selection']}; color: {p['selection_text']};
}}
QLabel {{ background-color: transparent; }}
QTabBar::tab {{
    background: {p['button']}; color: {p['button_text']};
    padding: 6px 16px; border: 1px solid {p['border']};
}}
QTabBar::tab:selected {{ background: {p['selection']}; color: {p['selection_text']}; }}
QProgressBar {{
    border: 1px solid {p['border']}; text-align: center; color: {p['text']};
}}
QProgressBar::chunk {{ background-color: {p['selection']}; }}
QScrollBar:vertical {{ width: 14px; background: {p['alt']}; }}
QScrollBar::handle:vertical {{
    background: {p['border']}; min-height: 20px; border-radius: 4px;
}}
QSplitter::handle {{ background: {p['border']}; }}
QMenuBar {{ background-color: {p['button']}; color: {p['button_text']}; }}
QMenuBar::item:selected {{ background-color: {p['selection']}; color: {p['selection_text']}; }}
QMenu {{ background-color: {p['window']}; color: {p['text']}; border: 1px solid {p['border']}; }}
QMenu::item:selected {{ background-color: {p['selection']}; color: {p['selection_text']}; }}
QDockWidget::title {{ background: {p['button']}; padding: 4px; }}
"""


class StyleManager:
    """Generates and applies Qt stylesheets from AppSettings.

    Call set_app(QApplication) once, then register apply() as an
    AppSettings observer.
    """

    def __init__(self) -> None:
        self._app = None

    def set_app(self, app) -> None:
        self._app = app

    def apply(self, settings) -> None:
        if self._app is None:
            return
        palette = _PALETTES.get(settings.theme, _LIGHT)
        self._app.setStyleSheet(_sheet(settings.font_size, palette))
