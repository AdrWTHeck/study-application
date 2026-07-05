"""Dialog and menu overlay rules."""
from __future__ import annotations

from ui.theme.tokens import Tokens
from ui.theme.qss.primitives import join_rules, rule


def rules(tokens: Tokens) -> str:
    p = tokens.palette
    t = tokens.typography
    d = tokens.density
    body_pt = f"{t.size('body')}pt"

    return join_rules([
        # Dialogs — solid surface background (overlay_bg is semi-transparent)
        rule("QDialog, QMessageBox", {
            "background-color": p.bg_surface,
            "color": p.text_primary,
            "border": f"1px solid {p.border}",
        }),
        # Prevent Windows from bleeding white background into direct dialog children
        rule("QDialog > QWidget, QMessageBox > QWidget", {
            "background-color": p.bg_surface,
        }),

        # Context menus
        rule("QMenu", {
            "background-color": p.bg_surface,
            "color": p.text_primary,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius_sm}px",
            "padding": f"{d.space(0.5)}px 0px",
        }),
        rule("QMenu::item", {
            "background-color": "transparent",
            "color": p.text_primary,
            "padding": f"{d.space(0.75)}px {d.space(2.5)}px",
            "font-size": body_pt,
        }),
        rule("QMenu::item:selected, QMenu::item:hover", {
            "background-color": p.accent_muted,
            "color": p.text_primary,
        }),
        rule("QMenu::separator", {
            "height": "1px",
            "background-color": p.border,
            "margin": f"{d.space(0.5)}px 0px",
        }),
    ])
