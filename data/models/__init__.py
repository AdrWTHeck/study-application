"""ORM models. Importing this package registers every model on Base.metadata,
so ``Database.create_all()`` builds the full schema."""
from data.models.card import Card
from data.models.deck import Deck
from data.models.note import Note, NoteFieldValue
from data.models.note_type import CardTemplate, Field, NoteType
from data.models.review_log import ReviewLog
from data.models.tag import Tag, deck_tags, note_tags

__all__ = [
    "Card",
    "Deck",
    "Note",
    "NoteFieldValue",
    "CardTemplate",
    "Field",
    "NoteType",
    "ReviewLog",
    "Tag",
    "deck_tags",
    "note_tags",
]
