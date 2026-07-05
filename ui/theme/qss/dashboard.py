"""Dashboard card rules (plus the test-results snapshot, which shares them)."""
from __future__ import annotations

from ui.theme.tokens import Tokens
from ui.theme.qss.primitives import join_rules, rgba, rule


def rules(tokens: Tokens) -> str:
    p = tokens.palette
    t = tokens.typography
    d = tokens.density
    mono = f'"{t.mono_family}"'
    caption = f"{t.size('caption')}pt"

    # Translucent accent tints read badly on pure-black/white HC surfaces, so
    # high-contrast palettes get solid muted fills instead (VIS-02).
    if p.is_high_contrast:
        hero_bg = p.accent_muted
        insight_bg = p.accent_muted
    else:
        hero_bg = (
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {rgba(p.accent, 0.16)}, stop:1 {rgba(p.accent, 0.04)})"
        )
        insight_bg = rgba(p.accent, 0.08)

    return join_rules([
        rule("QWidget#DashboardCard", {
            "background-color": p.bg_surface,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius}px",
        }),
        rule("QWidget#DashboardCard:hover", {
            "border": f"1px solid {p.bg_hover}",
        }),
        rule("QLabel#DashboardCardTitle", {
            "color": p.text_primary,
            "font-size": f"{t.size('subtitle')}pt",
            "font-weight": "700",
            "background": "transparent",
            "padding": "0px",
        }),
        rule("QWidget#DashboardCard QLabel", {
            "background": "transparent",
        }),

        # Test-result cards: a surface card with a coloured header strip
        # (the header colour is set inline per-card so each box reads distinctly).
        rule("QWidget#ResultCard", {
            "background-color": p.bg_surface,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius}px",
        }),
        rule("QWidget#ResultCard QLabel", {
            "background": "transparent",
        }),
        # Body of a result card — must NOT inherit #Page bg_base from the scroll-area rule.
        rule("QWidget#ResultCardBody", {
            "background-color": p.bg_surface,
            "border-bottom-left-radius": f"{d.radius}px",
            "border-bottom-right-radius": f"{d.radius}px",
        }),
        rule("QWidget#ResultCardBody QLabel", {
            "background": "transparent",
        }),
        # Focus-session companion/timer panels inside the Cards stack.
        rule("QWidget#FocusPanel", {
            "background-color": p.bg_surface,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius}px",
        }),
        rule("QWidget#FocusPanel QLabel", {
            "background": "transparent",
        }),
        rule("QLabel#FocusTimerDisplay", {
            "color": p.text_primary,
            "font-size": f"{t.size('display') * 2}pt",
            "font-weight": "700",
            "background": "transparent",
        }),

        # --- Clay redesign: dashboard hero + stat cards -------------------
        rule("QWidget#HeroCard", {
            "background": hero_bg,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius + 4}px",
        }),
        rule("QWidget#HeroCard QLabel", {"background": "transparent"}),
        rule("QLabel#HeroStatValue", {
            "color": p.text_primary,
            "font-family": mono,
            "font-size": f"{t.size('display')}pt",
            "font-weight": "700",
        }),
        rule('QLabel#HeroStatValue[accent="true"]', {"color": p.accent}),
        rule("QLabel#HeroStatCaption", {
            "color": p.text_secondary,
            "font-size": caption,
            "font-weight": "600",
        }),
        rule("QFrame#HeroDivider", {
            "background-color": p.border,
            "border": "none",
            "max-width": "1px",
        }),
        rule("QLabel#StatCardValue", {
            "color": p.text_primary,
            "font-family": mono,
            "font-size": f"{t.size('h2')}pt",
            "font-weight": "700",
        }),
        rule("QLabel#StatCardCaption", {
            "color": p.text_secondary,
            "font-size": caption,
        }),
        rule("QLabel#DashGreeting", {
            "color": p.text_primary,
            "font-size": f"{t.size('display')}pt",
            "font-weight": "700",
        }),
        rule("QLabel#DashGreetingSub", {
            "color": p.text_secondary,
            "font-size": f"{t.size('subtitle')}pt",
        }),
        # Right-aligned mono percentage (recent-test rows, summaries).
        rule("QLabel#MonoScore", {
            "color": p.text_primary,
            "font-family": mono,
            "font-size": f"{t.size('body')}pt",
            "font-weight": "600",
        }),
        # Thin per-state distribution bars ("Cards by state").
        rule("QProgressBar#StateProgress", {
            "background-color": p.bg_raised,
            "border": "none",
            "border-radius": "3px",
            "min-height": "6px",
            "max-height": "6px",
            "padding-left": "0px",
            "text-align": "center",
        }),
        rule('QProgressBar#StateProgress[state="new"]::chunk', {
            "background-color": p.state_new, "border-radius": "3px",
        }),
        rule('QProgressBar#StateProgress[state="learning"]::chunk', {
            "background-color": p.state_learning, "border-radius": "3px",
        }),
        rule('QProgressBar#StateProgress[state="review"]::chunk', {
            "background-color": p.state_review, "border-radius": "3px",
        }),
        rule('QProgressBar#StateProgress[state="relearning"]::chunk', {
            "background-color": p.state_learning, "border-radius": "3px",
        }),

        # --- Clay redesign: test-results snapshot -------------------------
        rule("QWidget#InsightBox", {
            "background": insight_bg,
            "border": f"1px solid {p.accent}",
            "border-radius": f"{d.radius}px",
        }),
        rule("QWidget#InsightBox QLabel", {"background": "transparent"}),
        rule("QLabel#InsightTitle", {
            "color": p.accent,
            "font-size": caption,
            "font-weight": "700",
        }),
        rule("QLabel#InsightText", {
            "color": p.text_primary,
            "font-size": f"{t.size('body')}pt",
        }),
        rule("QWidget#ScoreStatBox", {
            "background-color": p.bg_raised,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius}px",
        }),
        rule("QWidget#ScoreStatBox QLabel", {"background": "transparent"}),
        rule('QWidget#ScoreStatBox[tone="good"]', {
            "background-color": p.success_muted,
            "border-color": p.success,
        }),
        rule('QWidget#ScoreStatBox[tone="bad"]', {
            "background-color": p.danger_muted,
            "border-color": p.danger,
        }),
        rule("QLabel#ScoreStatValue", {
            "color": p.text_primary,
            "font-family": mono,
            "font-size": f"{t.size('h2')}pt",
            "font-weight": "700",
        }),
        rule("QLabel#ScoreStatCaption", {
            "color": p.text_secondary,
            "font-size": caption,
            "font-weight": "600",
        }),
        # Missed-answer cards with a coloured left edge.
        rule("QWidget#MissedCard", {
            "background-color": p.bg_surface,
            "border": f"1px solid {p.border}",
            "border-left": f"3px solid {p.danger}",
            "border-radius": f"{d.radius_sm}px",
        }),
        rule("QWidget#MissedCard QLabel", {"background": "transparent"}),
        rule("QLabel#AnswerQuote", {
            "color": p.text_secondary,
            "font-size": f"{t.size('body')}pt",
        }),
        rule('QLabel#AnswerQuote[tone="yours"]', {"color": p.danger}),
        rule('QLabel#AnswerQuote[tone="correct"]', {"color": p.success, "font-weight": "600"}),
        rule('QLabel#AnswerQuote[tone="why"]', {"color": p.text_secondary, "font-style": "italic"}),
        # Progress-ring centre labels.
        rule("QLabel#RingValue", {
            "color": p.text_primary,
            "font-family": mono,
            "font-size": f"{t.size('h2')}pt",
            "font-weight": "700",
        }),
        rule("QLabel#RingCaption", {
            "color": p.text_secondary,
            "font-size": caption,
        }),
    ])
