"""Prewritten encouragement response pools for the study companion (§6.3).

All responses are supportive and non-pressuring — the companion encourages,
it does not shame or create urgency.
"""
from __future__ import annotations

import random

RESPONSES: dict[str, list[str]] = {
    "session_complete": [
        "Great session! Your companion is proud of you.",
        "You finished a full focus block — that takes dedication.",
        "Well done. Consistency is how mastery is built.",
        "Another session done. You're showing up and that matters.",
    ],
    "improved_confidence": [
        "Your confidence improved — you're getting stronger with these concepts.",
        "Improvement spotted! Keep reviewing and the knowledge will stick.",
        "You rated yourself higher at the end. That's real progress.",
    ],
    "reviewed_due_cards": [
        "Cards reviewed! Your future self is grateful.",
        "Your streak grows with every review. Nice work.",
        "Showing up for your cards today means fewer to catch up on tomorrow.",
    ],
    "low_score_support": [
        "That's okay — reviewing is exactly how we learn.",
        "Every review makes the concept a little clearer. Keep going.",
        "Hard material takes time. You're doing the right thing.",
        "It doesn't need to be perfect today. Come back tomorrow.",
    ],
    "returning_after_gap": [
        "Welcome back! Your companion missed you.",
        "You're here — and that's what matters most.",
        "Starting again is the hardest part, and you did it.",
    ],
    "streak_continued": [
        "Streak maintained! One more day of consistency.",
        "Another day added to your streak. Keep the momentum.",
    ],
    "gentle_break": [
        "Take a breath — you've earned this break.",
        "Rest is part of studying well. Step away for a moment.",
        "Breaks help consolidate memory. This is productive rest.",
    ],
    "focus_start": [
        "Focus time. You've got this.",
        "Your companion is studying alongside you.",
        "Let's make this block count.",
    ],
}


class EncouragementService:
    def pick(self, category: str) -> str:
        """Return a random response from the given category, or a fallback."""
        options = RESPONSES.get(category, [])
        if not options:
            return "Keep going — you're doing great."
        return random.choice(options)
