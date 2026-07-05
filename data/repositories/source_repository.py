from __future__ import annotations

from sqlalchemy import select

from data.models import SourceDocument
from data.repositories.base_repository import BaseRepository


class SourceRepository(BaseRepository[SourceDocument]):
    model = SourceDocument

    def all_ordered(self) -> list[SourceDocument]:
        return list(
            self.session.scalars(
                select(SourceDocument).order_by(SourceDocument.created_at.desc())
            )
        )
