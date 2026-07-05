"""Word-of-the-day pool for the deadline forecast.

A base pool of 50+ entries across three categories (academic / fun / interesting),
plus helpers to resolve the effective pool from user settings (custom words and
selected categories) and to pick a stable daily word.
"""
from __future__ import annotations

CATEGORIES = ("academic", "fun", "interesting")

# (word, definition, category)
BASE_WORDS: list[tuple[str, str, str]] = [
    # --- academic ---
    ("assiduous", "showing great care and effort", "academic"),
    ("lucid", "clear and easy to understand", "academic"),
    ("tenacious", "persistent and determined", "academic"),
    ("diligent", "careful and persistent in work or effort", "academic"),
    ("methodical", "done according to a systematic plan", "academic"),
    ("persevere", "continue steadily despite difficulty", "academic"),
    ("resilient", "recovering quickly from difficulties", "academic"),
    ("cogent", "clear, logical, and convincing", "academic"),
    ("astute", "having keen insight and good judgment", "academic"),
    ("meticulous", "very careful and precise", "academic"),
    ("deliberate", "done with careful consideration", "academic"),
    ("steadfast", "resolutely firm and unwavering", "academic"),
    ("perspicacious", "having a ready insight into things", "academic"),
    ("indefatigable", "persisting tirelessly", "academic"),
    ("sagacious", "having or showing keen mental discernment", "academic"),
    ("circumspect", "wary and unwilling to take risks", "academic"),
    ("erudite", "having or showing great knowledge", "academic"),
    ("assimilate", "take in and understand fully", "academic"),
    ("synthesize", "combine ideas into a coherent whole", "academic"),
    ("discern", "recognize or find out", "academic"),
    ("rigorous", "extremely thorough and careful", "academic"),
    ("coherent", "logical and consistent", "academic"),
    ("empirical", "based on observation or experience", "academic"),
    ("nuance", "a subtle difference in meaning", "academic"),
    ("salient", "most noticeable or important", "academic"),
    ("pragmatic", "dealing with things sensibly and realistically", "academic"),
    ("elucidate", "make something clear; explain", "academic"),
    ("scrupulous", "diligent, thorough, and attentive to detail", "academic"),
    # --- fun ---
    ("serendipity", "a pleasant discovery made by accident", "fun"),
    ("whimsical", "playfully quaint or fanciful", "fun"),
    ("ebullient", "cheerful and full of energy", "fun"),
    ("zest", "great enthusiasm and energy", "fun"),
    ("jubilant", "feeling or expressing great happiness", "fun"),
    ("buoyant", "cheerful and optimistic", "fun"),
    ("frolic", "play and move about cheerfully", "fun"),
    ("gusto", "enjoyment and enthusiasm", "fun"),
    ("effervescent", "vivacious and enthusiastic", "fun"),
    ("quirky", "having peculiar or unexpected traits", "fun"),
    ("vivacious", "attractively lively and animated", "fun"),
    ("plucky", "having or showing determined courage", "fun"),
    # --- interesting ---
    ("petrichor", "the pleasant smell of rain on dry earth", "interesting"),
    ("sonder", "the realization that each passerby has a vivid life", "interesting"),
    ("ephemeral", "lasting for a very short time", "interesting"),
    ("limerence", "the state of being infatuated with someone", "interesting"),
    ("apricity", "the warmth of the sun in winter", "interesting"),
    ("mellifluous", "sweet or musical; pleasant to hear", "interesting"),
    ("susurrus", "a whispering or rustling sound", "interesting"),
    ("halcyon", "denoting a happy, peaceful period", "interesting"),
    ("numinous", "having a strong spiritual or mysterious quality", "interesting"),
    ("ineffable", "too great to be expressed in words", "interesting"),
    ("luminous", "giving off light; bright or shining", "interesting"),
    ("solitude", "the state of being pleasantly alone", "interesting"),
    ("wanderlust", "a strong desire to travel and explore", "interesting"),
    ("eudaimonia", "a state of flourishing and well-being", "interesting"),
]


def resolve_pool(
    custom_words: list[str] | None = None,
    categories: list[str] | None = None,
) -> list[tuple[str, str]]:
    """The effective (word, definition) pool.

    If *custom_words* is non-empty, it wins (each item is ``"word"`` or
    ``"word - definition"`` / ``"word: definition"``). Otherwise the base pool is
    filtered to *categories* (or all categories when none given).
    """
    if custom_words:
        out: list[tuple[str, str]] = []
        for raw in custom_words:
            text = (raw or "").strip()
            if not text:
                continue
            for sep in (" - ", " — ", ": ", " – "):
                if sep in text:
                    word, definition = text.split(sep, 1)
                    out.append((word.strip(), definition.strip()))
                    break
            else:
                out.append((text, ""))
        if out:
            return out

    wanted = set(categories) if categories else set(CATEGORIES)
    return [(w, d) for (w, d, cat) in BASE_WORDS if cat in wanted] or [
        (w, d) for (w, d, _c) in BASE_WORDS
    ]


def word_of_the_day(ordinal: int, pool: list[tuple[str, str]]) -> tuple[str, str]:
    """Pick a stable daily word from *pool* using a day ordinal."""
    if not pool:
        return ("", "")
    return pool[ordinal % len(pool)]
