"""Low-level QSS helpers shared by all rule modules."""
from __future__ import annotations


def rule(selector: str, props: dict[str, str]) -> str:
    body = " ".join(f"{k}: {v};" for k, v in props.items())
    return f"{selector} {{ {body} }}"


def join_rules(rules: list[str]) -> str:
    return "\n".join(r for r in rules if r)


def rgba(hex_color: str, alpha: float) -> str:
    """Turn a palette hex value into a QSS rgba() string.

    Palette fields must stay plain hex (painters do ``QColor(palette.x)``),
    so translucent tints live only inside QSS rule strings. High-contrast
    palettes should not use tints at all — callers branch on
    ``palette.is_high_contrast`` and substitute a solid muted color instead.
    """
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"
