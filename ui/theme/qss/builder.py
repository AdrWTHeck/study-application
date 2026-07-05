"""Assemble per-component QSS modules into a single application stylesheet.

Each module owns one semantic area. Ordering matters: later rules win on equal
specificity. The sequence below mirrors the natural CSS cascade from structural
primitives up to page-specific components.
"""
from __future__ import annotations

from ui.theme.tokens import Tokens
from ui.theme.qss import (
    badges,
    containers,
    controls,
    dashboard,
    data_views,
    deadlines,
    layout,
    navigation,
    overlays,
    typography,
)


def build_qss(tokens: Tokens) -> str:
    sections = [
        layout.rules(tokens),
        typography.rules(tokens),
        navigation.rules(tokens),
        controls.rules(tokens),
        containers.rules(tokens),
        data_views.rules(tokens),
        overlays.rules(tokens),
        badges.rules(tokens),
        dashboard.rules(tokens),
        deadlines.rules(tokens),
    ]
    return "\n\n".join(s for s in sections if s)
