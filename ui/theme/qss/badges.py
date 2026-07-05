"""Chip, pill, and badge labels: urgency tiers, SRS state badges, status pills."""
from __future__ import annotations

from ui.theme.tokens import Tokens
from ui.theme.qss.primitives import join_rules, rule


def rules(tokens: Tokens) -> str:
    p = tokens.palette
    t = tokens.typography
    d = tokens.density
    caption = f"{t.size('caption')}pt"
    pad = f"2px {d.space(1.5)}px"
    pill_pad = f"1px {d.space(1)}px"
    radius = f"{d.radius_sm}px"

    return join_rules([
        # Urgency chips (text-only, VIS-03: no info by color alone)
        rule("QLabel#UrgentChip", {
            "color": p.warning,
            "font-size": caption,
            "font-weight": "700",
        }),
        rule("QLabel#SoonChip", {
            "color": p.text_secondary,
            "font-size": caption,
        }),
        rule("QLabel#DeadlineUrgencyChip", {
            "color": p.warning,
            "background-color": p.warning_muted,
            "border": f"1px solid {p.warning}",
            "border-radius": radius,
            "padding": pill_pad,
            "font-size": caption,
            "font-weight": "700",
        }),

        # SRS state text badges
        rule("QLabel#StateBadgeNew", {
            "color": p.state_new,
            "font-weight": "700",
            "font-size": caption,
        }),
        rule("QLabel#StateBadgeLearning", {
            "color": p.state_learning,
            "font-weight": "700",
            "font-size": caption,
        }),
        rule("QLabel#StateBadgeReview", {
            "color": p.state_review,
            "font-weight": "700",
            "font-size": caption,
        }),

        # Rounded SRS state pills (clay redesign: muted fill + state text).
        rule("QLabel#StatePillNew", {
            "color": p.state_new,
            "background-color": p.info_muted,
            "border": f"1px solid {p.state_new}",
            "border-radius": f"{d.space(1.25)}px",
            "padding": pill_pad,
            "font-size": caption,
            "font-weight": "700",
        }),
        rule("QLabel#StatePillLearning", {
            "color": p.state_learning,
            "background-color": p.warning_muted,
            "border": f"1px solid {p.state_learning}",
            "border-radius": f"{d.space(1.25)}px",
            "padding": pill_pad,
            "font-size": caption,
            "font-weight": "700",
        }),
        rule("QLabel#StatePillReview", {
            "color": p.state_review,
            "background-color": p.success_muted,
            "border": f"1px solid {p.state_review}",
            "border-radius": f"{d.space(1.25)}px",
            "padding": pill_pad,
            "font-size": caption,
            "font-weight": "700",
        }),
        # Mono per-deck count pill in the deck list.
        rule("QLabel#DeckCountPill", {
            "color": p.text_secondary,
            "background-color": p.bg_raised,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.space(1.25)}px",
            "padding": pill_pad,
            "font-family": f'"{t.mono_family}"',
            "font-size": caption,
            "font-weight": "600",
        }),

        # Deadline status badges — ON TRACK / BEHIND / REST DAY / NOT STARTED / ALL DONE / OVERDUE
        rule("QLabel#StatusBadgeOnTrack", {
            "color": p.state_review,
            "background-color": p.success_muted,
            "border": f"1px solid {p.state_review}",
            "border-radius": radius,
            "padding": pad,
            "font-size": caption,
            "font-weight": "700",
        }),
        rule("QLabel#StatusBadgeBehind", {
            "color": p.warning,
            "background-color": p.warning_muted,
            "border": f"1px solid {p.warning}",
            "border-radius": radius,
            "padding": pad,
            "font-size": caption,
            "font-weight": "700",
        }),
        rule("QLabel#StatusBadgeRestDay", {
            "color": p.text_secondary,
            "background-color": p.bg_hover,
            "border": f"1px solid {p.border}",
            "border-radius": radius,
            "padding": pad,
            "font-size": caption,
            "font-weight": "700",
        }),
        rule("QLabel#StatusBadgeNotStarted", {
            "color": p.text_dim,
            "background-color": p.bg_hover,
            "border": f"1px solid {p.border}",
            "border-radius": radius,
            "padding": pad,
            "font-size": caption,
            "font-weight": "700",
        }),
        rule("QLabel#StatusBadgeAllDone", {
            "color": p.state_review,
            "background-color": p.success_muted,
            "border": f"1px solid {p.state_review}",
            "border-radius": radius,
            "padding": pad,
            "font-size": caption,
            "font-weight": "700",
        }),
        rule("QLabel#StatusBadgeOverdue", {
            "color": p.danger,
            "background-color": p.danger_muted,
            "border": f"1px solid {p.danger}",
            "border-radius": radius,
            "padding": pad,
            "font-size": caption,
            "font-weight": "700",
        }),

        # Compact status pills (smaller padding variant of the badges above)
        rule("QLabel#StatusPillPending", {
            "color": p.text_secondary,
            "background-color": p.bg_hover,
            "border": f"1px solid {p.border}",
            "border-radius": radius,
            "padding": pill_pad,
            "font-size": caption,
            "font-weight": "700",
        }),
        rule("QLabel#StatusPillDone", {
            "color": p.state_review,
            "background-color": p.success_muted,
            "border": f"1px solid {p.state_review}",
            "border-radius": radius,
            "padding": pill_pad,
            "font-size": caption,
            "font-weight": "700",
        }),
        rule("QLabel#StatusPillOverdue", {
            "color": p.warning,
            "background-color": p.warning_muted,
            "border": f"1px solid {p.warning}",
            "border-radius": radius,
            "padding": pill_pad,
            "font-size": caption,
            "font-weight": "700",
        }),
        rule("QLabel#StatusPillUrgent", {
            "color": p.state_learning,
            "background-color": p.warning_muted,
            "border": f"1px solid {p.state_learning}",
            "border-radius": radius,
            "padding": pill_pad,
            "font-size": caption,
            "font-weight": "700",
        }),
    ])
