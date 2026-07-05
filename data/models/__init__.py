"""ORM models. Importing this package registers every model on Base.metadata,
so ``Database.create_all()`` builds the full schema."""
from data.models.card import Card
from data.models.deadline import Deadline, VacationDay, deadline_decks
from data.models.deck import Deck
from data.models.note import Note, NoteFieldValue
from data.models.note_flag import NoteFlag, note_flag_assignments
from data.models.note_type import CardTemplate, Field, NoteType
from data.models.review_log import ReviewLog
from data.models.source import (
    Bookmark,
    SourceDocument,
    TextSegment,
    deck_sources,
    source_tags,
)
from data.models.tag import Tag, deck_tags, note_tags
from data.models.achievement import Achievement
from data.models.companion import CompanionState, DiagnosticItem
from data.models.testing import (
    Question,
    QuestionAnswer,
    QuestionOption,
    QuestionResult,
    QuizSession,
)

__all__ = [
    "Achievement",
    "CompanionState",
    "DiagnosticItem",
    "Card",
    "Deadline",
    "VacationDay",
    "deadline_decks",
    "Deck",
    "Note",
    "NoteFieldValue",
    "NoteFlag",
    "note_flag_assignments",
    "CardTemplate",
    "Field",
    "NoteType",
    "ReviewLog",
    "SourceDocument",
    "TextSegment",
    "Bookmark",
    "deck_sources",
    "source_tags",
    "Tag",
    "deck_tags",
    "note_tags",
    "Question",
    "QuestionOption",
    "QuestionAnswer",
    "QuizSession",
    "QuestionResult",
]
