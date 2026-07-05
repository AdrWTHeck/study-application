"""Session-based incremental maintenance for the FTS5 ``search_index``.

These helpers operate on a caller-provided SQLAlchemy ``Session`` so a mutation
(creating a note, deleting a question, importing a source) can keep the search
index fresh *inside its own transaction* — no nested sessions, no full rebuild.

The index is only touched once a full build has happened (tracked by the
``search_meta.built`` flag). Before that, incremental calls are no-ops: the next
:meth:`SearchService.ensure_built` does a one-time full rebuild that captures
everything. This keeps a fresh database correct without every caller rebuilding.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

CONTENT_TYPES = ("note", "question", "source", "deadline")


def index_is_built(session: Session) -> bool:
    """True once a full rebuild has stamped the meta flag."""
    try:
        row = session.execute(text("SELECT built FROM search_meta LIMIT 1")).first()
    except Exception:
        return False
    return bool(row and row[0])


def _upsert(session: Session, ctype: str, cid: int, title: str, body: str) -> None:
    session.execute(
        text("DELETE FROM search_index WHERE content_type = :t AND content_id = :i"),
        {"t": ctype, "i": cid},
    )
    session.execute(
        text(
            "INSERT INTO search_index(content_type, content_id, title, body) "
            "VALUES (:t, :i, :ti, :b)"
        ),
        {"t": ctype, "i": cid, "ti": title or "", "b": body or ""},
    )


def remove(session: Session, ctype: str, cid: int) -> None:
    """Drop a single row from the index (after a delete). No-op if not built."""
    if not index_is_built(session):
        return
    session.execute(
        text("DELETE FROM search_index WHERE content_type = :t AND content_id = :i"),
        {"t": ctype, "i": cid},
    )


# -- row builders (shared with the full rebuild) ----------------------------

def note_row(note) -> tuple[str, int, str, str]:
    body = " ".join(v for v in note.values_by_field_name().values() if v)
    title = note.deck.name if note.deck else "Note"
    return ("note", note.id, title, body)


def question_row(question) -> tuple[str, int, str, str]:
    parts = [question.prompt]
    parts += [o.text for o in question.options]
    parts += [a.accepted_text for a in question.answers]
    return ("question", question.id, "Question", " ".join(p for p in parts if p))


def source_row(source) -> tuple[str, int, str, str]:
    seg_text = " ".join(seg.text for seg in source.segments)
    body = f"{seg_text} {source.notes_text or ''}".strip()
    return ("source", source.id, source.title, body)


def deadline_row(deadline) -> tuple[str, int, str, str]:
    return ("deadline", deadline.id, deadline.name, deadline.name)


# -- incremental reindex of a single object ---------------------------------

def reindex_note(session: Session, note) -> None:
    if index_is_built(session):
        _upsert(session, *note_row(note))


def reindex_question(session: Session, question) -> None:
    if index_is_built(session):
        _upsert(session, *question_row(question))


def reindex_source(session: Session, source) -> None:
    if index_is_built(session):
        _upsert(session, *source_row(source))


def reindex_deadline(session: Session, deadline) -> None:
    if index_is_built(session):
        _upsert(session, *deadline_row(deadline))
