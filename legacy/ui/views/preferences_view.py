"""PreferencesView — font size, colour scheme, TTS settings."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from config.constants import FONT_SIZE_DEFAULT, FONT_SIZE_MAX, FONT_SIZE_MIN, FONT_SIZE_STEP
from services.core.app_settings import AppSettings
from services.accessibility.tts_service import TTSService


class PreferencesView(QWidget):
    """Settings panel wired to AppSettings.

    Changes are applied immediately via AppSettings.set(), which notifies
    StyleManager and any other observers.
    """

    def __init__(self, tts: TTSService, parent=None) -> None:
        super().__init__(parent)
        self._settings = AppSettings.get_instance()
        self._tts = tts
        self._build_ui()
        self._load()
        self._settings.register(self._on_settings_changed)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- Appearance -------------------------------------------------
        appearance = QGroupBox("Appearance")
        form = QFormLayout(appearance)

        self._font_slider = QSlider(Qt.Orientation.Horizontal)
        self._font_slider.setRange(FONT_SIZE_MIN, FONT_SIZE_MAX)
        self._font_slider.setSingleStep(FONT_SIZE_STEP)
        self._font_slider.setTickInterval(FONT_SIZE_STEP)
        self._font_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._font_label = QLabel(f"{FONT_SIZE_DEFAULT}pt")
        self._font_label.setFixedWidth(36)
        font_row = QHBoxLayout()
        font_row.addWidget(self._font_slider)
        font_row.addWidget(self._font_label)
        form.addRow("Font size:", font_row)
        self._font_slider.valueChanged.connect(self._on_font_changed)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["Default", "High Contrast Dark", "High Contrast Light"])
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        form.addRow("Colour scheme:", self._theme_combo)

        root.addWidget(appearance)

        # --- Text-to-Speech ---------------------------------------------
        tts_group = QGroupBox("Text-to-Speech")
        tts_form = QFormLayout(tts_group)

        self._rate_spin = QSpinBox()
        self._rate_spin.setRange(50, 400)
        self._rate_spin.setSingleStep(10)
        self._rate_spin.setSuffix(" wpm")
        self._rate_spin.valueChanged.connect(self._on_rate_changed)
        tts_form.addRow("Speech rate:", self._rate_spin)

        self._voice_combo = QComboBox()
        self._populate_voices()
        self._voice_combo.currentIndexChanged.connect(self._on_voice_changed)
        tts_form.addRow("Voice:", self._voice_combo)

        root.addWidget(tts_group)

        # --- Dictionary -------------------------------------------------
        dict_group = QGroupBox("Dictionary")
        dict_form = QFormLayout(dict_group)
        shortcut_label = QLabel(self._settings.dictionary_shortcut)
        shortcut_label.setToolTip("Change in settings.json to customise.")
        dict_form.addRow("Open shortcut:", shortcut_label)
        root.addWidget(dict_group)

    def _populate_voices(self) -> None:
        self._voice_combo.clear()
        self._voice_ids: list[str | None] = [None]
        self._voice_combo.addItem("System default")
        for v in self._tts.get_available_voices():
            self._voice_combo.addItem(v["name"])
            self._voice_ids.append(v["id"])

    # ------------------------------------------------------------------
    # Load / sync
    # ------------------------------------------------------------------

    def _load(self) -> None:
        s = self._settings
        self._font_slider.blockSignals(True)
        self._font_slider.setValue(s.font_size)
        self._font_label.setText(f"{s.font_size}pt")
        self._font_slider.blockSignals(False)

        _THEME_INDEX = {"default": 0, "high_contrast_dark": 1, "high_contrast_light": 2}
        self._theme_combo.blockSignals(True)
        self._theme_combo.setCurrentIndex(_THEME_INDEX.get(s.theme, 0))
        self._theme_combo.blockSignals(False)

        self._rate_spin.blockSignals(True)
        self._rate_spin.setValue(s.tts_rate)
        self._rate_spin.blockSignals(False)

    def _on_settings_changed(self, s: AppSettings) -> None:
        self._load()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    _THEME_KEYS = ["default", "high_contrast_dark", "high_contrast_light"]

    def _on_font_changed(self, value: int) -> None:
        self._font_label.setText(f"{value}pt")
        self._settings.set(font_size=value)

    def _on_theme_changed(self, idx: int) -> None:
        if 0 <= idx < len(self._THEME_KEYS):
            self._settings.set(theme=self._THEME_KEYS[idx])

    def _on_rate_changed(self, value: int) -> None:
        self._settings.set(tts_rate=value)
        self._tts.set_rate(value)

    def _on_voice_changed(self, idx: int) -> None:
        if 0 <= idx < len(self._voice_ids):
            vid = self._voice_ids[idx]
            self._settings.set(tts_voice_id=vid)
            if vid:
                self._tts.set_voice(vid)
