"""Grade a response against a question.

Option types (mcq / true_false) are exact-match on the correct option text.
Text types (short_answer / fill_blank) use fuzzy matching (rapidfuzz) against
any accepted answer, with the pass threshold taken from Settings (default 80).
"""
from __future__ import annotations

from rapidfuzz import fuzz

from data.models.testing import OPTION_TYPES


def _norm(text: str | None) -> str:
    return " ".join((text or "").strip().lower().split())


def grade(question, response: str, fuzzy_threshold: int = 80) -> tuple[bool, float]:
    """Return (is_correct, score 0–100)."""
    if question.type in OPTION_TYPES:
        correct = {_norm(o.text) for o in question.options if o.is_correct}
        ok = bool(correct) and _norm(response) in correct
        return ok, (100.0 if ok else 0.0)

    accepted = [a.accepted_text for a in question.answers]
    if not accepted:
        return False, 0.0
    best = max(fuzz.ratio(_norm(response), _norm(a)) for a in accepted)
    return best >= fuzzy_threshold, float(best)
