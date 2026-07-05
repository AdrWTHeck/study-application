"""App-wide search via a persistent, incrementally maintained SQLite FTS5 index.

Indexes notes (flattened field values), questions (prompt + options + answers),
sources (extracted text + notes), and deadlines. The index persists across
sessions: it is built **once** (:meth:`ensure_built`) and then kept fresh by
incremental upserts/removes (see :mod:`domain.search.indexer`) fired from the
services that mutate data. :meth:`rebuild` (a.k.a. :meth:`repair`) does a full
drop-and-repopulate for the Settings "repair index" action.

``search`` runs a prefix-OR FTS5 query and returns ranked results with a snippet.
"""
from __future__ import annotations

import logging
import re

from sqlalchemy import select, text

from data.db import Database
from data.models import Note, Question, SourceDocument
from data.models.deadline import Deadline
from domain.dictionary.service import DictionaryService
from domain.search import indexer

logger = logging.getLogger(__name__)

_CREATE = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5("
    "content_type, content_id UNINDEXED, title, body)"
)
_CREATE_META = "CREATE TABLE IF NOT EXISTS search_meta (built INTEGER NOT NULL DEFAULT 0)"


class SearchResult:
    __slots__ = ("type", "id", "title", "snippet")

    def __init__(self, type_: str, id_: int, title: str, snippet: str) -> None:
        self.type = type_
        self.id = id_
        self.title = title
        self.snippet = snippet


class SearchService:
    def __init__(self, db: Database, dictionary_service: DictionaryService | None = None) -> None:
        self.db = db
        self.dictionary_service = dictionary_service

    def ensure_built(self) -> None:
        """Build the index once, then leave it to incremental maintenance.

        Cheap to call repeatedly: it no-ops once the ``search_meta.built`` flag
        is set. Use this from hot paths (Search view, related-cards) instead of
        :meth:`rebuild`, which always does a full repopulate.
        """
        with self.db.session() as session:
            session.execute(text(_CREATE_META))
            if indexer.index_is_built(session):
                return
        self.rebuild()

    def rebuild(self) -> None:
        """Full drop-and-repopulate. Backs the Settings 'repair index' action."""
        with self.db.session() as session:
            session.execute(text("DROP TABLE IF EXISTS search_index"))
            session.execute(text(_CREATE))
            session.execute(text(_CREATE_META))

            rows: list[tuple[str, int, str, str]] = []
            for note in session.scalars(select(Note)):
                rows.append(indexer.note_row(note))
            for question in session.scalars(select(Question)):
                rows.append(indexer.question_row(question))
            for source in session.scalars(select(SourceDocument)):
                rows.append(indexer.source_row(source))
            for dl in session.scalars(select(Deadline)):
                rows.append(indexer.deadline_row(dl))

            for content_type, content_id, title, body in rows:
                session.execute(
                    text(
                        "INSERT INTO search_index(content_type, content_id, title, body) "
                        "VALUES (:t, :i, :ti, :b)"
                    ),
                    {"t": content_type, "i": content_id, "ti": title, "b": body},
                )

            # Stamp the built flag (single-row meta table).
            session.execute(text("DELETE FROM search_meta"))
            session.execute(text("INSERT INTO search_meta(built) VALUES (1)"))

    # Backwards-friendly alias for the Settings "Repair search index" action.
    def repair(self) -> None:
        self.rebuild()

    def search(self, query: str, limit: int = 40) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []

        out: list[SearchResult] = []
        if self.dictionary_service is not None:
            for word in self.dictionary_service.prefix_search(query, limit=10):
                out.append(SearchResult("dictionary", 0, word, ""))

        fts_query = self._fts_query(query)
        if not fts_query:
            return out[:limit]

        rem = max(0, limit - len(out))
        if rem <= 0:
            return out[:limit]

        with self.db.session() as session:
            try:
                rows = session.execute(
                    text(
                        "SELECT content_type, content_id, title, "
                        "snippet(search_index, 3, '[', ']', '…', 12) AS snip "
                        "FROM search_index WHERE search_index MATCH :q LIMIT :lim"
                    ),
                    {"q": fts_query, "lim": rem},
                ).all()
            except Exception:
                logger.exception("Search failed; index may be missing.")
                return out[:limit]
        out.extend(SearchResult(r.content_type, r.content_id, r.title, r.snip) for r in rows)
        return out[:limit]

    def related_notes(
        self, query: str, limit: int = 5, exclude_note_ids: tuple[int, ...] = ()
    ) -> list[SearchResult]:
        """Notes whose indexed text best matches *query*, ranked by FTS5 bm25.

        Backs the related-cards feature: it maps a missed test question to the
        note cards that teach the same material. Restricted to ``note`` rows and
        ordered by relevance (``ORDER BY rank``). Returns at most *limit* notes,
        skipping any id in *exclude_note_ids* (e.g. an exact source-card link
        already surfaced).
        """
        fts_query = self._fts_query(query)
        if not fts_query:
            return []
        excluded = set(exclude_note_ids)
        with self.db.session() as session:
            try:
                rows = session.execute(
                    text(
                        "SELECT content_id, title, "
                        "snippet(search_index, 3, '[', ']', '…', 12) AS snip "
                        "FROM search_index "
                        "WHERE content_type = 'note' AND search_index MATCH :q "
                        "ORDER BY rank LIMIT :lim"
                    ),
                    {"q": fts_query, "lim": limit + len(excluded)},
                ).all()
            except Exception:
                logger.exception("Related-notes query failed; index may be missing.")
                return []
        out: list[SearchResult] = []
        for r in rows:
            if r.content_id in excluded:
                continue
            out.append(SearchResult("note", r.content_id, r.title, r.snip))
            if len(out) >= limit:
                break
        return out

    @staticmethod
    def _fts_query(query: str) -> str:
        terms = re.findall(r"\w+", query.lower())
        return " OR ".join(f"{t}*" for t in terms)
