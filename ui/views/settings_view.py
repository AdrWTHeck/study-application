"""Settings view — the live control surface for the whole token system.

Single-column, generously grouped (COG-01/COG-02). Every change writes
straight to :class:`Settings`, which the ThemeController observes, so theme,
font scale, density (mode), and spacing update instantly. Each control carries
an accessible name (SR-01).

Theme & Colors section
──────────────────────
Four clickable ThemeCards replace the old combo + button row.  Selecting a
card updates ``settings["theme"]``, which flows through ThemeController →
build_qss → live QSS swap.  The eight ColorPickerRow controls below write to
``settings["custom_colors"]``, which build_tokens() merges via dataclass
replace() — also live.  Import/export persist a custom palette as plain JSON
so it can be shared or restored.
"""
from __future__ import annotations

import json
from dataclasses import replace

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
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
from ui.components.color_picker_row import ColorPickerRow
from ui.theme.tokens import PALETTES

_MODES = [
    ("Accessibility-first (simpler, guided)", "accessibility"),
    ("Advanced (denser, more tools)", "advanced"),
]
_FONTS = ["IBM Plex Sans", "Atkinson Hyperlegible", "OpenDyslexic", "Segoe UI", "Arial", "Verdana", "Helvetica"]

# Palette keys exposed in the color-override section, in display order.
_COLOR_OVERRIDES: list[tuple[str, str]] = [
    ("accent",        "Accent"),
    ("bg_base",       "Page background"),
    ("bg_surface",    "Surface / cards"),
    ("text_primary",  "Body text"),
    ("border",        "Borders"),
    ("success",       "Success"),
    ("warning",       "Warning"),
    ("danger",        "Danger"),
]


# ---------------------------------------------------------------------------
# ThemeCard — one card in the 2 × 2 palette picker grid
# ---------------------------------------------------------------------------

