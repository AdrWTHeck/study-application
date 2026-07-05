"""Dashboard widget registry + per-mode default boards.

Customization is a saved, ordered list of visible widget keys
(``settings["dashboard_widgets"]``). Accessibility-First mode shows a calm,
small default board; Advanced mode shows a denser one. No drag-and-drop — order
comes from the saved list, kept simple and keyboard-friendly.
"""
from __future__ import annotations

from ui.views.dashboard.base import DashboardWidget
from ui.views.dashboard.widgets import (
    CardStatesWidget,
    CompanionWidget,
    DeadlineWidget,
    HeroWidget,
    QuickActionsWidget,
    RecentTestsWidget,
    RetentionWidget,
    StickyNoteWidget,
    StreakWidget,
    StudyWidget,
)

# key → widget class
WIDGETS: dict[str, type[DashboardWidget]] = {
    cls.key: cls
    for cls in (
        HeroWidget,
        StudyWidget,
        RetentionWidget,
        CardStatesWidget,
        RecentTestsWidget,
        DeadlineWidget,
        StreakWidget,
        CompanionWidget,
        StickyNoteWidget,
        QuickActionsWidget,
    )
}

# Human labels for the Settings show/hide list.
WIDGET_LABELS: dict[str, str] = {key: cls.title for key, cls in WIDGETS.items()}

# The hero replaces the small Study card in both defaults (it shows the same
# due/new info plus streak and both study actions). StudyWidget stays
# registered for saved boards that prefer the compact card.
# Accessibility-First default: fewer cards, one thing at a time.
DEFAULT_BOARD_ACCESSIBILITY = [
    "hero",
    "deadline",
    "companion",
    "recent_tests",
    "quick_actions",
]

# Advanced default: denser, with charts and extras.
DEFAULT_BOARD_ADVANCED = [
    "hero",
    "retention",
    "card_states",
    "deadline",
    "companion",
    "recent_tests",
    "streak",
    "sticky_note",
    "quick_actions",
]


def default_board(mode: str) -> list[str]:
    return DEFAULT_BOARD_ADVANCED if mode == "advanced" else DEFAULT_BOARD_ACCESSIBILITY


def resolve_board(settings) -> list[str]:
    """The ordered, validated list of widget keys to show.

    Uses the saved ``dashboard_widgets`` list when present, else the per-mode
    default. Unknown keys (from an older build) are dropped.
    """
    saved = settings.get("dashboard_widgets")
    mode = settings.get("mode")
    keys = saved if isinstance(saved, list) and saved else default_board(mode)
    return [k for k in keys if k in WIDGETS]
