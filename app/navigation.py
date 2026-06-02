"""The five primary destinations plus Settings (OVERHAUL_PLAN §5)."""
from __future__ import annotations

from enum import Enum


class Destination(Enum):
    DASHBOARD = "Dashboard"
    LIBRARY = "Library"
    CARDS = "Cards"
    TESTS = "Tests"
    SEARCH = "Search"
    SETTINGS = "Settings"

    @property
    def title(self) -> str:
        return self.value


# Primary nav order (Search is grouped under Tools in the sidebar).
PRIMARY: list[Destination] = [
    Destination.DASHBOARD,
    Destination.LIBRARY,
    Destination.CARDS,
    Destination.TESTS,
]
TOOLS: list[Destination] = [Destination.SEARCH]

# Text glyph hints until real icons are added (kept simple + legible).
ICON: dict[Destination, str] = {
    Destination.DASHBOARD: "▤",
    Destination.LIBRARY: "▦",
    Destination.CARDS: "▭",
    Destination.TESTS: "✓",
    Destination.SEARCH: "⌕",
    Destination.SETTINGS: "⚙",
}

# Short helper text shown on each placeholder page until the view is built.
DESCRIPTION: dict[Destination, str] = {
    Destination.DASHBOARD: "Your study overview — what's due, recent activity, quick actions.",
    Destination.LIBRARY: "Your PDF sources — read, highlight, take notes, make cards.",
    Destination.CARDS: "Your decks and flashcards — review with spaced repetition.",
    Destination.TESTS: "Your tests — build questions, take quizzes, review results.",
    Destination.SEARCH: "Search across everything — sources, cards, and questions.",
    Destination.SETTINGS: "Accessibility, appearance, and study preferences.",
}
