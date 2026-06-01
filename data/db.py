"""SQLAlchemy engine + session management.

Unlike the previous iteration's module-level globals, the engine and session
factory live on a :class:`Database` instance — no hidden global state, so tests
can spin up isolated databases freely. WAL + foreign keys are enabled on every
connection via a connect listener.
"""
from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all ORM models (registered in data/models/)."""


class Database:
    def __init__(self, db_path: Path | str) -> None:
        self.path = str(db_path)
        self.engine = create_engine(
            f"sqlite:///{self.path}",
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(self.engine, "connect")
        def _set_pragmas(dbapi_conn, _record) -> None:  # noqa: ANN001
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.close()

        self._sessionmaker = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    def new_session(self) -> Session:
        """Return a raw session the caller is responsible for closing."""
        return self._sessionmaker()

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Session scope that commits on success and rolls back on error."""
        session = self._sessionmaker()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()
