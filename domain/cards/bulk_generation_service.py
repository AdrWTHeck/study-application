"""Parse pasted/imported text into editable card drafts for bulk creation.

Three deterministic parser modes (no AI, learner stays in control — AUT-01):
  * ``pairs`` — one card per line, front/back split on a tab, ``|``, or comma.
  * ``qa``    — ``Q:`` / ``A:`` blocks.
  * ``cloze`` — one cloze card per line containing ``{{c1::…}}`` markup.

The service only *parses* and flags duplicates; the UI previews the drafts and
saves the chosen ones through :class:`NoteService`, so every generated card is a
normal, fully editable note.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from data.models import Note

PAIRS = "pairs"
QA = "qa"
CLOZE = "cloze"

_CLOZE_RE = re.compile(r"\{\{c\d+::", re.IGNORECASE)


@dataclass
class GeneratedCardDraft:
    front: str
    back: str = ""
    kind: str = "basic"            # "basic" | "cloze"
    tags: list[str] = field(default_factory=list)
    duplicate: bool = False        # set by mark_duplicates


def _split_pair(line: str) -> tuple[str, str]:
    """Split a line into (front, back) on the first tab, ``|``, or comma."""
    for delim in ("\t", "|", ","):
        if delim in line:
            front, back = line.split(delim, 1)
            return front.strip(), back.strip()
    return line.strip(), ""


def parse(text: str, mode: str = PAIRS) -> list[GeneratedCardDraft]:
    """Parse *text* into card drafts using *mode*. Empty input → []."""
    if not text or not text.strip():
        return []
    if mode == QA:
        return _parse_qa(text)
    if mode == CLOZE:
        return _parse_cloze(text)
    return _parse_pairs(text)


def _parse_pairs(text: str) -> list[GeneratedCardDraft]:
    drafts: list[GeneratedCardDraft] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        front, back = _split_pair(line)
        if front:
            drafts.append(GeneratedCardDraft(front=front, back=back, kind="basic"))
    return drafts


def _parse_qa(text: str) -> list[GeneratedCardDraft]:
    drafts: list[GeneratedCardDraft] = []
    front: str | None = None
    back_parts: list[str] = []

    def flush() -> None:
        nonlocal front, back_parts
        if front:
            drafts.append(
                GeneratedCardDraft(front=front, back=" ".join(back_parts).strip(), kind="basic")
            )
        front, back_parts = None, []

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("q:"):
            flush()
            front = line[2:].strip()
        elif low.startswith("a:"):
            back_parts.append(line[2:].strip())
        elif front is not None and not back_parts:
            # continuation of the question prompt
            front = f"{front} {line}".strip()
        elif front is not None:
            back_parts.append(line)
    flush()
    return drafts


def _parse_cloze(text: str) -> list[GeneratedCardDraft]:
    drafts: list[GeneratedCardDraft] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line and _CLOZE_RE.search(line):
            drafts.append(GeneratedCardDraft(front=line, back="", kind="cloze"))
    return drafts


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())


def mark_duplicates(
    session: Session, deck_id: int, drafts: list[GeneratedCardDraft]
) -> list[GeneratedCardDraft]:
    """Flag drafts whose front already exists (normalized) in *deck_id*.

    Also flags duplicates *within* the pasted batch so the same card isn't added
    twice in one go.
    """
    existing: set[str] = set()
    for note in session.scalars(select(Note).where(Note.deck_id == deck_id)):
        values = list(note.values_by_field_name().values())
        if values and values[0]:
            existing.add(_normalize(values[0]))

    seen: set[str] = set()
    for draft in drafts:
        key = _normalize(draft.front)
        draft.duplicate = key in existing or key in seen
        seen.add(key)
    return drafts
