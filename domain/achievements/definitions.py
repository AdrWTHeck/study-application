"""Achievement registry.

Each achievement is a simple "reach N of some metric" goal, which keeps both the
unlock check and the progress display uniform. Metrics are gathered once per
evaluation (see :class:`AchievementMetrics`) so definitions never touch the DB.

Visibility:
  * Normal locked achievements show their goal and progress (motivating).
  * ``hidden`` achievements (rare/hard) show only a locked mystery box until
    they're earned.
"""
from __future__ import annotations

from dataclasses import dataclass

# Categories (used for grouping/labels).
GETTING_STARTED = "Getting started"
CARDS = "Cards"
LIBRARY = "Library"
TESTS = "Tests"
FOCUS = "Focus"
CONSISTENCY = "Consistency"
MASTERY = "Mastery"
HIDDEN = "Hidden challenges"


@dataclass
class AchievementMetrics:
    review_count: int = 0
    deck_count: int = 0
    note_count: int = 0
    source_count: int = 0
    highlight_count: int = 0
    bookmark_count: int = 0
    question_count: int = 0
    quiz_count: int = 0
    perfect_quizzes: int = 0
    study_days: int = 0
    streak: int = 0
    companion_level: int = 1


@dataclass(frozen=True)
class AchievementDef:
    code: str
    title: str
    symbol: str
    description: str
    category: str
    metric: str          # attribute on AchievementMetrics
    target: int
    hidden: bool = False
    rarity: str = "common"   # common | rare | legendary

    def current(self, m: AchievementMetrics) -> int:
        return int(getattr(m, self.metric, 0))

    def is_unlocked(self, m: AchievementMetrics) -> bool:
        return self.current(m) >= self.target

    def progress_text(self, m: AchievementMetrics) -> str:
        return f"{min(self.current(m), self.target)}/{self.target}"

    def fraction(self, m: AchievementMetrics) -> float:
        return min(1.0, self.current(m) / self.target) if self.target else 1.0


