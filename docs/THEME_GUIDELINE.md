# Theme Usage & Integration Guideline

This is the canonical reference for theming any view in the app. The whole UI is
**token-driven**: no view hardcodes a color, size, or spacing value — everything
derives from `Tokens`, which is what keeps the build visually consistent and
makes dark/light/high-contrast and comfortable/compact switching "just work".

> If you are adding or changing a view, follow the [New-View Checklist](#new-view-checklist).
> The Converter view (`ui/views/converter_view.py`) is the reference example.

---

## 1. How the system fits together

```
core/settings.py ──▶ ui/theme/theme_controller.py ──▶ build_tokens()  ──▶ Tokens
                                  │                    (ui/theme/tokens.py)
                                  │
                                  ▼
                       ui/theme/qss/builder.py ──▶ build_qss(tokens) ──▶ one global stylesheet
                                  │
                                  ▼
                       app.setStyleSheet(qss)  ──▶ every widget styled by objectName / type
```

- **`ui/theme/tokens.py`** — the single source of truth. `Tokens = palette + typography + density + layout`.
- **`ui/theme/theme_controller.py`** — `ThemeController` recomposes tokens when a relevant setting changes and re-applies the stylesheet. It exposes `tokens` and a `changed` signal.
- **`ui/theme/qss/`** — 11 modules, each owning one semantic area; `builder.py` joins them in cascade order. **Adding a rule inside an existing module needs no builder change.**
- **Views** set `objectName()` (and dynamic properties) to match QSS rules. They never set colors inline.

---

## 2. Token vocabulary (`ui/theme/tokens.py`)

### Palette roles — access via `tokens.palette.<role>`

| Group | Roles |
|-------|-------|
| Surfaces | `bg_base`, `bg_surface`, `bg_raised`, `bg_hover`, `overlay_bg`, `overlay_text` |
| Border | `border` |
| Text | `text_primary`, `text_secondary`, `text_dim` |
| Accent | `accent`, `accent_hover`, `accent_muted`, `on_accent`, `focus` |
| Status | `success`(`_muted`), `warning`(`_muted`), `danger`(`_muted`), `info`(`_muted`) |
| SRS states | `state_new`, `state_learning`, `state_review` (always paired with icon/text — never color alone, VIS-03) |

Four palettes exist: `dark`, `light`, `hc_dark`, `hc_light`. User custom colors override individual roles via `build_tokens(custom_colors=…)`.

### Typography — `tokens.typography.size("<role>")` → int pt

`caption` 0.85 · `body` 1.0 · `card_title` 1.08 · `subtitle` 1.15 · `section` 1.25 · `title` 1.45 · `h2` 1.8 · `display` 2.3 (multipliers of `base_pt × scale`).

### Density — `tokens.density`

`space(mult)` → scaled px (unit 8 comfortable / 6 compact). Also `control_height`, `sidebar_width`, `radius`, `radius_sm`, `focus_width`, `min_target`.

### Layout — `tokens.layout`

`topbar_height`, `page_margin_x/y`, `gap`, and `content_width("focused"|"balanced"|"wide"|"full")`. Per-page width class lives in `app/main_window.py::_PAGE_WIDTH_CLASS`.

---

## 3. Reusable styled object names

Set these with `setObjectName(...)` to inherit the matching QSS. (Owner module under `ui/theme/qss/`.)

| Object name | Widget | Purpose | Module |
|-------------|--------|---------|--------|
| `Page` | QWidget | Standard page/root container (bg_base) | layout |
| `PageTitle` / `PageSubtitle` | QLabel | Hero title / subtitle | typography |
| `SettingsSection` / `SettingsHint` / `FieldLabel` | QLabel | Section header / helper text / field label | typography |
| `Card` / `SurfacePanel` | QWidget | Surface container (bg_surface + border + radius) | containers |
| `DeckRow` | QWidget | List/deck row surface | containers |
| `PrimaryButton` | QPushButton | Accent call-to-action button | controls |
| `DeckLink` | QPushButton | Flat accent hyperlink-style button | containers |
| `ConverterStatus` | QLabel | Status line; color via `[state]` property | controls |
| `DashboardCard`, `DeadlineCard`, `AchievementTile`, … | QWidget | Page-specific cards | dashboard / deadlines / containers |

**Styled by widget type (no object name needed):** `QPushButton` (+`:default`), `QLineEdit`/`QComboBox`/`QSpinBox`/`QTextEdit`/…, `QCheckBox`, `QRadioButton`, `QGroupBox` (+`::title`), `QProgressBar` (+`::chunk` accent), `QSlider`, `QTabWidget`/`QTabBar`, `QAbstractItemView`, `QScrollBar`, `QMenu`, `QDialog`.

### Dynamic properties (state-driven styling)

Set with `setProperty("name", value)` then re-polish (see helper below):

| Property | Values | Used on |
|----------|--------|---------|
| `nav` / `active` | `true`/`false` | sidebar nav buttons |
| `badge` | `new` / `learning` / `review` | SRS state labels |
| `unlocked` / `hidden` | `true`/`false` | achievement tiles |
| `state` | `running` / `success` / `error` | `ConverterStatus` |

Re-polish after changing a dynamic property:

```python
style = widget.style()
if style is not None:
    style.unpolish(widget)
    style.polish(widget)
```

---

## 4. Conventions (the rules)

1. **No hardcoded colors in view code.** Use object names + QSS. (Exceptions in §6.)
2. **Reuse existing object names** before inventing a new one. If you need a new
   styled primitive, add a rule to the right `ui/theme/qss/` module so it is
   available app-wide — don't `setStyleSheet()` on the widget.
3. **Custom surfaces need a styled background.** Any `QWidget` you give a
   `bg_*`/border via object name must also call
   `setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)` or the
   background/border won't paint.
4. **Spacing comes from tokens.** Prefer `tokens.density.space(mult)` /
   `tokens.layout.*` over magic pixel numbers, so layouts tighten in compact
   mode. A small `_sp(mult)` helper that falls back to `8*mult` (for context-less
   construction) is the established pattern (see `ConverterView._sp`).
5. **React to theme changes when spacing is computed in Python.** Colors update
   automatically (the global stylesheet is re-applied), but token-derived margins
   set once in code do not — connect `context.theme.changed` and re-apply. (See
   `ConverterView._on_theme_changed`.)
6. **Accessibility is non-negotiable** (this is the thesis thesis): every
   interactive widget gets `setAccessibleName(...)`, targets meet `min_target`,
   focus rings come from the `:focus` rules, and state is never color-only.

---

## 5. New-View Checklist

- [ ] Root widget `setObjectName("Page")` (or a page-specific name with a QSS rule).
- [ ] Reuse `PageTitle` / `PageSubtitle` / `SurfacePanel` / `Card` / `FieldLabel` / etc.
- [ ] `WA_StyledBackground` on every custom surface container.
- [ ] Spacing via `tokens.density.space()` / `tokens.layout` (with a fallback).
- [ ] `setAccessibleName()` on all interactive widgets; meet `min_target`.
- [ ] State-driven styling via dynamic properties + re-polish — not inline color.
- [ ] No hex colors in the `.py` file (grep your file for `#` to be sure).
- [ ] If the view computes spacing in Python, connect `context.theme.changed`.
- [ ] Register width class in `_PAGE_WIDTH_CLASS` if it's a routed destination.

---

## 6. Justified inline-style exceptions

Inline `setStyleSheet()`/hex is acceptable **only** when the color *is* the data:

- **Live palette previews** (the theme swatch cards in `settings_view.py`).
- **User-configured colors** read from settings (e.g. earned-badge border in `achievements_view.py`).
- **Annotation color palettes** in the reader (a fixed, user-pickable swatch set).
- **Contrast/utility functions** that compute a readable text color.

Everything else goes through tokens + QSS.

---

## 7. Primitives added for the converter (reference)

These were added so the Converter view reads like the rest of the build, and are
now reusable everywhere:

- `QGroupBox` + `QGroupBox::title` — themed surface group container (`ui/theme/qss/containers.py`).
- `QRadioButton` — mirrors the `QCheckBox` treatment (`ui/theme/qss/controls.py`).
- `QPushButton#PrimaryButton` — accent CTA, with hover/focus/disabled states (`ui/theme/qss/controls.py`).
- `QLabel#ConverterStatus[state=…]` — semantic status line (`ui/theme/qss/controls.py`).
