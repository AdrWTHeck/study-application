"""Design tokens — the single source of truth for the entire UI.

Four axes, all driven by settings:
  * palette   — color, with standard (dark/light) and high-contrast variants (VIS-02)
  * typography— family/size/spacing, scaled by ``font_scale`` (VIS-01, RDG-01/02)
  * density   — spacing/sizing, swapped by mode: comfortable (accessibility) vs
                compact (advanced)  (OVERHAUL_PLAN §2)
  * layout    — structural margins, top-bar height, and per-page content widths
                so each page uses just as much horizontal space as it benefits from

No view hardcodes a color, size, or spacing value; everything derives from here,
which is what prevents the layout drift / overlap from the previous iteration.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Palette:
    name: str
    is_high_contrast: bool
    # surfaces
    bg_base: str
    bg_surface: str
    overlay_bg: str
    overlay_text: str
    bg_raised: str
    bg_hover: str
    border: str
    # text
    text_primary: str
    text_secondary: str
    text_dim: str
    # accent
    accent: str
    accent_hover: str
    accent_muted: str
    on_accent: str
    focus: str
    # semantic status
    success: str
    success_muted: str
    warning: str
    warning_muted: str
    danger: str
    danger_muted: str
    info: str
    info_muted: str
    # SRS card states (always paired with icon/text — never color alone, VIS-03)
    state_new: str
    state_learning: str
    state_review: str


# "Clay" — the warm dark theme from the StudyApp UI redesign (terracotta accent
# on deep warm browns, cream-tinted text). All values are plain hex because
# painters do QColor(palette.x), which cannot parse rgba() strings.
DARK = Palette(
    name="dark", is_high_contrast=False,
    bg_base="#16130e", bg_surface="#1b1711", bg_raised="#201c15", bg_hover="#262117",
    border="#332d24",
    text_primary="#f3ede2", text_secondary="#9d9486", text_dim="#6f685c",
    overlay_bg="#00000080", overlay_text="#ffffff",
    accent="#d97757", accent_hover="#e08a6d", accent_muted="#33201a", on_accent="#1a1006",
    focus="#e0a06d",
    success="#7fa76a", success_muted="#23301e",
    warning="#d9a441", warning_muted="#33290f",
    danger="#cf6b5a", danger_muted="#33201c",
    info="#6f9edb", info_muted="#1d2836",
    state_new="#6f9edb", state_learning="#d9a441", state_review="#7fa76a",
)

# "Cream" — the matching light theme: warm paper surfaces, deep clay accent.
LIGHT = Palette(
    name="light", is_high_contrast=False,
    bg_base="#faf7f0", bg_surface="#f5f0e6", bg_raised="#ede6d8", bg_hover="#e6dcc9",
    border="#d5cbb8",
    text_primary="#232019", text_secondary="#6a6252", text_dim="#8a8172",
    overlay_bg="#ffffffcc", overlay_text="#232019",
    accent="#b0543a", accent_hover="#c25f3f", accent_muted="#f3ddd4", on_accent="#ffffff",
    focus="#b0543a",
    success="#4f7d3d", success_muted="#e3eeda",
    warning="#8a5d0a", warning_muted="#f5e9d0",
    danger="#a33d2a", danger_muted="#f7e0da",
    info="#3d6a9e", info_muted="#dfe9f5",
    state_new="#3d6a9e", state_learning="#a05f16", state_review="#4f7d3d",
)

HC_DARK = Palette(
    name="hc_dark", is_high_contrast=True,
    bg_base="#000000", bg_surface="#000000", bg_raised="#0d0d0d", bg_hover="#1f1f1f",
    border="#ffffff",
    text_primary="#ffffff", text_secondary="#ffffff", text_dim="#e6e6e6",
    overlay_bg="#000000", overlay_text="#ffffff",
    accent="#ffd400", accent_hover="#ffe066", accent_muted="#332b00", on_accent="#000000",
    focus="#ffd400",
    success="#5dff8a", success_muted="#003318",
    warning="#ffb84d", warning_muted="#3d2800",
    danger="#ff6b6b", danger_muted="#3d0000",
    info="#99e9f2", info_muted="#003340",
    state_new="#99e9f2", state_learning="#ffe066", state_review="#8cff9e",
)

HC_LIGHT = Palette(
    name="hc_light", is_high_contrast=True,
    bg_base="#ffffff", bg_surface="#ffffff", bg_raised="#f2f2f2", bg_hover="#e0e0e0",
    border="#000000",
    text_primary="#000000", text_secondary="#000000", text_dim="#1a1a1a",
    overlay_bg="#ffffff", overlay_text="#000000",
    accent="#0033cc", accent_hover="#0026a3", accent_muted="#d6e0ff", on_accent="#ffffff",
    focus="#0033cc",
    success="#006400", success_muted="#d0f5d8",
    warning="#8a4b00", warning_muted="#ffe5cc",
    danger="#a30000", danger_muted="#ffd5d5",
    info="#003f8a", info_muted="#d0e4ff",
    state_new="#003f8a", state_learning="#8a4b00", state_review="#006400",
)

PALETTES: dict[str, Palette] = {p.name: p for p in (DARK, LIGHT, HC_DARK, HC_LIGHT)}


# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

# Type roles as multiples of the base size; effective pt = base * scale * role.
_TYPE_ROLES: dict[str, float] = {
    "caption": 0.85,
    "body": 1.0,
    "card_title": 1.08,
    "subtitle": 1.15,
    "section": 1.25,
    "title": 1.45,
    "h2": 1.8,
    "display": 2.3,
}


@dataclass(frozen=True)
class Typography:
    family: str
    base_pt: float
    scale: float
    line_height: float
    letter_spacing: float
    word_spacing: float
    # Monospace face for eyebrow/section labels and mono badges (falls back
    # via ui.theme.fonts.resolve_mono when not installed/bundled).
    mono_family: str = "IBM Plex Mono"

    def size(self, role: str = "body") -> int:
        mult = _TYPE_ROLES.get(role, 1.0)
        return max(1, round(self.base_pt * self.scale * mult))


# ---------------------------------------------------------------------------
# Density
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Density:
    name: str
    space_unit: int      # base spacing unit (px)
    control_height: int
    sidebar_width: int
    radius: int
    radius_sm: int
    focus_width: int
    min_target: int      # minimum interactive target (KBD-02 / WCAG 2.5.5)

    def space(self, mult: float = 1.0) -> int:
        return max(0, round(self.space_unit * mult))


COMFORTABLE = Density(
    name="comfortable", space_unit=8, control_height=44, sidebar_width=248,
    radius=10, radius_sm=6, focus_width=3, min_target=44,
)
COMPACT = Density(
    name="compact", space_unit=6, control_height=32, sidebar_width=200,
    radius=8, radius_sm=4, focus_width=2, min_target=32,
)

DENSITIES: dict[str, Density] = {d.name: d for d in (COMFORTABLE, COMPACT)}


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Layout:
    """The fourth design axis: structural spacing and per-page content widths.

    Margins, the top-bar height, and the inter-card gap scale with density, so
    the whole shell tightens in compact mode. The named content widths let each
    page declare how much horizontal space it should use — ``wide`` for
    workspace pages (reader, deadlines), ``focused`` for reading/forms
    (settings) — instead of one global cap. ``width_full`` is a sentinel
    meaning "use the whole window".
    """

    name: str
    topbar_height: int
    page_margin_x: int
    page_margin_y: int
    gap: int
    width_narrow: int
    width_focused: int
    width_balanced: int
    width_wide: int
    width_full: int
    deck_pane_width: int

    def content_width(self, width_class: str = "balanced") -> int:
        return {
            "narrow": self.width_narrow,
            "focused": self.width_focused,
            "balanced": self.width_balanced,
            "wide": self.width_wide,
            "full": self.width_full,
        }.get(width_class, self.width_balanced)


COMFORTABLE_LAYOUT = Layout(
    name="comfortable", topbar_height=56, page_margin_x=40, page_margin_y=24, gap=16,
    width_narrow=660, width_focused=760, width_balanced=1080, width_wide=1400,
    width_full=100_000, deck_pane_width=340,
)
COMPACT_LAYOUT = Layout(
    name="compact", topbar_height=48, page_margin_x=28, page_margin_y=18, gap=12,
    width_narrow=640, width_focused=720, width_balanced=1140, width_wide=1480,
    width_full=100_000, deck_pane_width=300,
)

LAYOUTS: dict[str, Layout] = {lt.name: lt for lt in (COMFORTABLE_LAYOUT, COMPACT_LAYOUT)}


# ---------------------------------------------------------------------------
# Composed token set
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Tokens:
    palette: Palette
    typography: Typography
    density: Density
    layout: Layout


def build_tokens(
    *,
    theme: str = "dark",
    font_scale: float = 1.0,
    font_family: str = "IBM Plex Sans",
    line_height: float = 1.5,
    letter_spacing: float = 0.0,
    word_spacing: float = 0.0,
    density: str = "comfortable",
    custom_colors: dict[str, str] | None = None,
) -> Tokens:
    """Compose a full token set from individual setting values."""
    palette = PALETTES.get(theme, DARK)
    if custom_colors:
        overrides = {k: v for k, v in custom_colors.items() if hasattr(palette, k)}
        if overrides:
            palette = replace(palette, **overrides)
    typography = Typography(
        family=font_family,
        base_pt=12.0,
        scale=max(1.0, min(float(font_scale), 2.0)),
        line_height=line_height,
        letter_spacing=letter_spacing,
        word_spacing=word_spacing,
    )
    density_tokens = DENSITIES.get(density, COMFORTABLE)
    return Tokens(
        palette=palette,
        typography=typography,
        density=density_tokens,
        layout=LAYOUTS.get(density_tokens.name, COMFORTABLE_LAYOUT),
    )
