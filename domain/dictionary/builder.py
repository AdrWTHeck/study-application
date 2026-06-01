"""Build the optimized Wiktionary SQLite DB from kaikki.org JSON entries.

Schema (selective fields only — word, pos, gloss, examples):
    entries(id, word, word_lower, pos)         + index on word_lower (prefix search)
    senses(id, entry_id, gloss, examples)      + index on entry_id
    senses_fts FTS5(gloss)                      external-content over senses (if available)

The builder accepts any iterable of kaikki-style dicts, so it is fully testable
with synthetic data; ``build_from_jsonl`` is the convenience reader for the real
dump. FTS5 is created opportunistically and skipped gracefully if the local
sqlite lacks it.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterable, Iterator
from pathlib import Path

logger = logging.getLogger(__name__)


def _create_schema(conn: sqlite3.Connection) -> bool:
    conn.executescript(
        """
        DROP TABLE IF EXISTS senses;
        DROP TABLE IF EXISTS entries;
        CREATE TABLE entries (
            id         INTEGER PRIMARY KEY,
            word       TEXT NOT NULL,
            word_lower TEXT NOT NULL,
            pos        TEXT
        );
        CREATE INDEX idx_entries_word_lower ON entries(word_lower);
        CREATE TABLE senses (
            id        INTEGER PRIMARY KEY,
            entry_id  INTEGER NOT NULL REFERENCES entries(id),
            gloss     TEXT NOT NULL,
            examples  TEXT
        );
        CREATE INDEX idx_senses_entry ON senses(entry_id);
        """
    )
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE senses_fts USING fts5("
            "gloss, content='senses', content_rowid='id')"
        )
        return True
    except sqlite3.OperationalError:
        logger.warning("FTS5 not available in this sqlite build — definition search disabled.")
        return False


def _gloss_of(sense: dict) -> str:
    glosses = sense.get("glosses") or sense.get("raw_glosses") or []
    if isinstance(glosses, list):
        return "; ".join(g for g in glosses if g).strip()
    return str(glosses).strip()


def _examples_of(sense: dict) -> str | None:
    examples = [ex.get("text") for ex in sense.get("examples", []) if ex.get("text")]
    return "\n".join(examples) if examples else None


def build_dictionary(entries: Iterable[dict], db_path: Path | str) -> int:
    """Build the DB from kaikki-style entry dicts. Returns the sense count."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    try:
        has_fts = _create_schema(conn)
        cur = conn.cursor()
        sense_count = 0
        for entry in entries:
            word = (entry.get("word") or "").strip()
            if not word:
                continue
            cur.execute(
                "INSERT INTO entries (word, word_lower, pos) VALUES (?, ?, ?)",
                (word, word.lower(), entry.get("pos")),
            )
            entry_id = cur.lastrowid
            for sense in entry.get("senses", []):
                gloss = _gloss_of(sense)
                if not gloss:
                    continue
                cur.execute(
                    "INSERT INTO senses (entry_id, gloss, examples) VALUES (?, ?, ?)",
                    (entry_id, gloss, _examples_of(sense)),
                )
                sense_count += 1
        if has_fts:
            conn.execute("INSERT INTO senses_fts(senses_fts) VALUES('rebuild')")
        conn.commit()
        logger.info("Built dictionary: %d senses at %s", sense_count, db_path)
        return sense_count
    finally:
        conn.close()


def _read_jsonl(path: Path) -> Iterator[dict]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


def build_from_jsonl(jsonl_path: Path | str, db_path: Path | str) -> int:
    """Build the DB from a kaikki JSONL dump (one JSON object per line)."""
    return build_dictionary(_read_jsonl(Path(jsonl_path)), db_path)
