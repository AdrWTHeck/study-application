"""Compile a :class:`Tokens` set into a single global Qt stylesheet.

Widgets reference tokens only through object names and dynamic properties
(``nav``, ``active``) — never hardcoded values — so a theme/scale/density change
is one stylesheet swap. Letter-spacing and line-height are *not* Qt-stylesheet
properties; those are applied via the application ``QFont`` and rich-text
rendering respectively (see ThemeController).
"""
from __future__ import annotations

from ui.theme.tokens import Tokens


def _rule(selector: str, props: dict[str, str]) -> str:
    body = " ".join(f"{k}: {v};" for k, v in props.items())
    return f"{selector} {{ {body} }}"


def build_qss(tokens: Tokens) -> str:
    p = tokens.palette
    t = tokens.typography
    d = tokens.density

    pad_v = d.space(1.0)
    pad_h = d.space(1.5)
    body_pt = f"{t.size('body')}pt"

    rules = [
        # base surfaces
        _rule("QMainWindow, QWidget#Content, QWidget#Page", {
            "background-color": p.bg_base,
        }),
        _rule("QLabel", {
            "color": p.text_primary,
            "background": "transparent",
            "font-size": body_pt,
        }),

        # sidebar
        _rule("QWidget#Sidebar", {
            "background-color": p.bg_surface,
            "border-right": f"1px solid {p.border}",
        }),
        _rule("QLabel#Logo", {
            "color": p.text_primary,
            "font-size": f"{t.size('title')}pt",
            "font-weight": "700",
            "padding": f"{d.space(2)}px {pad_h}px",
        }),
        _rule("QLabel#NavSection", {
            "color": p.text_dim,
            "font-size": f"{t.size('caption')}pt",
            "font-weight": "600",
            "padding": f"{d.space(1.5)}px {pad_h}px {d.space(0.5)}px {pad_h}px",
        }),

        # top bar
        _rule("QWidget#TopBar", {
            "background-color": p.bg_surface,
            "border-bottom": f"1px solid {p.border}",
        }),
        _rule("QLabel#TopTitle", {
            "color": p.text_primary,
            "font-size": f"{t.size('title')}pt",
            "font-weight": "700",
        }),

        # placeholder page content
        _rule("QLabel#PageTitle", {
            "color": p.text_primary,
            "font-size": f"{t.size('display')}pt",
            "font-weight": "700",
        }),
        _rule("QLabel#PageSubtitle", {
            "color": p.text_secondary,
            "font-size": f"{t.size('subtitle')}pt",
        }),

        # navigation buttons
        _rule('QPushButton[nav="true"]', {
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
        _rule('QPushButton[nav="true"]:hover', {
            "background-color": p.bg_hover,
            "color": p.text_primary,
        }),
        _rule('QPushButton[nav="true"][active="true"]', {
            "background-color": p.accent_muted,
            "color": p.text_primary,
            "border-left": f"3px solid {p.accent}",
            "font-weight": "600",
        }),
        _rule('QPushButton[nav="true"]:focus', {
            "border": f"{d.focus_width}px solid {p.focus}",
        }),

        # generic buttons
        _rule("QPushButton", {
            "background-color": p.bg_raised,
            "color": p.text_primary,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius_sm}px",
            "padding": f"{pad_v}px {pad_h}px",
            "min-height": f"{d.min_target}px",
            "font-size": body_pt,
        }),
        _rule("QPushButton:hover", {
            "background-color": p.bg_hover,
            "border-color": p.accent,
        }),
        _rule("QPushButton:focus", {
            "border": f"{d.focus_width}px solid {p.focus}",
        }),
        _rule("QPushButton:default", {
            "background-color": p.accent,
            "color": p.on_accent,
            "border-color": p.accent,
        }),

        # inputs (used from Phase 1 settings onward)
        _rule("QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit", {
            "background-color": p.bg_raised,
            "color": p.text_primary,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius_sm}px",
            "padding": f"{d.space(0.75)}px {pad_v}px",
            "min-height": f"{d.min_target}px",
            "font-size": body_pt,
            "selection-background-color": p.accent,
            "selection-color": p.on_accent,
        }),
        _rule("QLineEdit:focus, QComboBox:focus, QSpinBox:focus, "
              "QPlainTextEdit:focus, QTextEdit:focus", {
            "border": f"{d.focus_width}px solid {p.focus}",
        }),

        # settings / form elements
        _rule("QLabel#SettingsSection", {
            "color": p.text_primary,
            "font-size": f"{t.size('subtitle')}pt",
            "font-weight": "700",
            "padding": f"{d.space(2)}px 0px {d.space(0.5)}px 0px",
        }),
        _rule("QLabel#SettingsHint", {
            "color": p.text_secondary,
            "font-size": f"{t.size('caption')}pt",
        }),
        _rule("QLabel#FieldLabel", {
            "color": p.text_primary,
            "font-size": body_pt,
            "font-weight": "600",
        }),
        _rule("QCheckBox", {
            "color": p.text_primary,
            "font-size": body_pt,
            "spacing": f"{d.space(1)}px",
            "min-height": f"{d.min_target}px",
        }),
        _rule("QCheckBox:focus", {
            "border": f"{d.focus_width}px solid {p.focus}",
            "border-radius": f"{d.radius_sm}px",
        }),

        # deck browser + card review
        _rule("QWidget#DeckRow", {
            "background-color": p.bg_surface,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius}px",
        }),
        _rule("QLabel#DeckName", {
            "font-size": f"{t.size('subtitle')}pt",
            "font-weight": "600",
            "color": p.text_primary,
        }),
        _rule('QLabel[badge="new"]', {"color": p.state_new, "font-weight": "700"}),
        _rule('QLabel[badge="learning"]', {"color": p.state_learning, "font-weight": "700"}),
        _rule('QLabel[badge="review"]', {"color": p.state_review, "font-weight": "700"}),
        _rule("QTextBrowser#CardFace", {
            "background-color": p.bg_surface,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius}px",
            "padding": f"{d.space(3)}px",
            "font-size": f"{t.size('title')}pt",
            "color": p.text_primary,
        }),

        # scrollbars (subtle, theme-aware)
        _rule("QScrollBar:vertical", {
            "background": "transparent",
            "width": "10px",
            "margin": "0px",
        }),
        _rule("QScrollBar::handle:vertical", {
            "background": p.bg_hover,
            "border-radius": "5px",
            "min-height": "30px",
        }),
        _rule("QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical", {
            "height": "0px",
        }),
    ]
    return "\n".join(rules)
