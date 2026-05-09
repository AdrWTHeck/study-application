"""Import all models so SQLAlchemy metadata is fully populated before create_all()."""
from .base import Base, init_engine, get_engine, get_session
from .deck import Deck, deck_sources
from .card import Card
from .question import Question
from .question_result import QuestionResult
from .quiz_session import QuizSession
from .source_document import SourceDocument, TextSegment

__all__ = [
    "Base",
    "init_engine",
    "get_engine",
    "get_session",
    "Deck",
    "deck_sources",
    "Card",
    "Question",
    "QuestionResult",
    "QuizSession",
    "SourceDocument",
    "TextSegment",
]
