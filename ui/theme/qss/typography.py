"""Text and label rules: base QLabel, semantic named labels, section separators."""
from __future__ import annotations

from ui.theme.tokens import Tokens
from ui.theme.qss.primitives import join_rules, rule


def rules(tokens: Tokens) -> str:
    p = tokens.palette
    t = tokens.typography
    d = tokens.density
    body_pt = f"{t.size('body')}pt"

    return join_rules([
        rule("QLabel", {
            "color": p.text_primary,
            "background": "transparent",
            "font-size": body_pt,
        }),
        rule("QLabel#Logo", {
            "color": p.text_primary,
            "font-size": f"{t.size('title')}pt",
            "font-weight": "700",
            "padding": f"{d.space(2)}px {d.space(1.5)}px",
        }),
        # Mono uppercase "eyebrow" section labels (MAIN / TOOLS), per the clay
        # redesign. Letter-spacing/uppercase aren't QSS properties in Qt, so
        # the caller uppercases the text; the mono face carries the look.
        rule("QLabel#NavSection", {
            "color": p.text_dim,
            "font-family": f'"{t.mono_family}"',
            "font-size": f"{t.size('caption')}pt",
            "font-weight": "600",
            "padding": f"{d.space(1.5)}px {d.space(1.5)}px {d.space(0.5)}px {d.space(1.5)}px",
        }),
        # Library folder-sidebar eyebrow — same treatment as NavSection.
        rule("QLabel#SidebarTitle", {
            "color": p.text_dim,
            "font-family": f'"{t.mono_family}"',
            "font-size": f"{t.size('caption')}pt",
            "font-weight": "600",
        }),
        # Generic mono uppercase eyebrow for card/section headers anywhere
        # (callers uppercase the text; Qt QSS has no text-transform).
        rule("QLabel#Eyebrow", {
            "color": p.text_dim,
            "font-family": f'"{t.mono_family}"',
            "font-size": f"{t.size('caption')}pt",
            "font-weight": "600",
        }),
        rule("QLabel#TopTitle", {
            "color": p.text_primary,
            "font-size": f"{t.size('title')}pt",
            "font-weight": "700",
        }),
        rule("QLabel#PageTitle", {
            "color": p.text_primary,
            "font-size": f"{t.size('display')}pt",
            "font-weight": "700",
        }),
        rule("QLabel#PageSubtitle", {
            "color": p.text_secondary,
            "font-size": f"{t.size('subtitle')}pt",
        }),
        rule("QLabel#SettingsSection", {
            "color": p.text_primary,
            "font-size": f"{t.size('subtitle')}pt",
            "font-weight": "700",
            "padding": f"{d.space(2)}px 0px {d.space(0.5)}px 0px",
        }),
        rule("QLabel#SettingsHint", {
            "color": p.text_secondary,
            "font-size": f"{t.size('caption')}pt",
        }),
        rule("QLabel#FieldLabel", {
            "color": p.text_primary,
            "font-size": body_pt,
            "font-weight": "600",
        }),
        rule("QLabel#DeckName", {
            "color": p.text_primary,
            "font-size": f"{t.size('subtitle')}pt",
            "font-weight": "600",
        }),
        rule("QLabel#DeckTitle", {
            "color": p.text_primary,
            "font-size": f"{t.size('subtitle')}pt",
            "font-weight": "600",
        }),
        # Unified deadline/card title — uses card_title role for slightly smaller than subtitle
        rule("QLabel#DeadlineTitle", {
            "color": p.text_primary,
            "font-size": f"{t.size('card_title')}pt",
            "font-weight": "700",
            "background": "transparent",
        }),
        rule("QLabel#DeadlineMeta", {
            "color": p.text_secondary,
            "font-size": f"{t.size('caption')}pt",
            "font-weight": "500",
            "background": "transparent",
        }),
        rule("QLabel#SectionSeparator", {
            "color": p.text_dim,
            "font-size": f"{t.size('caption')}pt",
            "font-weight": "700",
            "padding": f"{d.space(2)}px 0px {d.space(0.5)}px 0px",
        }),
    ])
