"""Sidebar, top bar, and navigation button rules."""
from __future__ import annotations

from ui.theme.tokens import Tokens
from ui.theme.qss.primitives import join_rules, rule


def rules(tokens: Tokens) -> str:
    p = tokens.palette
    t = tokens.typography
    d = tokens.density
    pad_v = d.space(1.0)
    pad_h = d.space(1.5)
    body_pt = f"{t.size('body')}pt"

    return join_rules([
        rule("QWidget#Sidebar", {
            "background-color": p.bg_surface,
            "border-right": f"1px solid {p.border}",
        }),
        rule("QWidget#TopBar", {
            "background-color": p.bg_surface,
            "border-bottom": f"1px solid {p.border}",
        }),
        # Mono ACC/ADV dual-mode badge in the topbar (clay redesign chrome).
        rule("QLabel#ModeBadge", {
            "color": p.text_secondary,
            "background-color": p.bg_raised,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius_sm}px",
            "font-family": f'"{t.mono_family}"',
            "font-size": f"{t.size('caption')}pt",
            "font-weight": "600",
            "padding": f"{d.space(0.25)}px {d.space(0.75)}px",
        }),
        rule('QPushButton[nav="true"]', {
            "text-align": "left",
            "padding": f"{pad_v}px {pad_h}px",
            "margin": f"{d.space(0.25)}px {d.space(1)}px",
            "border": "none",
            "border-left": "3px solid transparent",
            "border-radius": f"{d.radius_sm}px",
            "color": p.text_secondary,
            "background": "transparent",
            "font-size": body_pt,
            "min-height": f"{d.min_target}px",
        }),
        rule('QPushButton[nav="true"]:hover', {
            "background-color": p.bg_hover,
            "color": p.text_primary,
        }),
        rule('QPushButton[nav="true"][active="true"]', {
            "background-color": p.accent_muted,
            "color": p.text_primary,
            "border-left": f"3px solid {p.accent}",
            "font-weight": "600",
        }),
        rule('QPushButton[nav="true"]:focus', {
            "border": f"{d.focus_width}px solid {p.focus}",
        }),
    ])
