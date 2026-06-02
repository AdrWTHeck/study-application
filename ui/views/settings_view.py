"""Settings view — the live control surface for the whole token system.

Single-column and generously grouped (COG-01/COG-02). Every change writes
straight to :class:`Settings`, which the ThemeController observes, so theme,
font scale, density (mode), and spacing update instantly. Each control carries
an accessible name (SR-01).
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from core.settings import Settings
from domain.accessibility.tts_service import TTSService

_MODES = [("Accessibility-first (simpler, guided)", "accessibility"), ("Advanced (denser, more tools)", "advanced")]
_THEMES = [
    ("Dark", "dark"),
    ("Light", "light"),
    ("High contrast — dark", "hc_dark"),
    ("High contrast — light", "hc_light"),
]
_FONTS = ["Atkinson Hyperlegible", "OpenDyslexic", "Segoe UI", "Arial", "Verdana", "Helvetica"]


class SettingsView(QWidget):
    def __init__(self, settings: Settings, tts: TTSService | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._tts = tts
        self.setObjectName("Page")
        self.setAccessibleName("Settings page")

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        body = QWidget()
        body.setObjectName("Page")
        self._form = QVBoxLayout(body)
        self._form.setContentsMargins(40, 24, 40, 40)
        self._form.setSpacing(6)
        scroll.setWidget(body)

        self._build()
        self._form.addStretch(1)

    # -- sections -----------------------------------------------------------

    def _build(self) -> None:
        self._section("Mode & appearance")
        self.mode_combo = self._combo("Mode", _MODES, self._settings.get("mode"),
                                      lambda v: self._settings.set("mode", v),
                                      hint="Accessibility-first keeps screens simple and guided. "
                                           "Advanced unlocks denser layouts and power tools.")
        self.theme_combo = self._combo("Theme", _THEMES, self._settings.get("theme"),
                                       lambda v: self._settings.set("theme", v))

        self._section("Reading")
        self.scale_slider = self._slider("Text size", 100, 200, int(self._settings.get("font_scale") * 100),
                                         lambda v: self._settings.set("font_scale", v / 100),
                                         suffix="%", hint="Scales all text. Layouts reflow without clipping.")
        self.font_combo = self._font_combo()
        self.line_spin = self._dspin("Line height", 1.0, 2.5, 0.1, float(self._settings.get("line_height")),
                                     lambda v: self._settings.set("line_height", v))
        self.letter_spin = self._dspin("Letter spacing", 0.0, 4.0, 0.5, float(self._settings.get("letter_spacing")),
                                       lambda v: self._settings.set("letter_spacing", v), suffix=" px")
        self.word_spin = self._dspin("Word spacing", 0.0, 8.0, 0.5, float(self._settings.get("word_spacing")),
                                     lambda v: self._settings.set("word_spacing", v), suffix=" px")

        self._section("Speech")
        self.tts_content = self._check("Read study content aloud (TTS)",
                                       bool(self._settings.get("tts_content_enabled")),
                                       lambda v: self._settings.set("tts_content_enabled", v))
        self.tts_ui = self._check("Speak interface labels as I move focus",
                                  bool(self._settings.get("tts_ui_enabled")),
                                  lambda v: self._settings.set("tts_ui_enabled", v))
        self.rate_slider = self._slider("Speech rate", 80, 300, int(self._settings.get("tts_rate")),
                                        self._on_rate_changed, suffix=" wpm")
        self._add_test_voice_button()

        self._section("Study")
        self.fuzzy_slider = self._slider("Short-answer match tolerance", 50, 100,
                                         int(self._settings.get("short_answer_fuzzy_threshold")),
                                         lambda v: self._settings.set("short_answer_fuzzy_threshold", v),
                                         suffix="%", hint="How close a typed answer must be to count as correct.")

    # -- control builders ---------------------------------------------------

    def _section(self, title: str) -> None:
        label = QLabel(title)
        label.setObjectName("SettingsSection")
        self._form.addWidget(label)

    def _field_label(self, text: str, hint: str | None) -> None:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        self._form.addWidget(label)
        if hint:
            hint_label = QLabel(hint)
            hint_label.setObjectName("SettingsHint")
            hint_label.setWordWrap(True)
            self._form.addWidget(hint_label)

    def _combo(self, label, pairs, current, on_change, hint=None) -> QComboBox:
        self._field_label(label, hint)
        combo = QComboBox()
        combo.setAccessibleName(label)
        values = [v for _, v in pairs]
        for text, _ in pairs:
            combo.addItem(text)
        if current in values:
            combo.setCurrentIndex(values.index(current))
        combo.currentIndexChanged.connect(lambda i: on_change(values[i]))
        self._form.addWidget(combo)
        return combo

    def _font_combo(self) -> QComboBox:
        self._field_label("Font", "Dyslexia-friendly fonts are listed first. "
                                  "Missing fonts fall back to a system face.")
        combo = QComboBox()
        combo.setAccessibleName("Font")
        options = list(_FONTS)
        current = self._settings.get("font_family")
        if current not in options:
            options.insert(0, current)
        combo.addItems(options)
        combo.setCurrentIndex(options.index(current))
        combo.currentTextChanged.connect(lambda text: self._settings.set("font_family", text))
        self._form.addWidget(combo)
        return combo

    def _slider(self, label, lo, hi, value, on_change, suffix="", hint=None) -> QSlider:
        self._field_label(label, hint)
        row = QHBoxLayout()
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(lo)
        slider.setMaximum(hi)
        slider.setValue(value)
        slider.setAccessibleName(label)
        value_label = QLabel(f"{value}{suffix}")
        value_label.setMinimumWidth(64)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        def _handle(v: int) -> None:
            value_label.setText(f"{v}{suffix}")
            on_change(v)

        slider.valueChanged.connect(_handle)
        row.addWidget(slider, 1)
        row.addWidget(value_label)
        self._form.addLayout(row)
        return slider

    def _dspin(self, label, lo, hi, step, value, on_change, suffix="") -> QDoubleSpinBox:
        self._field_label(label, None)
        spin = QDoubleSpinBox()
        spin.setRange(lo, hi)
        spin.setSingleStep(step)
        spin.setValue(value)
        spin.setSuffix(suffix)
        spin.setAccessibleName(label)
        spin.valueChanged.connect(on_change)
        self._form.addWidget(spin)
        return spin

    def _check(self, label, value, on_change) -> QCheckBox:
        check = QCheckBox(label)
        check.setChecked(value)
        check.setAccessibleName(label)
        check.toggled.connect(on_change)
        self._form.addWidget(check)
        return check

    def _add_test_voice_button(self) -> None:
        button = QPushButton("Test voice")
        button.setAccessibleName("Test voice")
        button.clicked.connect(self._test_voice)
        self._form.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)

    # -- handlers -----------------------------------------------------------

    def _on_rate_changed(self, value: int) -> None:
        self._settings.set("tts_rate", value)
        if self._tts is not None:
            self._tts.set_rate(value)

    def _test_voice(self) -> None:
        if self._tts is not None:
            self._tts.speak("This is a sample of the current voice and speed.")
