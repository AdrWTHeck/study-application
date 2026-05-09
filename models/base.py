"""SQLAlchemy declarative base and engine management."""
from __future__ import annotations

from sqlalchemy import Engine, event
from sqlalchemy import create_engine as _create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


class Base(DeclarativeBase):
    pass


def init_engine(db_path: str) -> Engine:
    """Create the SQLAlchemy engine for *db_path* and register pragma listeners.

    Must be called once at startup before any repository or ORM operation.
    Returns the engine so callers can pass it to backup utilities.
    """
    global _engine, _SessionLocal

    _engine = _create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(_engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _connection_record) -> None:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.close()

    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Database engine not initialised — call init_engine() first.")
    return _engine


def get_session() -> Session:
    if _SessionLocal is None:
        raise RuntimeError("Database not initialised — call init_engine() first.")
    return _SessionLocal()
