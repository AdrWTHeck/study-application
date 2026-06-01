from __future__ import annotations

from sqlalchemy import select

from data.models import Note
from data.repositories.base_repository import BaseRepository


class NoteRepository(BaseRepository[Note]):
    model = Note

    def for_deck(self, deck_id: int) -> list[Note]:
        return list(
            self.session.scalars(
                select(Note).where(Note.deck_id == deck_id).order_by(Note.created_at.desc())
            )
        )