class _ThemeCard(QFrame):
    """Clickable card showing a palette's name and five color swatches.

    Uses inline styles driven by the palette it represents so it always looks
    correct regardless of the currently active app theme.
    """

    clicked = pyqtSignal(str)   # emits the palette key, e.g. "hc_dark"

    _PREVIEW_KEYS = ("bg_surface", "bg_raised", "accent", "text_primary", "border")

    def __init__(self, palette_key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._key = palette_key
        self._pal = PALETTES[palette_key]
        self._selected = False

        self.setObjectName("ThemeCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(130)
        self.setFixedHeight(84)

        display = palette_key.replace("hc_", "HC ").replace("_", " ").title()
        self.setAccessibleName(f"{display} theme")
        if self._pal.is_high_contrast:
            self.setAccessibleDescription("High contrast theme — designed for visual accessibility")

        self._build()
        self._apply_frame_style()

    # -- layout --------------------------------------------------------------

    def _build(self) -> None:
        pal = self._pal
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)

        # Swatch row
        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(4)
        for key in self._PREVIEW_KEYS:
            color = getattr(pal, key)
            dot = QLabel()
            dot.setFixedSize(14, 14)
            dot.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            dot.setStyleSheet(
                f"background: {color}; border-radius: 7px;"
                f" border: 1px solid rgba(128,128,128,0.25); background-color: {color};"
            )
            swatch_row.addWidget(dot)
        swatch_row.addStretch(1)
        layout.addLayout(swatch_row)

        # Name label
        display = self._key.replace("hc_", "HC ").replace("_", " ").title()
        name_lbl = QLabel(display)
        name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        name_lbl.setStyleSheet(
            f"color: {pal.text_primary}; font-weight: 600;"
            f" font-size: 11px; background: transparent; border: none;"
        )
        layout.addWidget(name_lbl)

        # High-contrast badge
        if pal.is_high_contrast:
            badge = QLabel("♿ High contrast")
            badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            badge.setStyleSheet(
                f"color: {pal.text_secondary}; font-size: 9px;"
                f" background: transparent; border: none;"
            )
            layout.addWidget(badge)

    # -- state ---------------------------------------------------------------

    def set_selected(self, selected: bool) -> None:
        if self._selected == selected:
            return
        self._selected = selected
        self._apply_frame_style()

    def _apply_frame_style(self) -> None:
        pal = self._pal
        border = (
            f"2px solid {pal.accent}"
            if self._selected
            else f"1px solid {pal.border}"
        )
        self.setStyleSheet(
            f"QFrame#ThemeCard {{"
            f"  background-color: {pal.bg_surface};"
            f"  border-radius: 8px;"
            f"  border: {border};"
            f"}}"
        )

    # -- interaction ---------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._key)
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Settings view
# ---------------------------------------------------------------------------

class SettingsView(QWidget):
    def __init__(
        self,
        settings: Settings,
        tts: TTSService | None = None,
        context=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._tts = tts
        self._context = context
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

        self._theme_cards: list[tuple[str, _ThemeCard]] = []
        self._color_rows: list[ColorPickerRow] = []
        self._build()
        self._form.addStretch(1)

    # -- sections -----------------------------------------------------------

    def _build(self) -> None:
        # ── Mode ───────────────────────────────────────────────────────────
        self._section("Mode")
        self.mode_combo = self._combo(
            "Mode", _MODES, self._settings.get("mode"),
            lambda v: self._settings.set("mode", v),
            hint="Accessibility-first keeps screens simple and guided. "
                 "Advanced unlocks denser layouts and power tools.",
        )

        # ── Theme & Colors ─────────────────────────────────────────────────
        self._section("Theme & Colors")
        self._hint(
            "Select a base palette. High-contrast options (♿) meet WCAG AA "
            "contrast — recommended for visual accessibility."
        )
        self._form.addWidget(self._build_theme_grid())

        # Mini live preview (surface · accent · text on surface)
        preview_row = QHBoxLayout()
        self._swatch_surface = QLabel(" ")
        self._swatch_surface.setFixedSize(48, 32)
        self._swatch_surface.setObjectName("PaletteSwatch")
        self._swatch_accent = QLabel(" ")
        self._swatch_accent.setFixedSize(48, 32)
        self._swatch_accent.setObjectName("PaletteSwatch")
        self._swatch_overlay = QLabel("Aa")
        self._swatch_overlay.setFixedSize(48, 32)
        self._swatch_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._swatch_overlay.setObjectName("PaletteSwatch")
        preview_row.addWidget(self._swatch_surface)
        preview_row.addWidget(self._swatch_accent)
        preview_row.addWidget(self._swatch_overlay)
        preview_row.addStretch(1)
        self._form.addLayout(preview_row)

        # ── Color overrides ────────────────────────────────────────────────
        self._section("Color overrides")
        self._hint(
            "Override individual palette colors. Changes apply instantly. "
            "Leave blank to use the selected theme's default."
        )
        for key, label in _COLOR_OVERRIDES:
            row = ColorPickerRow(label, key, self._settings, parent=self)
            self._color_rows.append(row)
            self._form.addWidget(row)

        # Action buttons
        btn_row = QHBoxLayout()
        reset_btn = QPushButton("Reset all overrides")
        reset_btn.setAccessibleName("Reset all color overrides to theme defaults")
        reset_btn.clicked.connect(self._reset_overrides)
        btn_row.addWidget(reset_btn)

        export_btn = QPushButton("Export palette…")
        export_btn.setAccessibleName("Export current color overrides to a JSON file")
        export_btn.clicked.connect(self._export_palette)
        btn_row.addWidget(export_btn)

        import_btn = QPushButton("Import palette…")
        import_btn.setAccessibleName("Import color overrides from a JSON file")
        import_btn.clicked.connect(self._import_palette)
        btn_row.addWidget(import_btn)

        btn_row.addStretch(1)
        self._form.addLayout(btn_row)

        # Wire preview refresh
        self._settings.subscribe(self._on_setting_changed)
        self._update_palette_preview()

        # ── Reading ────────────────────────────────────────────────────────
        self._section("Reading")
        self.scale_slider = self._slider(
            "Text size", 100, 200, int(self._settings.get("font_scale") * 100),
            lambda v: self._settings.set("font_scale", v / 100),
            suffix="%", hint="Scales all text. Layouts reflow without clipping.",
        )
        self.font_combo = self._font_combo()
        self.line_spin = self._dspin(
            "Line height", 1.0, 2.5, 0.1, float(self._settings.get("line_height")),
            lambda v: self._settings.set("line_height", v),
        )
        self.letter_spin = self._dspin(
            "Letter spacing", 0.0, 4.0, 0.5, float(self._settings.get("letter_spacing")),
            lambda v: self._settings.set("letter_spacing", v), suffix=" px",
        )
        self.word_spin = self._dspin(
            "Word spacing", 0.0, 8.0, 0.5, float(self._settings.get("word_spacing")),
            lambda v: self._settings.set("word_spacing", v), suffix=" px",
        )

        # ── Speech ─────────────────────────────────────────────────────────
        self._section("Speech")
        self.tts_content = self._check(
            "Read study content aloud (TTS)",
            bool(self._settings.get("tts_content_enabled")),
            lambda v: self._settings.set("tts_content_enabled", v),
        )
        self.tts_ui = self._check(
            "Speak interface labels as I move focus",
            bool(self._settings.get("tts_ui_enabled")),
            lambda v: self._settings.set("tts_ui_enabled", v),
        )
        self.rate_slider = self._slider(
            "Speech rate", 80, 300, int(self._settings.get("tts_rate")),
            self._on_rate_changed, suffix=" wpm",
        )
        self._add_test_voice_button()

        # ── Study ──────────────────────────────────────────────────────────
        self._section("Study")
        self.new_cards_slider = self._slider(
            "New cards per study session", 0, 100,
            int(self._settings.get("new_cards_per_session")),
            lambda v: self._settings.set("new_cards_per_session", v),
            suffix=" cards",
            hint="How many brand-new cards a review session introduces at most.",
        )
        self.fuzzy_slider = self._slider(
            "Short-answer match tolerance", 50, 100,
            int(self._settings.get("short_answer_fuzzy_threshold")),
            lambda v: self._settings.set("short_answer_fuzzy_threshold", v),
            suffix="%", hint="How close a typed answer must be to count as correct.",
        )
        self.related_check = self._check(
            "Suggest related cards to review after a test",
            bool(self._settings.get("related_cards_enabled")),
            lambda v: self._settings.set("related_cards_enabled", v),
        )
        related_hint = QLabel(
            "After a test, point out cards that share material with questions you "
            "missed. Bringing them forward in your reviews always stays your choice."
        )
        related_hint.setObjectName("SettingsHint")
        related_hint.setWordWrap(True)
        self._form.addWidget(related_hint)

        if self._context is not None and self._context.db is not None:
            self._hint(
                "Search stays up to date automatically. If results ever look "
                "wrong or out of date, you can rebuild the search index."
            )
            repair_btn = QPushButton("Repair search index")
            repair_btn.setAccessibleName("Repair search index")
            repair_btn.clicked.connect(self._repair_search_index)
            self._form.addWidget(repair_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # ── Note flags ─────────────────────────────────────────────────────
        if self._context is not None and self._context.db is not None:
            self._section("Note flags")
            self._hint("Customize the colored status flags you can apply to cards.")
            flags_btn = QPushButton("Manage note flags…")
            flags_btn.setAccessibleName("Manage note flags")
            flags_btn.clicked.connect(self._open_flag_editor)
            self._form.addWidget(flags_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # ── Pomodoro companion ──────────────────────────────────────────────
        self._section("Pomodoro companion")
        self._hint(
            "The study companion lives on the Dashboard. It tracks your focus "
            "sessions, asks how confident you feel about your cards, and grows "
            "as you study consistently."
        )
        self._check(
            "Show companion on Dashboard",
            bool(self._settings.get("companion_enabled")),
            lambda v: self._settings.set("companion_enabled", v),
        )
        self._combo(
            "Companion type",
            [("Tree 🌱", "tree"), ("Pet 🥚", "pet")],
            self._settings.get("companion_kind") or "tree",
            lambda v: self._settings.set("companion_kind", v),
            hint="Your companion grows with consistency.",
        )
        self._slider(
            "Focus block length (minutes)", 5, 60,
            int(self._settings.get("pomodoro_focus_minutes") or 25),
            lambda v: self._settings.set("pomodoro_focus_minutes", v),
            suffix=" min",
        )
        self._slider(
            "Short break length (minutes)", 1, 30,
            int(self._settings.get("pomodoro_break_minutes") or 5),
            lambda v: self._settings.set("pomodoro_break_minutes", v),
            suffix=" min",
        )
        self._check(
            "Reduce motion (static companion, no animations)",
            bool(self._settings.get("companion_reduced_motion")),
            lambda v: self._settings.set("companion_reduced_motion", v),
        )

        # ── Dashboard widgets ───────────────────────────────────────────────
        self._build_dashboard_section()

        # ── Word of the day ─────────────────────────────────────────────────
        self._build_word_of_day_section()

    def _build_dashboard_section(self) -> None:
        from ui.views.dashboard.registry import (
            WIDGET_LABELS,
            default_board,
            resolve_board,
        )

        self._section("Dashboard widgets")
        self._hint(
            "Choose which cards appear on your Dashboard. Your simplified default "
            "keeps things calm; Advanced mode starts with more."
        )
        active = set(resolve_board(self._settings))
        # Preserve a stable, sensible order: the advanced default lists them all.
        ordered_keys = default_board("advanced")
        for key in ordered_keys:
            label = WIDGET_LABELS.get(key, key)
            self._check(
                f"Show “{label}”",
                key in active,
                lambda checked, k=key: self._toggle_dashboard_widget(k, checked),
            )

    def _build_word_of_day_section(self) -> None:
        self._section("Word of the day")
        self._hint(
            "A vocabulary word shown on the Deadlines forecast. Pick categories, "
            "or add your own words."
        )
        self._check(
            "Show word of the day",
            bool(self._settings.get("word_of_day_enabled")),
            lambda v: self._settings.set("word_of_day_enabled", v),
        )
        active = set(self._settings.get("word_of_day_categories") or [])
        for category in ("academic", "fun", "interesting"):
            self._check(
                f"Include {category} words",
                category in active,
                lambda checked, c=category: self._toggle_word_category(c, checked),
            )
        edit = QPushButton("Edit custom words…")
        edit.setAccessibleName("Edit custom words for word of the day")
        edit.clicked.connect(self._edit_custom_words)
        self._form.addWidget(edit, alignment=Qt.AlignmentFlag.AlignLeft)

    def _toggle_word_category(self, category: str, on: bool) -> None:
        categories = list(self._settings.get("word_of_day_categories") or [])
        if on and category not in categories:
            categories.append(category)
        elif not on and category in categories:
            categories.remove(category)
        self._settings.set("word_of_day_categories", categories)

    def _edit_custom_words(self) -> None:
        from PyQt6.QtWidgets import QInputDialog

        current = "\n".join(self._settings.get("word_of_day_pool") or [])
        text, ok = QInputDialog.getMultiLineText(
            self, "Custom words",
            "One per line, e.g.  diligent - careful and persistent.\n"
            "Leave blank to use the built-in word pool.",
            current,
        )
        if ok:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            self._settings.set("word_of_day_pool", lines)

    def _toggle_dashboard_widget(self, key: str, visible: bool) -> None:
        from ui.views.dashboard.registry import default_board, resolve_board

        current = resolve_board(self._settings)
        if visible and key not in current:
            # Insert keeping the canonical order from the advanced default board.
            canonical = default_board("advanced")
            current = [k for k in canonical if k in set(current) | {key}]
        elif not visible and key in current:
            current = [k for k in current if k != key]
        self._settings.set("dashboard_widgets", current)

    # -- theme grid ----------------------------------------------------------

    def _build_theme_grid(self) -> QWidget:
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(10)
        grid.setContentsMargins(0, 4, 0, 4)
        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
        for (row, col), (key, _pal) in zip(positions, PALETTES.items()):
            card = _ThemeCard(key, parent=container)
            card.clicked.connect(self._on_theme_card_clicked)
            self._theme_cards.append((key, card))
            grid.addWidget(card, row, col)
        return container

    def _on_theme_card_clicked(self, key: str) -> None:
        self._settings.set("theme", key)

    # -- palette preview & card sync ----------------------------------------

    def _on_setting_changed(self, key: str, _value: object) -> None:
        if key in ("theme", "custom_colors"):
            self._update_palette_preview()
        if key == "theme":
            for row in self._color_rows:
                row.refresh()

    def _update_palette_preview(self, _key=None, _value=None) -> None:
        current_theme = self._settings.get("theme")
        pal = PALETTES.get(current_theme, PALETTES["dark"])
        colors = self._settings.get("custom_colors") or {}
        overrides = {k: v for k, v in colors.items() if hasattr(pal, k)}
        if overrides:
            pal = replace(pal, **overrides)

        self._swatch_surface.setStyleSheet(
            f"background:{pal.bg_surface}; border:1px solid {pal.border};"
        )
        self._swatch_accent.setStyleSheet(
            f"background:{pal.accent}; border:1px solid {pal.border};"
        )
        self._swatch_overlay.setStyleSheet(
            f"background:{pal.bg_surface}; color:{pal.text_primary};"
            f" border:1px solid {pal.border};"
        )

        for theme_key, card in self._theme_cards:
            card.set_selected(theme_key == current_theme)

    # -- palette import / export --------------------------------------------

    def _reset_overrides(self) -> None:
        self._settings.set("custom_colors", {})
        for row in self._color_rows:
            row.refresh()

    def _export_palette(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export palette", "my_palette.json",
            "JSON files (*.json);;All files (*)",
        )
        if not path:
            return
        data = self._settings.get("custom_colors") or {}
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass

    def _import_palette(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import palette", "",
            "JSON files (*.json);;All files (*)",
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(raw, dict):
            return
        # Accept only keys that exist on Palette
        from ui.theme.tokens import Palette
        valid = {k: v for k, v in raw.items()
                 if k in Palette.__dataclass_fields__ and isinstance(v, str)}
        if valid:
            self._settings.set("custom_colors", valid)
            for row in self._color_rows:
                row.refresh()

    # -- control builders ---------------------------------------------------

    def _section(self, title: str) -> None:
        label = QLabel(title)
        label.setObjectName("SettingsSection")
        self._form.addWidget(label)

    def _hint(self, text: str) -> None:
        lbl = QLabel(text)
        lbl.setObjectName("SettingsHint")
        lbl.setWordWrap(True)
        self._form.addWidget(lbl)

    def _field_label(self, text: str, hint: str | None) -> None:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        self._form.addWidget(label)
        if hint:
            self._hint(hint)

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
        self._field_label(
            "Font",
            "Dyslexia-friendly fonts are listed first. "
            "Missing fonts fall back to a system face.",
        )
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

    def _open_flag_editor(self) -> None:
        from ui.views.flag_editor import FlagEditorDialog
        if self._context is not None:
            FlagEditorDialog(self._context, self).exec()

    def _repair_search_index(self) -> None:
        from PyQt6.QtWidgets import QMessageBox

        from domain.search.search_service import SearchService

        if self._context is None or self._context.db is None:
            return
        try:
            SearchService(self._context.db, self._context.dictionary).repair()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(
                self, "Repair search index",
                f"The search index could not be rebuilt:\n{exc}",
            )
            return
        QMessageBox.information(
            self, "Repair search index", "The search index has been rebuilt."
        )

    def _on_rate_changed(self, value: int) -> None:
        self._settings.set("tts_rate", value)
        if self._tts is not None:
            self._tts.set_rate(value)

    def _test_voice(self) -> None:
        if self._tts is not None:
            self._tts.speak("This is a sample of the current voice and speed.")
