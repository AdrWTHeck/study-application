"""WCAG 2.1 contrast-ratio utilities (VIS-02 acceptance criteria).

Used both at runtime and in tests to assert that every shipped theme meets its
contrast target before it can be considered done.
"""
from __future__ import annotations

# WCAG 2.1 thresholds.
AA_NORMAL = 4.5
AA_LARGE = 3.0
AAA_NORMAL = 7.0
UI_COMPONENT = 3.0  # 1.4.11 Non-text Contrast (focus rings, borders)


def _channel_to_linear(value: int) -> float:
    c = value / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _parse_hex(color: str) -> tuple[int, int, int]:
    h = color.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) != 6:
        raise ValueError(f"Invalid hex color: {color!r}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def relative_luminance(color: str) -> float:
    r, g, b = _parse_hex(color)
    return (
        0.2126 * _channel_to_linear(r)
        + 0.7152 * _channel_to_linear(g)
        + 0.0722 * _channel_to_linear(b)
    )


def contrast_ratio(fg: str, bg: str) -> float:
    """Return the WCAG contrast ratio (1.0–21.0) between two hex colors."""
    l1 = relative_luminance(fg)
    l2 = relative_luminance(bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def meets(fg: str, bg: str, threshold: float = AA_NORMAL) -> bool:
    return contrast_ratio(fg, bg) >= threshold