DEFINITIONS: list[AchievementDef] = [
    # ── Getting started ──
    AchievementDef("first-review", "First Review", "🌱",
                   "Complete your first card review.", GETTING_STARTED, "review_count", 1),
    AchievementDef("first-deck", "First Deck", "🗂️",
                   "Create your first study deck.", GETTING_STARTED, "deck_count", 1),
    AchievementDef("first-note", "First Card", "🃏",
                   "Create your first card.", GETTING_STARTED, "note_count", 1),
    AchievementDef("first-source", "First Source", "📄",
                   "Import your first source into the Library.", GETTING_STARTED, "source_count", 1),
    AchievementDef("first-question", "First Question", "❓",
                   "Create your first test question.", GETTING_STARTED, "question_count", 1),
    AchievementDef("first-quiz", "First Quiz", "✅",
                   "Complete your first test.", GETTING_STARTED, "quiz_count", 1),

    # ── Cards ──
    AchievementDef("card-collector", "Card Collector", "📇",
                   "Create 20 cards.", CARDS, "note_count", 20),
    AchievementDef("card-curator", "Card Curator", "📚",
                   "Create 50 cards.", CARDS, "note_count", 50, rarity="rare"),
    AchievementDef("card-librarian", "Card Librarian", "🏛️",
                   "Create 200 cards.", CARDS, "note_count", 200, rarity="rare"),
    AchievementDef("deck-builder", "Deck Builder", "🧱",
                   "Create 3 decks.", CARDS, "deck_count", 3),
    AchievementDef("deck-architect", "Deck Architect", "🏗️",
                   "Create 10 decks.", CARDS, "deck_count", 10, rarity="rare"),

    # ── Library ──
    AchievementDef("source-shelf", "Source Shelf", "📰",
                   "Import 5 sources.", LIBRARY, "source_count", 5),
    AchievementDef("source-library", "Reference Library", "🗄️",
                   "Import 20 sources.", LIBRARY, "source_count", 20, rarity="rare"),
    AchievementDef("highlight-helper", "Highlight Helper", "🖍️",
                   "Make your first source highlight.", LIBRARY, "highlight_count", 1),
    AchievementDef("margin-master", "Margin Master", "✍️",
                   "Make 25 highlights.", LIBRARY, "highlight_count", 25, rarity="rare"),
    AchievementDef("highlight-legend", "Highlight Legend", "🌈",
                   "Make 100 highlights.", LIBRARY, "highlight_count", 100, rarity="rare"),
    AchievementDef("bookmarker", "Bookmarker", "🔖",
                   "Bookmark 10 pages.", LIBRARY, "bookmark_count", 10),

    # ── Tests ──
    AchievementDef("question-crafter", "Question Crafter", "🛠️",
                   "Create 10 questions.", TESTS, "question_count", 10),
    AchievementDef("question-forge", "Question Forge", "⚒️",
                   "Create 50 questions.", TESTS, "question_count", 50, rarity="rare"),
    AchievementDef("quiz-regular", "Quiz Regular", "📝",
                   "Complete 10 tests.", TESTS, "quiz_count", 10),
    AchievementDef("quiz-devotee", "Quiz Devotee", "🧪",
                   "Complete 50 tests.", TESTS, "quiz_count", 50, rarity="rare"),
    AchievementDef("flawless", "Flawless", "💯",
                   "Score 100% on a test.", TESTS, "perfect_quizzes", 1),
    AchievementDef("flawless-five", "Perfectionist", "🌟",
                   "Score 100% on 5 tests.", TESTS, "perfect_quizzes", 5, rarity="rare"),

    # ── Focus ──
    AchievementDef("focus-seed", "Focus Seed", "🌳",
                   "Grow your companion to level 2.", FOCUS, "companion_level", 2),
    AchievementDef("focus-grove", "Focus Grove", "🌲",
                   "Grow your companion to level 5.", FOCUS, "companion_level", 5),
    AchievementDef("focus-forest", "Focus Forest", "🏕️",
                   "Grow your companion to level 10.", FOCUS, "companion_level", 10, rarity="rare"),

    # ── Consistency ──
    AchievementDef("steady-sprout", "Steady Sprout", "🔥",
                   "Study three days in a row.", CONSISTENCY, "streak", 3),
    AchievementDef("weekly-warrior", "Weekly Warrior", "📅",
                   "Study seven days in a row.", CONSISTENCY, "streak", 7),
    AchievementDef("fortnight", "Fortnight Focus", "🗓️",
                   "Study fourteen days in a row.", CONSISTENCY, "streak", 14, rarity="rare"),
    AchievementDef("regular-visitor", "Regular Visitor", "🚪",
                   "Study on 10 different days.", CONSISTENCY, "study_days", 10),
    AchievementDef("dedicated", "Dedicated", "🧭",
                   "Study on 30 different days.", CONSISTENCY, "study_days", 30, rarity="rare"),

    # ── Mastery ──
    AchievementDef("review-regular", "Review Regular", "🔁",
                   "Complete 20 card reviews.", MASTERY, "review_count", 20),
    AchievementDef("review-veteran", "Review Veteran", "🎯",
                   "Complete 100 card reviews.", MASTERY, "review_count", 100),
    AchievementDef("review-master", "Review Master", "🥇",
                   "Complete 250 card reviews.", MASTERY, "review_count", 250, rarity="rare"),

    # ── Hidden challenges ──
    AchievementDef("marathon-gardener", "Marathon Gardener", "🏆",
                   "Study 30 days in a row.", HIDDEN, "streak", 30,
                   hidden=True, rarity="legendary"),
    AchievementDef("source-alchemist", "Source Alchemist", "⚗️",
                   "Create 100 cards.", HIDDEN, "note_count", 100,
                   hidden=True, rarity="legendary"),
    AchievementDef("century-scholar", "Century Scholar", "👑",
                   "Complete 500 card reviews.", HIDDEN, "review_count", 500,
                   hidden=True, rarity="legendary"),
    AchievementDef("ancient-oak", "Ancient Oak", "🌳",
                   "Grow your companion to level 20.", HIDDEN, "companion_level", 20,
                   hidden=True, rarity="legendary"),
    AchievementDef("unbroken", "Unbroken", "💎",
                   "Study 100 days in a row.", HIDDEN, "streak", 100,
                   hidden=True, rarity="legendary"),
]
