"""Create/edit/delete questions, and the card→question bridge.

The bridge (``card_to_question``) produces a short-answer **draft**
(is_generated_draft=True) linked to the source card — clearly labeled and fully
editable before use (AUT-01). No bulk auto-generation.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from data.models import Card, Question, QuestionAnswer, QuestionOption
from data.models.testing import MCQ, SHORT_ANSWER, TRUE_FALSE
from data.repositories.question_repository import QuestionRepository
from domain.search import indexer


class QuestionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.questions = QuestionRepository(session)

    def _create(self, deck_id, type_, prompt, explanation, is_draft, source_card_id) -> Question:
        question = Question(
            deck_id=deck_id, type=type_, prompt=prompt, explanation=explanation,
            is_generated_draft=is_draft, source_card_id=source_card_id,
        )
        self.session.add(question)
        self.session.flush()
        return question

    def create_mcq(self, deck_id, prompt, options, explanation="",
                   is_draft=False, source_card_id=None) -> Question:
        """options: list of (text, is_correct)."""
        question = self._create(deck_id, MCQ, prompt, explanation, is_draft, source_card_id)
        for i, (text, correct) in enumerate(options):
            question.options.append(QuestionOption(text=text, is_correct=bool(correct), ordinal=i))
        self.session.flush()
        indexer.reindex_question(self.session, question)
        return question

    def create_true_false(self, deck_id, prompt, answer: bool, explanation="") -> Question:
        question = self._create(deck_id, TRUE_FALSE, prompt, explanation, False, None)
        question.options.append(QuestionOption(text="True", is_correct=bool(answer), ordinal=0))
        question.options.append(QuestionOption(text="False", is_correct=not bool(answer), ordinal=1))
        self.session.flush()
        indexer.reindex_question(self.session, question)
        return question

    def create_text(self, deck_id, prompt, accepted, type_=SHORT_ANSWER, explanation="",
                    is_draft=False, source_card_id=None) -> Question:
        question = self._create(deck_id, type_, prompt, explanation, is_draft, source_card_id)
        for text in accepted:
            question.answers.append(QuestionAnswer(accepted_text=text))
        self.session.flush()
        indexer.reindex_question(self.session, question)
        return question

    def card_to_question(self, card: Card, deck_id: int) -> Question:
        """Generate an editable short-answer draft from a card."""
        note_type = card.note.note_type
        fields = sorted(note_type.fields, key=lambda f: f.ordinal) if note_type else []
        values = card.note.values_by_field_name()
        prompt = values.get(fields[0].name, "") if fields else ""
        answer = values.get(fields[1].name, "") if len(fields) > 1 else prompt
        return self.create_text(
            deck_id, prompt, [answer] if answer else [],
            type_=SHORT_ANSWER, is_draft=True, source_card_id=card.id,
        )

    def update(self, question: Question, prompt: str | None = None, explanation: str | None = None,
               options: list | None = None, accepted: list[str] | None = None) -> Question:
        if prompt is not None:
            question.prompt = prompt
        if explanation is not None:
            question.explanation = explanation
        if options is not None:
            question.options.clear()
            for i, (text, correct) in enumerate(options):
                question.options.append(QuestionOption(text=text, is_correct=bool(correct), ordinal=i))
        if accepted is not None:
            question.answers.clear()
            for text in accepted:
                question.answers.append(QuestionAnswer(accepted_text=text))
        question.is_generated_draft = False  # editing confirms a draft
        self.session.flush()
        indexer.reindex_question(self.session, question)
        return question

    def confirm_draft(self, question: Question) -> None:
        question.is_generated_draft = False
        self.session.flush()

    def delete(self, question: Question) -> None:
        question_id = question.id
        self.session.delete(question)
        self.session.flush()
        indexer.remove(self.session, "question", question_id)
