"""Dictionary lookup: indexed prefix search + exact lookup + FTS over the
Wiktionary DB, with a WordNet fallback when the DB is absent or has no match.

Replaces the previous fuzzy-everywhere approach: prefix search is an indexed
B-tree range scan (fast, predictable), exactly as intended.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Sense:
    gloss: str
    pos: str | None = None
    examples: list[str] = field(default_factory=list)


@dataclass
class DictionaryResult:
    word: str
    senses: list[Sense]
    source: str  # "wiktionary" | "wordnet"


class DictionaryService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._available = self._db_path.exists() and self._db_path.stat().st_size > 0
        self._has_fts: bool | None = None

    @property
    def available(self) -> bool:
        return self._available

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # -- prefix search (indexed) -------------------------------------------

    def prefix_search(self, prefix: str, limit: int = 20) -> list[str]:
        prefix = prefix.strip()
        if not prefix or not self._available:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT word FROM entries "
                "WHERE word_lower LIKE ? ORDER BY word_lower LIMIT ?",
                (prefix.lower() + "%", limit),
            ).fetchall()
        return [row["word"] for row in rows]

    # -- exact lookup -------------------------------------------------------

    def lookup(self, word: str) -> DictionaryResult | None:
        word = word.strip()
        if not word:
            return None
        if self._available:
            result = self._lookup_db(word)
            if result and result.senses:
                return result
        return self._lookup_wordnet(word)

    def _lookup_db(self, word: str) -> DictionaryResult | None:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT e.pos AS pos, s.gloss AS gloss, s.examples AS examples "
                "FROM entries e JOIN senses s ON s.entry_id = e.id "
                "WHERE e.word_lower = ?",
                (word.lower(),),
            ).fetchall()
        if not rows:
            return None
        senses = [
            Sense(
                gloss=row["gloss"],
                pos=row["pos"],
                examples=row["examples"].split("\n") if row["examples"] else [],
            )
            for row in rows
        ]
        return DictionaryResult(word=word, senses=senses, source="wiktionary")

    # -- definition full-text search ---------------------------------------

    def search_definitions(self, query: str, limit: int = 20) -> list[tuple[str, str]]:
        query = query.strip()
        if not query or not self._available or not self._fts_available():
            return []
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT e.word AS word, s.gloss AS gloss "
                    "FROM senses_fts f "
                    "JOIN senses s ON s.id = f.rowid "
                    "JOIN entries e ON e.id = s.entry_id "
                    "WHERE senses_fts MATCH ? LIMIT ?",
                    (query, limit),
                ).fetchall()
            return [(row["word"], row["gloss"]) for row in rows]
        except sqlite3.OperationalError:
            return []

    def _fts_available(self) -> bool:
        if self._has_fts is None:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='senses_fts'"
                ).fetchone()
            self._has_fts = row is not None
        return self._has_fts

    # -- WordNet fallback ---------------------------------------------------

    def _lookup_wordnet(self, word: str) -> DictionaryResult | None:
        try:
            from nltk.corpus import wordnet as wn
        except Exception:
            return None
        try:
            synsets = wn.synsets(word)
        except Exception:
            # WordNet corpus not downloaded — degrade silently.
            return None
        if not synsets:
            return None
        pos_map = {"n": "noun", "v": "verb", "a": "adjective", "s": "adjective", "r": "adverb"}
        senses = [
            Sense(gloss=s.definition(), pos=pos_map.get(s.pos(), s.pos()), examples=list(s.examples()))
            for s in synsets
            if s.definition()
        ]
        if not senses:
            return None
        return DictionaryResult(word=word, senses=senses, source="wordnet")
