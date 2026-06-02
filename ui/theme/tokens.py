"""Design tokens — the single source of truth for the entire UI.

Three axes, all driven by settings:
  * palette   — color, with standard (dark/light) and high-contrast variants (VIS-02)
  * typography— family/size/spacing, scaled by ``font_scale`` (VIS-01, RDG-01/02)
  * density   — spacing/sizing, swapped by mode: comfortable (accessibility) vs
                compact (advanced)  (OVERHAUL_PLAN §2)

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
    warning: str
    danger: str
    # SRS card states (always paired with icon/text — never color alone, VIS-03)
    state_new: str
    state_learning: str
    state_review: str


DARK = Palette(
    name="dark", is_high_contrast=False,
    bg_base="#1a1b1e", bg_surface="#25262b", bg_raised="#2c2e33", bg_hover="#373a40",
    border="#373a40",
    text_primary="#e6e8ec", text_secondary="#aab1bd", text_dim="#7a818c",
    accent="#4263eb", accent_hover="#5c7cfa", accent_muted="#2b3577", on_accent="#ffffff",
    focus="#91a7ff",
    success="#69db7c", warning="#ffa94d", danger="#ff8787",
    state_new="#74c0fc", state_learning="#ffc078", state_review="#8ce99a",
)

LIGHT = Palette(
    name="light", is_high_contrast=False,
    bg_base="#ffffff", bg_surface="#f1f3f5", bg_raised="#e9ecef", bg_hover="#dee2e6",
    border="#ced4da",
    text_primary="#1a1b1e", text_secondary="#495057", text_dim="#868e96",
    accent="#3b5bdb", accent_hover="#364fc7", accent_muted="#dbe4ff", on_accent="#ffffff",
    focus="#4c6ef5",
    success="#2b8a3e", warning="#e8590c", danger="#c92a2a",
    state_new="#1971c2", state_learning="#e8590c", state_review="#2f9e44",
)

HC_DARK = Palette(
    name="hc_dark", is_high_contrast=True,
    bg_base="#000000", bg_surface="#000000", bg_raised="#0d0d0d", bg_hover="#1f1f1f",
    border="#ffffff",
    text_primary="#ffffff", text_secondary="#ffffff", text_dim="#e6e6e6",
    accent="#ffd400", accent_hover="#ffe066", accent_muted="#332b00", on_accent="#000000",
    focus="#ffd400",
    success="#5dff8a", warning="#ffb84d", danger="#ff6b6b",
    state_new="#99e9f2", state_learning="#ffe066", state_review="#8cff9e",
)

HC_LIGHT = Palette(
    name="hc_light", is_high_contrast=True,
    bg_base="#ffffff", bg_surface="#ffffff", bg_raised="#f2f2f2", bg_hover="#e0e0e0",
    border="#000000",
    text_primary="#000000", text_secondary="#000000", text_dim="#1a1a1a",
    accent="#0033cc", accent_hover="#0026a3", accent_muted="#d6e0ff", on_accent="#ffffff",
    focus="#0033cc",
    success="#006400", warning="#8a4b00", danger="#a30000",
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
    "subtitle": 1.15,
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
# Composed token set
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Tokens:
    palette: Palette
    typography: Typography
    density: Density


def build_tokens(
    *,
    theme: str = "dark",
    font_scale: float = 1.0,
    font_family: str = "Atkinson Hyperlegible",
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
    return Tokens(
        palette=palette,
        typography=typography,
        density=DENSITIES.get(density, COMFORTABLE),
    )
