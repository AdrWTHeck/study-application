"""Reusable container widgets: deck rows, card face, deck link button."""
from __future__ import annotations

from ui.theme.tokens import Tokens
from ui.theme.qss.primitives import join_rules, rgba, rule


def rules(tokens: Tokens) -> str:
    p = tokens.palette
    t = tokens.typography
    d = tokens.density
    body_pt = f"{t.size('body')}pt"
    caption = f"{t.size('caption')}pt"
    mono = f'"{t.mono_family}"'

    # HC palettes get solid fills instead of translucent tints (VIS-02).
    if p.is_high_contrast:
        action_accent_bg = p.accent_muted
    else:
        action_accent_bg = (
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {rgba(p.accent, 0.22)}, stop:1 {rgba(p.accent, 0.08)})"
        )

    return join_rules([
        # Generic card primitive — pages specialise via their own object name
        rule("QWidget#Card", {
            "background-color": p.bg_surface,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius}px",
        }),
        rule("QWidget#Card:hover", {
            "border-color": p.bg_hover,
        }),
        rule("QWidget#SurfacePanel", {
            "background-color": p.bg_surface,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius}px",
        }),

        # Group box — themed surface container with a labelled title. Used to
        # group related controls (e.g. the converter's sections) so it reads
        # like the rest of the build instead of the raw Qt default frame.
        rule("QGroupBox", {
            "background-color": p.bg_surface,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius}px",
            "margin-top": f"{d.space(2)}px",
            "padding": f"{d.space(2.5)}px {d.space(2)}px {d.space(2)}px {d.space(2)}px",
            "font-size": f"{t.size('card_title')}pt",
        }),
        rule("QGroupBox::title", {
            "subcontrol-origin": "margin",
            "subcontrol-position": "top left",
            "left": f"{d.space(1.5)}px",
            "padding": f"0px {d.space(0.75)}px",
            "color": p.text_secondary,
            "font-weight": "600",
        }),

        # Deck browser row
        rule("QWidget#DeckRow", {
            "background-color": p.bg_surface,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius}px",
        }),

        # Flashcard face in review/cram
        rule("QTextBrowser#CardFace", {
            "background-color": p.bg_surface,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius}px",
            "padding": f"{d.space(3)}px",
            "font-size": f"{t.size('title')}pt",
            "color": p.text_primary,
        }),

        # Deck link — flat, accent-coloured hyperlink style
        rule("QPushButton#DeckLink", {
            "background": "transparent",
            "border": "none",
            "color": p.accent,
            "font-size": body_pt,
            "font-weight": "600",
            "text-align": "left",
            "padding": "0px",
            "min-height": "0px",
        }),
        rule("QPushButton#DeckLink:hover", {
            "color": p.accent_hover,
            "text-decoration": "underline",
        }),
        rule("QPushButton#DeckLink:focus", {
            "border": f"{d.focus_width}px solid {p.focus}",
            "border-radius": f"{d.radius_sm}px",
        }),

        # SRS state badge via [badge] dynamic property
        rule('QLabel[badge="new"]', {"color": p.state_new, "font-weight": "700"}),
        rule('QLabel[badge="learning"]', {"color": p.state_learning, "font-weight": "700"}),
        rule('QLabel[badge="review"]', {"color": p.state_review, "font-weight": "700"}),

        # Achievement tiles (rounded squares; states via dynamic properties)
        rule("QWidget#AchievementTile", {
            "background-color": p.bg_raised,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius}px",
        }),
        rule('QWidget#AchievementTile[unlocked="false"]', {
            "background-color": p.bg_base,
        }),
        rule('QWidget#AchievementTile[hidden="true"]', {
            "background-color": p.bg_base,
            "border": f"1px dashed {p.border}",
        }),
        rule("QWidget#AchievementTile:hover", {
            "border-color": p.accent,
        }),
        rule("QLabel#AchievementTileTitle", {
            "color": p.text_primary,
            "font-size": f"{t.size('caption')}pt",
            "font-weight": "600",
            "background-color": "transparent",
        }),
        rule("QLabel#AchievementSymbol", {
            "background-color": "transparent",
            "font-size": f"{t.size('h2')}pt",
        }),
        # Companion glyph (tree/mascot) — token-sized so it scales with font_scale
        # (RDG-01) instead of a hardcoded pixel size.
        rule("QLabel#CompanionGlyph", {
            "background-color": "transparent",
            "font-size": f"{t.size('display')}pt",
        }),

        # --- Clay redesign: deck browser two-pane -------------------------
        rule("QWidget#DeckListPane", {
            "background-color": p.bg_surface,
            "border-right": f"1px solid {p.border}",
        }),
        # Small mono "DECK" kind chip next to the detail title.
        rule("QLabel#DeckKindTag", {
            "color": p.text_dim,
            "font-family": mono,
            "font-size": caption,
            "font-weight": "600",
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius_sm}px",
            "padding": f"1px {d.space(1)}px",
        }),
        # Large study-action cards (Review / Quick pass / Cram).
        rule("QPushButton#StudyActionCard", {
            "background-color": p.bg_raised,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius}px",
            "padding": f"{d.space(1.5)}px {d.space(2)}px",
            "text-align": "left",
        }),
        rule("QPushButton#StudyActionCard:hover", {
            "background-color": p.bg_hover,
            "border-color": p.accent,
        }),
        rule("QPushButton#StudyActionCard:focus", {
            "border": f"{d.focus_width}px solid {p.focus}",
        }),
        rule('QPushButton#StudyActionCard[accent="true"]', {
            "background": action_accent_bg,
            "border": f"1px solid {p.accent}",
        }),
        rule("QLabel#StudyActionTitle", {
            "color": p.text_primary,
            "font-size": f"{t.size('card_title')}pt",
            "font-weight": "700",
            "background": "transparent",
        }),
        rule("QLabel#StudyActionHint", {
            "color": p.text_secondary,
            "font-size": caption,
            "background": "transparent",
        }),
        # Mono column-header row above the embedded notes table.
        rule("QWidget#NotesTableHeader", {
            "background-color": p.bg_raised,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius_sm}px",
        }),
        rule("QWidget#NotesTableHeader QLabel", {
            "color": p.text_dim,
            "font-family": mono,
            "font-size": caption,
            "font-weight": "600",
            "background": "transparent",
        }),

        # --- Clay redesign: review session chrome --------------------------
        rule("QWidget#SessionHeader", {
            "background-color": "transparent",
            "border-bottom": f"1px solid {p.border}",
        }),
        rule("QWidget#SessionHeader QLabel", {"background": "transparent"}),
        rule("QLabel#SessionCounter", {
            "color": p.text_secondary,
            "font-family": mono,
            "font-size": body_pt,
            "font-weight": "600",
        }),
        rule("QLabel#SessionEngineTag", {
            "color": p.text_dim,
            "font-family": mono,
            "font-size": caption,
            "font-weight": "600",
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius_sm}px",
            "padding": f"1px {d.space(1)}px",
        }),
        # Session-complete summary card.
        rule("QWidget#SummaryCard", {
            "background-color": p.bg_surface,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius + 4}px",
        }),
        rule("QWidget#SummaryCard QLabel", {"background": "transparent"}),
        rule("QLabel#SummaryStatValue", {
            "color": p.text_primary,
            "font-family": mono,
            "font-size": f"{t.size('h2')}pt",
            "font-weight": "700",
        }),
        rule("QLabel#SummaryStatCaption", {
            "color": p.text_secondary,
            "font-size": caption,
        }),
        # Per-rating count chips in the summary (always carry text labels).
        rule("QLabel#RatingPill", {
            "font-size": caption,
            "font-weight": "700",
            "border-radius": f"{d.radius_sm}px",
            "padding": f"2px {d.space(1.5)}px",
        }),
        rule('QLabel#RatingPill[rating="again"]', {
            "color": p.danger, "background-color": p.danger_muted,
            "border": f"1px solid {p.danger}",
        }),
        rule('QLabel#RatingPill[rating="hard"]', {
            "color": p.warning, "background-color": p.warning_muted,
            "border": f"1px solid {p.warning}",
        }),
        rule('QLabel#RatingPill[rating="good"]', {
            "color": p.success, "background-color": p.success_muted,
            "border": f"1px solid {p.success}",
        }),
        rule('QLabel#RatingPill[rating="easy"]', {
            "color": p.info, "background-color": p.info_muted,
            "border": f"1px solid {p.info}",
        }),
    ])
