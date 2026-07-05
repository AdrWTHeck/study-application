"""Map struggled test questions to the note cards that teach the same material.

When a learner gets a question wrong (or scores low), the FTS5 search index is
used to find note cards whose text shares terms with that question, so the app
can *surface* them as "related cards to review". This is a study aid, not a
verdict: by default nothing is rescheduled (AUT-01, learner autonomy). Bringing
related cards forward in the review queue is a separate, explicit, opt-in action
(:meth:`RelatedCardsService.nudge_cards_due_now`) that only ever moves a card's
due date *earlier* and never alters its learned SM-2 state.

See docs/RELATED_CARDS.md.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.clock import now
from data.models import Card, Note, Question, QuestionResult
from data.models.testing import OPTION_TYPES
from domain.search.search_service import SearchService
from domain.srs.srs_base import NEW

# Policy defaults. A result counts as a "struggle" when it was marked incorrect
# OR its score (0-100) is below this bar. The default sits below the grading pass
# mark (80), so by default only wrong answers surface; raising it lets "barely
# correct" answers surface too (e.g. under partial-credit grading).
DEFAULT_LOW_SCORE = 60.0
DEFAULT_PER_QUESTION = 5

_TAG_RE = re.compile(r"<[^>]+>")


def _strip(value: str | None) -> str:
    """Flatten note/question rich text to plain words for previews + querying."""
    return " ".join(_TAG_RE.sub(" ", value or "").split())


@dataclass(frozen=True)
class RelatedCard:
    """One related note (the unit the FTS index keys on) plus its cards.

    A note generates one or more cards (e.g. Basic+Reversed -> 2) that share the
    note's deck. ``card_ids`` is every card the note generated -- what a reschedule
    nudge acts on -- while ``preview``/``deck_name`` drive the surfaced row.
    """

    note_id: int
    deck_id: int
    deck_name: str
    preview: str
    card_ids: tuple[int, ...]
    is_source: bool = False  # exact link: the question was generated from this card


@dataclass(frozen=True)
class QuestionStruggle:
    """A question the learner struggled with, and the cards related to it."""

    question_id: int
    prompt: str
    score: float
    miss_count: int            # times this question was missed across all sessions
    related: list[RelatedCard]


class RelatedCardsService:
    def __init__(
        self,
        session: Session,
        search: SearchService,
        *,
        low_score_threshold: float = DEFAULT_LOW_SCORE,
        per_question: int = DEFAULT_PER_QUESTION,
    ) -> None:
        self.session = session
        self.search = search
        self.low_score_threshold = low_score_threshold
        self.per_question = per_question

    # -- term extraction ----------------------------------------------------

    def question_terms(self, question: Question) -> str:
        """Text mined from a question to find related notes: its prompt, any
        accepted answers, and (for choice questions) the *correct* option text.
        Distractors are excluded so a wrong option can't pull in unrelated notes.
        """
        parts: list[str] = [question.prompt]
        parts += [a.accepted_text for a in question.answers]
        if question.type in OPTION_TYPES:
            parts += [o.text for o in question.options if o.is_correct]
        return _strip(" ".join(p for p in parts if p))

    # -- struggle detection -------------------------------------------------

    def is_struggle(self, result: QuestionResult) -> bool:
        return (not result.is_correct) or (result.score < self.low_score_threshold)

    def miss_count(self, question_id: int) -> int:
        """How many times this question has ever been answered incorrectly -- the
        'repeatedly gets it wrong' signal used to rank severity."""
        return self.session.scalar(
            select(func.count())
            .select_from(QuestionResult)
            .where(
                QuestionResult.question_id == question_id,
                QuestionResult.is_correct.is_(False),
            )
        ) or 0

    # -- related lookup -----------------------------------------------------

    def related_for_question(self, question: Question) -> list[RelatedCard]:
        related: list[RelatedCard] = []
        exclude: set[int] = set()

        # 1) Exact link: a question generated from a card (card->question bridge)
        #    is definitionally about that card -- surface it first, flagged.
        if question.source_card_id is not None:
            card = self.session.get(Card, question.source_card_id)
            if card is not None and card.note is not None and card.note.cards:
                related.append(self._note_to_related(card.note, is_source=True))
                exclude.add(card.note_id)

        # 2) Fuzzy links: notes whose text shares terms with the question.
        hits = self.search.related_notes(
            self.question_terms(question),
            limit=self.per_question,
            exclude_note_ids=tuple(exclude),
        )
        for hit in hits:
            note = self.session.get(Note, hit.id)
            if note is None or not note.cards:
                continue  # only notes that actually have studyable cards
            related.append(self._note_to_related(note))
            if len(related) >= self.per_question:
                break
        return related

    def _note_to_related(self, note: Note, *, is_source: bool = False) -> RelatedCard:
        return RelatedCard(
            note_id=note.id,
            deck_id=note.deck_id,
            deck_name=note.deck.name if note.deck else "Deck",
            preview=self._preview(note),
            card_ids=tuple(card.id for card in note.cards),
            is_source=is_source,
        )

    def _preview(self, note: Note) -> str:
        values = note.values_by_field_name()
        fields = note.note_type.fields if note.note_type else []
        for fld in fields:  # NoteType.fields is ordered by ordinal
            text = _strip(values.get(fld.name, ""))
            if text:
                return text[:80]
        for text in (_strip(v) for v in values.values()):
            if text:
                return text[:80]
        return "(empty note)"

    # -- orchestration ------------------------------------------------------

    def suggestions_for_session(self, session_id: int) -> list[QuestionStruggle]:
        """Struggled questions in a finished quiz, each with its related cards.

        Pure read: this NEVER changes scheduling (AUT-01). Questions with no
        related cards are omitted (nothing to suggest). Ordered most-missed
        first, then lowest score, so the learner sees their weakest spots first.
        """
        struggles: list[QuestionStruggle] = []
        seen: set[int] = set()
        results = self.session.scalars(
            select(QuestionResult)
            .where(QuestionResult.session_id == session_id)
            .order_by(QuestionResult.id)
        )
        for result in results:
            if result.question_id in seen or not self.is_struggle(result):
                continue
            seen.add(result.question_id)
            question = self.session.get(Question, result.question_id)
            if question is None:
                continue
            related = self.related_for_question(question)
            if not related:
                continue
            struggles.append(
                QuestionStruggle(
                    question_id=question.id,
                    prompt=_strip(question.prompt),
                    score=result.score,
                    miss_count=self.miss_count(question.id),
                    related=related,
                )
            )
        struggles.sort(key=lambda s: (-s.miss_count, s.score))
        return struggles

    @staticmethod
    def all_card_ids(struggles: list[QuestionStruggle]) -> list[int]:
        """Every related card id across *struggles*, de-duplicated, order kept."""
        ids: list[int] = []
        for struggle in struggles:
            for card in struggle.related:
                ids.extend(card.card_ids)
        return list(dict.fromkeys(ids))

    # -- opt-in reschedule --------------------------------------------------

    def nudge_cards_due_now(
        self, card_ids: Iterable[int], *, at: datetime | None = None
    ) -> int:
        """Opt-in only: bring *card_ids* forward so they appear in the next review.

        Moves a card's due date *earlier* (never later), skips New cards (already
        surfaced), and never touches ease/interval/state/reps -- so it changes
        *when* a card is seen, not the memory model's record of how well it's
        known. Returns how many cards were actually moved.

        Callers MUST gate this behind explicit user consent; it is never run
        automatically (AUT-01).
        """
        moment = at or now()
        changed = 0
        for card_id in dict.fromkeys(card_ids):
            card = self.session.get(Card, card_id)
            if card is None or card.srs_state == NEW:
                continue
            if card.due is not None and card.due > moment:
                card.due = moment
                changed += 1
        self.session.flush()
        return changed
