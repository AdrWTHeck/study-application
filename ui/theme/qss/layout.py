"""Structural layout rules: app surfaces, scroll areas, splitters."""
from __future__ import annotations

from ui.theme.tokens import Tokens
from ui.theme.qss.primitives import join_rules, rule


def rules(tokens: Tokens) -> str:
    p = tokens.palette
    return join_rules([
        rule("QMainWindow, QWidget#Content, QWidget#Page", {
            "background-color": p.bg_base,
        }),
        rule("QStackedWidget", {
            "background-color": "transparent",
        }),
        rule("QSplitter", {
            "background-color": "transparent",
        }),
        rule("QSplitter::handle", {
            "background-color": p.border,
        }),
        rule("QSplitter::handle:horizontal", {
            "width": "2px",
        }),
        rule("QSplitter::handle:vertical", {
            "height": "2px",
        }),
        rule("QSplitter::handle:hover", {
            "background-color": p.accent,
        }),
        # Scroll areas must stay transparent so the content widget's bg shows.
        rule("QScrollArea", {
            "border": "none",
            "background": "transparent",
            "background-color": "transparent",
        }),
        rule("QScrollArea > QWidget", {
            "background": "transparent",
            "background-color": "transparent",
        }),
        rule("QScrollArea QWidget#Page", {
            "background-color": p.bg_base,
        }),
    ])
