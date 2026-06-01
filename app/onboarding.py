"""First-run accessibility onboarding (ONB-01).

Accessibility is configured *before* the app proper — surfaced at setup, not
buried in a menu. The flow is one task per step (COG-01). Choices write to
settings immediately, and because the ThemeController observes settings, the
dialog itself restyles live as the user picks a theme or text size — so they
see the effect before committing. Step 1 states the local/offline privacy
posture in plain language (PRV-01).
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from core.settings import Settings
from domain.accessibility.tts_service import TTSService

_THEMES = [
    ("Dark", "dark"),
    ("Light", "light"),
    ("High contrast — dark", "hc_dark"),
    ("High contrast — light", "hc_light"),
]


class OnboardingDialog(QDialog):
    def __init__(self, settings: Settings, tts: TTSService | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._tts = tts
        self.setWindowTitle("Welcome to StudyApp")
        self.setAccessibleName("First-run setup")
        self.setModal(True)
        self.resize(660, 580)

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 32, 36, 24)
        from PyQt6.QtWidgets import QStackedWidget

        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)
        self._steps = [
            self._welcome_step(),
            self._mode_step(),
            self._appearance_step(),
            self._speech_step(),
        ]
        for step in self._steps:
            self._stack.addWidget(step)

        footer = QHBoxLayout()
        self._step_label = QLabel()
        self._step_label.setObjectName("SettingsHint")
        self._back_btn = QPushButton("Back")
        self._back_btn.setAccessibleName("Back")
        self._back_btn.clicked.connect(self._back)
        self._next_btn = QPushButton("Next")
        self._next_btn.setAccessibleName("Next")
        self._next_btn.clicked.connect(self._next)
        footer.addWidget(self._step_label)
        footer.addStretch(1)
        footer.addWidget(self._back_btn)
        footer.addWidget(self._next_btn)
        root.addLayout(footer)

        self._go(0)

    # -- step scaffolding ---------------------------------------------------

    def _page(self, title: str, intro: str | None = None) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        heading = QLabel(title)
        heading.setObjectName("SettingsSection")
        layout.addWidget(heading)
        if intro:
            text = QLabel(intro)
            text.setObjectName("SettingsHint")
            text.setWordWrap(True)
            layout.addWidget(text)
        return page, layout

    def _welcome_step(self) -> QWidget:
        page, layout = self._page(
            "Welcome",
            "StudyApp is built accessibility-first: clear, calm screens that you can "
            "tune to how you read and study.",
        )
        privacy = QLabel(
            "Your privacy: everything stays on this device. There is no account, no "
            "cloud, and no tracking — your notes, cards, and study history never leave "
            "your computer."
        )
        privacy.setObjectName("FieldLabel")
        privacy.setWordWrap(True)
        layout.addSpacing(12)
        layout.addWidget(privacy)
        layout.addStretch(1)
        return page

    def _mode_step(self) -> QWidget:
        page, layout = self._page(
            "Choose your starting experience",
            "You can switch anytime in Settings.",
        )
        self.mode_accessibility = QRadioButton(
            "Accessibility-first — simpler screens, one task at a time, larger targets"
        )
        self.mode_advanced = QRadioButton(
            "Advanced — denser layouts and more tools at once"
        )
        for radio in (self.mode_accessibility, self.mode_advanced):
            radio.setAccessibleName(radio.text())
        self.mode_accessibility.setChecked(self._settings.get("mode") == "accessibility")
        self.mode_advanced.setChecked(self._settings.get("mode") == "advanced")
        self.mode_accessibility.toggled.connect(
            lambda on: self._settings.set("mode", "accessibility") if on else None
        )
        self.mode_advanced.toggled.connect(
            lambda on: self._settings.set("mode", "advanced") if on else None
        )
        layout.addWidget(self.mode_accessibility)
        layout.addWidget(self.mode_advanced)
        layout.addStretch(1)
        return page

    def _appearance_step(self) -> QWidget:
        page, layout = self._page(
            "Make it comfortable to read",
            "Pick a theme and text size. Try a high-contrast theme if you need it.",
        )
        layout.addWidget(self._label("Theme"))
        self.theme_combo = QComboBox()
        self.theme_combo.setAccessibleName("Theme")
        values = [v for _, v in _THEMES]
        self.theme_combo.addItems([t for t, _ in _THEMES])
        current = self._settings.get("theme")
        if current in values:
            self.theme_combo.setCurrentIndex(values.index(current))
        self.theme_combo.currentIndexChanged.connect(
            lambda i: self._settings.set("theme", values[i])
        )
        layout.addWidget(self.theme_combo)

        layout.addWidget(self._label("Text size"))
        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setMinimum(100)
        self.scale_slider.setMaximum(200)
        self.scale_slider.setValue(int(self._settings.get("font_scale") * 100))
        self.scale_slider.setAccessibleName("Text size")
        self.scale_slider.valueChanged.connect(
            lambda v: self._settings.set("font_scale", v / 100)
        )
        layout.addWidget(self.scale_slider)
        layout.addStretch(1)
        return page

    def _speech_step(self) -> QWidget:
        page, layout = self._page(
            "Speech (optional)",
            "StudyApp can read content and interface labels aloud.",
        )
        self.tts_content = QCheckBox("Read study content aloud")
        self.tts_content.setChecked(bool(self._settings.get("tts_content_enabled")))
        self.tts_content.setAccessibleName(self.tts_content.text())
        self.tts_content.toggled.connect(
            lambda v: self._settings.set("tts_content_enabled", v)
        )
        self.tts_ui = QCheckBox("Speak interface labels as I move focus")
        self.tts_ui.setChecked(bool(self._settings.get("tts_ui_enabled")))
        self.tts_ui.setAccessibleName(self.tts_ui.text())
        self.tts_ui.toggled.connect(lambda v: self._settings.set("tts_ui_enabled", v))
        test = QPushButton("Test voice")
        test.setAccessibleName("Test voice")
        test.clicked.connect(self._test_voice)
        layout.addWidget(self.tts_content)
        layout.addWidget(self.tts_ui)
        layout.addWidget(test, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        return page

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        return label

    # -- navigation ---------------------------------------------------------

    def _go(self, index: int) -> None:
        index = max(0, min(index, len(self._steps) - 1))
        self._stack.setCurrentIndex(index)
        self._step_label.setText(f"Step {index + 1} of {len(self._steps)}")
        self._back_btn.setEnabled(index > 0)
        self._next_btn.setText("Finish" if index == len(self._steps) - 1 else "Next")

    def _back(self) -> None:
        self._go(self._stack.currentIndex() - 1)

    def _next(self) -> None:
        index = self._stack.currentIndex()
        if index == len(self._steps) - 1:
            self._finish()
        else:
            self._go(index + 1)

    def _finish(self) -> None:
        self._settings.set("onboarding_complete", True)
        self.accept()

    def _test_voice(self) -> None:
        if self._tts is not None:
            self._tts.speak("This is a sample of the current voice.")
