"""Parse pasted/imported text into editable question drafts for bulk creation.

Mirrors the card bulk importer (``domain/cards/bulk_generation_service``) but for
test questions. Three deterministic modes (no AI — every draft is editable):
  * ``short`` — one short-answer question per line: ``prompt | accepted answer``
    (split on tab, ``|``, or comma; extra accepted answers separated by ``/``).
  * ``mcq``   — one multiple-choice question per line:
    ``prompt | *Correct | Wrong | Wrong``  (mark the correct option with a
    leading ``*``; if none is marked, the first option is treated as correct).
  * ``tf``    — one true/false question per line: ``statement | true``
    (true/t/yes/1 ⇒ true; false/f/no/0 ⇒ false).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from data.models import Question
from data.models.testing import MCQ, SHORT_ANSWER, TRUE_FALSE

SHORT = "short"
MCQ_MODE = "mcq"
TF = "tf"

_TRUE_WORDS = {"true", "t", "yes", "y", "1"}
_FALSE_WORDS = {"false", "f", "no", "n", "0"}


@dataclass
class GeneratedQuestionDraft:
    prompt: str
    qtype: str = SHORT_ANSWER
    options: list[tuple[str, bool]] = field(default_factory=list)  # mcq
    accepted: list[str] = field(default_factory=list)              # short answer
    answer: bool = True                                            # true/false
    duplicate: bool = False

    def summary(self) -> str:
        """Short human-readable description of the answer, for the preview."""
        if self.qtype == MCQ:
            correct = next((t for t, c in self.options if c), "")
            return f"✓ {correct}   ({len(self.options)} options)"
        if self.qtype == TRUE_FALSE:
            return "True" if self.answer else "False"
        return ", ".join(self.accepted) or "—"


def _split(line: str) -> list[str]:
    """Split a line on the first delimiter family present (tab, ``|``, comma)."""
    for delim in ("\t", "|"):
        if delim in line:
            return [p.strip() for p in line.split(delim)]
    if "," in line:
        return [p.strip() for p in line.split(",")]
    return [line.strip()]


def parse(text: str, mode: str = SHORT) -> list[GeneratedQuestionDraft]:
    if not text or not text.strip():
        return []
    if mode == MCQ_MODE:
        return _parse_mcq(text)
    if mode == TF:
        return _parse_tf(text)
    return _parse_short(text)


def _parse_short(text: str) -> list[GeneratedQuestionDraft]:
    drafts: list[GeneratedQuestionDraft] = []
    for raw in text.splitlines():
        parts = _split(raw.strip())
        if not parts or not parts[0]:
            continue
        prompt = parts[0]
        answer_blob = parts[1] if len(parts) > 1 else ""
        accepted = [a.strip() for a in answer_blob.split("/") if a.strip()]
        drafts.append(GeneratedQuestionDraft(
            prompt=prompt, qtype=SHORT_ANSWER, accepted=accepted,
        ))
    return drafts


def _parse_mcq(text: str) -> list[GeneratedQuestionDraft]:
    drafts: list[GeneratedQuestionDraft] = []
    for raw in text.splitlines():
        parts = _split(raw.strip())
        if len(parts) < 2 or not parts[0]:
            continue
        prompt = parts[0]
        options: list[tuple[str, bool]] = []
        for opt in parts[1:]:
            if not opt:
                continue
            correct = opt.startswith("*")
            options.append((opt[1:].strip() if correct else opt, correct))
        if not options:
            continue
        if not any(c for _t, c in options):       # none marked → first is correct
            options[0] = (options[0][0], True)
        drafts.append(GeneratedQuestionDraft(prompt=prompt, qtype=MCQ, options=options))
    return drafts


def _parse_tf(text: str) -> list[GeneratedQuestionDraft]:
    drafts: list[GeneratedQuestionDraft] = []
    for raw in text.splitlines():
        parts = _split(raw.strip())
        if not parts or not parts[0]:
            continue
        prompt = parts[0]
        value = (parts[1].lower() if len(parts) > 1 else "true")
        if value in _FALSE_WORDS:
            answer = False
        elif value in _TRUE_WORDS:
            answer = True
        else:
            answer = True  # default to True when ambiguous
        drafts.append(GeneratedQuestionDraft(prompt=prompt, qtype=TRUE_FALSE, answer=answer))
    return drafts


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())


def mark_duplicates(
    session: Session, deck_id: int, drafts: list[GeneratedQuestionDraft]
) -> list[GeneratedQuestionDraft]:
    """Flag drafts whose prompt already exists in *deck_id* or earlier in the batch."""
    existing = {
        _normalize(q.prompt)
        for q in session.scalars(select(Question).where(Question.deck_id == deck_id))
        if q.prompt
    }
    seen: set[str] = set()
    for draft in drafts:
        key = _normalize(draft.prompt)
        draft.duplicate = key in existing or key in seen
        seen.add(key)
    return drafts
