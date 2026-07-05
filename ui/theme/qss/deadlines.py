"""Deadline view rules — legacy cards, forecast panel, calendar, priority list.

All deadline-specific selectors live here so deadline styling can be edited
without touching any other part of the stylesheet. No rule from this module
duplicates a selector defined elsewhere.
"""
from __future__ import annotations

from ui.theme.tokens import Tokens
from ui.theme.qss.primitives import join_rules, rule


def rules(tokens: Tokens) -> str:
    p = tokens.palette
    t = tokens.typography
    d = tokens.density
    body_pt = f"{t.size('body')}pt"
    caption = f"{t.size('caption')}pt"

    return join_rules([
        # -----------------------------------------------------------------------
        # Legacy deadline cards (kept for future detail view)
        # -----------------------------------------------------------------------
        rule("QWidget#DeadlineCard", {
            "background-color": p.bg_surface,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius}px",
        }),
        rule("QWidget#DeadlineCardFocus", {
            "background-color": p.bg_surface,
            "border": f"1px solid {p.accent}",
            "border-radius": f"{d.radius}px",
        }),
        rule("QWidget#DeadlineCardUrgent", {
            "background-color": p.bg_surface,
            "border": f"1px solid {p.warning}",
            "border-radius": f"{d.radius}px",
        }),
        # Content area — bg_surface with RIGHT-side radius so it doesn't bleed
        # bg_base past the card's outer border-radius (Qt doesn't clip children)
        rule("QWidget#DeadlineCardContent", {
            "background-color": p.bg_surface,
            "border-top-right-radius": f"{d.radius}px",
            "border-bottom-right-radius": f"{d.radius}px",
        }),
        # Left accent strips — only LEFT corners rounded to match the card outline
        rule("QWidget#DeadlineAccentFocus", {
            "background-color": p.accent,
            "border-top-left-radius": f"{d.radius}px",
            "border-bottom-left-radius": f"{d.radius}px",
            "min-width": "5px",
            "max-width": "5px",
        }),
        rule("QWidget#DeadlineAccentUrgent", {
            "background-color": p.warning,
            "border-top-left-radius": f"{d.radius}px",
            "border-bottom-left-radius": f"{d.radius}px",
            "min-width": "5px",
            "max-width": "5px",
        }),
        rule("QWidget#DeadlineAccentNormal", {
            "background-color": p.border,
            "border-top-left-radius": f"{d.radius}px",
            "border-bottom-left-radius": f"{d.radius}px",
            "min-width": "5px",
            "max-width": "5px",
        }),

        # Summary strip (overview mini-stats row)
        rule("QWidget#DeadlineSummaryStrip", {
            "background": "transparent",
        }),
        rule("QWidget#DeadlineMiniStat", {
            "background-color": p.bg_surface,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius}px",
        }),
        rule("QWidget#DeadlineMiniStat:hover", {
            "border": f"1px solid {p.bg_hover}",
        }),
        rule("QLabel#DeadlineMiniStatValue", {
            "color": p.text_primary,
            "font-size": f"{t.size('title')}pt",
            "font-weight": "700",
            "background": "transparent",
        }),
        rule("QLabel#DeadlineMiniStatLabel", {
            "color": p.text_secondary,
            "font-size": caption,
            "font-weight": "600",
            "background": "transparent",
        }),

        # Metric pills
        rule("QWidget#DeadlineMetric", {
            "background-color": p.bg_raised,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius_sm}px",
        }),
        rule("QWidget#DeadlineMetricUrgent", {
            "background-color": p.warning_muted,
            "border": f"1px solid {p.warning}",
            "border-radius": f"{d.radius_sm}px",
        }),
        rule("QWidget#DeadlineMetricSuccess", {
            "background-color": p.success_muted,
            "border": f"1px solid {p.state_review}",
            "border-radius": f"{d.radius_sm}px",
        }),
        rule("QLabel#DeadlineMetricValue", {
            "color": p.text_primary,
            "font-size": body_pt,
            "font-weight": "700",
            "background": "transparent",
        }),
        rule("QLabel#DeadlineMetricLabel", {
            "color": p.text_secondary,
            "font-size": caption,
            "background": "transparent",
        }),

        # Deadline progress bar (thin, percentage as separate label)
        rule("QProgressBar#DeadlineProgress", {
            "background-color": p.bg_raised,
            "border": "none",
            "border-radius": "4px",
            "min-height": "8px",
            "max-height": "8px",
            "font-size": "0pt",
        }),
        rule("QProgressBar#DeadlineProgress::chunk", {
            "background-color": p.accent,
            "border-radius": "4px",
        }),

        # -----------------------------------------------------------------------
        # Deadline Forecast panel — left side
        # -----------------------------------------------------------------------
        rule("QWidget#DeadlineForecastPanel", {
            "background-color": p.bg_base,
        }),
        rule("QLabel#ForecastTitle", {
            "color": p.text_primary,
            "font-size": f"{t.size('section')}pt",
            "font-weight": "700",
            "background": "transparent",
        }),
        rule("QLabel#ForecastSectionLabel", {
            "color": p.text_secondary,
            "font-size": caption,
            "font-weight": "600",
            "background": "transparent",
            "padding-bottom": "2px",
        }),
        rule("QLabel#WordOfDayText", {
            "color": p.text_primary,
            "font-size": body_pt,
            "background": "transparent",
        }),
        rule("QLabel#ForecastSignal", {
            "color": p.text_secondary,
            "font-size": body_pt,
            "background": "transparent",
        }),

        # Relative load rows
        rule("QWidget#ForecastWorkRow", {
            "background": "transparent",
        }),
        rule("QLabel#ForecastWorkName", {
            "color": p.text_primary,
            "font-size": body_pt,
            "background": "transparent",
        }),
        rule("QProgressBar#ForecastWorkBar", {
            "background-color": p.bg_raised,
            "border": "none",
            "border-radius": "4px",
            "min-height": "10px",
            "max-height": "10px",
            "font-size": "0pt",
        }),
        rule("QProgressBar#ForecastWorkBar::chunk", {
            "background-color": p.accent,
            "border-radius": "4px",
        }),
        rule("QLabel#ForecastWorkValue", {
            "color": p.text_secondary,
            "font-size": caption,
            "background": "transparent",
        }),
        rule("QLabel#ForecastWorkTotal", {
            "color": p.text_dim,
            "font-size": caption,
            "background": "transparent",
        }),

        # Calendar pressure map
        rule("QWidget#ForecastCalendarWidget", {
            "background": "transparent",
        }),
        rule("QLabel#ForecastCalDayOfWeek", {
            "color": p.text_dim,
            "font-size": caption,
            "font-weight": "600",
            "background": "transparent",
            "padding": "2px 0px",
        }),
        rule("QLabel#ForecastCalDayNum", {
            "color": p.text_primary,
            "font-size": caption,
            "font-weight": "600",
            "background": "transparent",
        }),
        rule("QLabel#ForecastCalDayNumToday", {
            "color": p.accent,
            "font-size": caption,
            "font-weight": "700",
            "background": "transparent",
        }),
        rule("QLabel#ForecastCalDayNumOtherMonth", {
            "color": p.text_dim,
            "font-size": caption,
            "background": "transparent",
        }),
        rule("QLabel#ForecastCalDue", {
            "color": p.warning,
            "font-size": f"{t.size('caption') - 1}pt",
            "font-weight": "700",
            "background": "transparent",
        }),
        rule("QLabel#ForecastCalMarker", {
            "color": p.text_secondary,
            "font-size": f"{t.size('caption') - 1}pt",
            "background": "transparent",
        }),
        rule("QLabel#ForecastCalMarkerSuccess", {
            "color": p.success,
            "font-size": caption,
            "font-weight": "700",
            "background": "transparent",
        }),
        rule("QLabel#ForecastLegend", {
            "color": p.text_dim,
            "font-size": caption,
            "background": "transparent",
        }),

        # Calendar toggle buttons
        rule("QPushButton#CalToggleActive", {
            "background-color": p.accent_muted,
            "color": p.text_primary,
            "border": f"1px solid {p.accent}",
            "border-radius": f"{d.radius_sm}px",
            "padding": f"3px {d.space(1.5)}px",
            "min-height": "28px",
            "font-size": caption,
            "font-weight": "600",
        }),
        rule("QPushButton#CalToggleInactive", {
            "background-color": "transparent",
            "color": p.text_secondary,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius_sm}px",
            "padding": f"3px {d.space(1.5)}px",
            "min-height": "28px",
            "font-size": caption,
        }),
        rule("QPushButton#CalToggleInactive:hover", {
            "background-color": p.bg_hover,
            "color": p.text_primary,
            "border-color": p.text_secondary,
        }),

        # Column divider between forecast and priority panels
        rule("QWidget#ForecastDivider", {
            "background-color": p.border,
        }),

        # -----------------------------------------------------------------------
        # Priority panel — right side
        # -----------------------------------------------------------------------
        rule("QWidget#DeadlinePriorityPanel", {
            "background-color": p.bg_base,
        }),
        rule("QLabel#PriorityGroupLabel", {
            "color": p.text_dim,
            "font-size": caption,
            "font-weight": "700",
            "background": "transparent",
            "padding-bottom": "2px",
        }),
        rule("QWidget#DeadlinePriorityCard", {
            "background-color": p.bg_surface,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius}px",
        }),
        rule("QWidget#DeadlinePriorityCard:hover", {
            "border-color": p.accent,
        }),
        rule("QLabel#PriorityCardName", {
            "color": p.text_primary,
            "font-size": body_pt,
            "font-weight": "600",
            "background": "transparent",
        }),
        rule("QLabel#PriorityCardMeta", {
            "color": p.text_secondary,
            "font-size": caption,
            "background": "transparent",
        }),
        rule("QLabel#PriorityCardDecks", {
            "color": p.text_dim,
            "font-size": caption,
            "background": "transparent",
        }),
        rule("QPushButton#PriorityCardMenu", {
            "background": "transparent",
            "border": "none",
            "color": p.text_dim,
            "font-size": body_pt,
            "font-weight": "700",
            "padding": "0px",
            "min-height": "24px",
        }),
        rule("QPushButton#PriorityCardMenu:hover", {
            "color": p.text_primary,
            "background-color": p.bg_hover,
            "border-radius": f"{d.radius_sm}px",
        }),
    ])
