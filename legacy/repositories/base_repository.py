"""Generic CRUD base — all concrete repositories inherit from this."""
from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy.orm import Session

from models.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Provides get, get_all, save, and delete for any mapped class."""

    model_class: type[T]

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, entity_id: int) -> T | None:
        return self._session.get(self.model_class, entity_id)

    def get_all(self) -> list[T]:
        return self._session.query(self.model_class).all()

    def save(self, entity: T) -> T:
        self._session.add(entity)
        self._session.flush()
        return entity

    def delete(self, entity: T) -> None:
        self._session.delete(entity)
        self._session.flush()
