"""Generate a line-completion cloze deck from a poem, lyrics, or a speech.

Each line becomes a card whose cloze hides the *next* line, drilling recall of
how the piece progresses; weak lines surface fast under SRS. Uses the built-in
Cloze note type (fields Text + Extra).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from data.repositories.note_type_repository import NoteTypeRepository
from domain.notes.note_service import NoteService
from domain.srs.srs_base import SrsEngine


def line_completion_values(text: str) -> list[dict[str, str]]:
    """For each adjacent line pair, a Cloze note hiding the following line."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    values: list[dict[str, str]] = []
    for current, following in zip(lines, lines[1:]):
        values.append({"Text": f"{current}<br>{{{{c1::{following}}}}}", "Extra": ""})
    return values


class ClozeDeckBuilder:
    def __init__(self, session: Session, engine: SrsEngine) -> None:
        self.session = session
        self.engine = engine

    def build(self, deck_id: int, text: str) -> int:
        """Create line-completion cloze notes in *deck_id*; return how many."""
        cloze_type = NoteTypeRepository(self.session).by_name("Cloze")
        if cloze_type is None:
            return 0
        notes = NoteService(self.session, self.engine)
        count = 0
        for values in line_completion_values(text):
            notes.create_note(deck_id, cloze_type.id, values)
            count += 1
        return count
