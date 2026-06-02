from __future__ import annotations

from sqlalchemy import select

from data.models import NoteType
from data.repositories.base_repository import BaseRepository


class NoteTypeRepository(BaseRepository[NoteType]):
    model = NoteType

    def all_ordered(self) -> list[NoteType]:
        return list(self.session.scalars(select(NoteType).order_by(NoteType.name)))

    def by_name(self, name: str) -> NoteType | None:
        return self.session.scalar(select(NoteType).where(NoteType.name == name))
