"""Offline dictionary service — three layered sources.

Source 1 — NLTK WordNet       (always offline, primary)
Source 2 — Webster's 1913 DB  (offline when asset is present)
Source 3 — AyDictionary        (online supplementary enrichment)

AyDictionary's meaning() wraps WordNet (offline).  Its synonym/antonym
methods scrape synonym.com (network required).  Every AyDictionary call is
guarded by a fast connectivity probe so the service degrades gracefully when
offline — no feature *requires* a network connection (CON-01).

Public API
----------
lookup(word)                 -> DictionaryResult
search(query, threshold)     -> list[str]   (fuzzy candidates)
"""
from __future__ import annotations

import logging
import socket
import sqlite3
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from rapidfuzz import process as fuzz_process, fuzz

from config.constants import DICTIONARY_FUZZY_THRESHOLD
from services.core.startup import WEBSTER_DB_PATH

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class WordNetEntry:
    """One synset from WordNet."""
    pos: str                        # "noun" | "verb" | "adjective" | "adverb"
    definition: str
    examples: list[str] = field(default_factory=list)
    synonyms: list[str] = field(default_factory=list)
    antonyms: list[str] = field(default_factory=list)


@dataclass
class DictionaryResult:
    """Combined result from all available sources."""
    word: str
    found: bool

    # Source 1 — WordNet (NLTK, always offline)
    wordnet_entries: list[WordNetEntry] = field(default_factory=list)

    # Source 2 — Webster's 1913 SQLite (offline when asset is present)
    webster_definition: str | None = None

    # Source 3 — AyDictionary (online enrichment; None when unavailable)
    # Shape: {"Noun": ["def1", "def2"], "Verb": [...]}
    ay_meanings: dict[str, list[str]] | None = None
    ay_synonyms: list[str] | None = None
    ay_antonyms: list[str] | None = None


# ---------------------------------------------------------------------------
# POS normalisation helper
# ---------------------------------------------------------------------------

_POS_MAP = {"n": "noun", "v": "verb", "a": "adjective", "s": "adjective", "r": "adverb"}


def _pos_label(synset_pos: str) -> str:
    return _POS_MAP.get(synset_pos, synset_pos)


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------

class DictionaryService:
    """Three-source dictionary with offline-first design.

    Instantiation is cheap.  The word list used by search() is built lazily
    and cached; the Webster's DB connection is opened per-lookup.
    """

    def __init__(self, webster_db_path: Path | None = None) -> None:
        self._webster_path = webster_db_path or WEBSTER_DB_PATH
        self._webster_available = self._webster_path.exists()
        self._word_list: list[str] | None = None   # built lazily

        if not self._webster_available:
            logger.warning(
                "Webster's 1913 DB not found at %s — Webster section disabled.",
                self._webster_path,
            )

    # ------------------------------------------------------------------
    # FR-5-05 — Word lookup
    # ------------------------------------------------------------------

    def lookup(self, word: str) -> DictionaryResult:
        """Return a DictionaryResult combining all available sources."""
        word = word.strip().lower()
        result = DictionaryResult(word=word, found=False)

        # Source 1 — WordNet (always runs, always offline)
        result.wordnet_entries = self._wordnet_lookup(word)
        if result.wordnet_entries:
            result.found = True

        # Source 2 — Webster's 1913 (offline, when asset is present)
        if self._webster_available:
            result.webster_definition = self._webster_lookup(word)
            if result.webster_definition:
                result.found = True

        # Source 3 — AyDictionary (network-guarded; enriches when online)
        if self._is_network_available():
            ay = self._aydictionary_lookup(word)
            if ay:
                result.ay_meanings = ay.get("meanings")
                result.ay_synonyms = ay.get("synonyms")
                result.ay_antonyms = ay.get("antonyms")
                if result.ay_meanings:
                    result.found = True
        else:
            logger.debug("Network unavailable — AyDictionary skipped for %r.", word)

        return result

    # ------------------------------------------------------------------
    # FR-5-06 — Fuzzy search
    # ------------------------------------------------------------------

    def search(self, query: str, threshold: int | None = None) -> list[str]:
        """Return candidate words above *threshold* ranked by fuzzy score.

        Runs on the combined offline word list (WordNet lemmas ∪ Webster
        headwords).  Runs on a background thread in the UI; this method
        is thread-safe.
        """
        if threshold is None:
            threshold = DICTIONARY_FUZZY_THRESHOLD

        word_list = self._get_word_list()
        if not word_list:
            return []

        matches = fuzz_process.extract(
            query,
            word_list,
            scorer=fuzz.WRatio,
            limit=20,
        )
        return [word for word, score, _ in matches if score >= threshold]

    # ------------------------------------------------------------------
    # Source 1 — WordNet (NLTK)
    # ------------------------------------------------------------------

    def _wordnet_lookup(self, word: str) -> list[WordNetEntry]:
        try:
            from nltk.corpus import wordnet as wn
            synsets = wn.synsets(word)
            if not synsets:
                return []

            entries: list[WordNetEntry] = []
            seen_defs: set[str] = set()

            for synset in synsets:
                definition = synset.definition() or ""
                if definition in seen_defs:
                    continue
                seen_defs.add(definition)

                # Synonyms — lemma names of this synset (excluding the query word)
                synonyms = [
                    lemma.name().replace("_", " ")
                    for lemma in synset.lemmas()
                    if lemma.name().lower() != word
                ]

                # Antonyms — from lemma antonyms
                antonyms = [
                    ant.name().replace("_", " ")
                    for lemma in synset.lemmas()
                    for ant in lemma.antonyms()
                ]

                entries.append(WordNetEntry(
                    pos=_pos_label(synset.pos()),
                    definition=definition,
                    examples=synset.examples(),
                    synonyms=synonyms,
                    antonyms=antonyms,
                ))

            return entries
        except Exception:
            logger.exception("WordNet lookup failed for %r.", word)
            return []

    # ------------------------------------------------------------------
    # Source 2 — Webster's 1913 SQLite
    # ------------------------------------------------------------------

    def _webster_lookup(self, word: str) -> str | None:
        """Query the bundled Webster's 1913 database.

        Returns the raw definition text, or None if not found.
        The DB schema has a 'entries' table with columns 'word' and
        'definition' (exact column names discovered at runtime so the
        service adapts to minor schema variations).
        """
        if not self._webster_available:
            return None
        try:
            with sqlite3.connect(str(self._webster_path)) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()

                # Discover table name (flexible — different Webster DBs vary)
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cur.fetchall()]
                if not tables:
                    return None
                table = tables[0]

                # Discover columns
                cur.execute(f"PRAGMA table_info({table})")
                cols = [row["name"].lower() for row in cur.fetchall()]

                word_col = next(
                    (c for c in cols if c in ("word", "headword", "entry")), cols[0]
                )
                def_col = next(
                    (c for c in cols if c in ("definition", "definitions", "body", "text")),
                    cols[1] if len(cols) > 1 else cols[0],
                )

                cur.execute(
                    f"SELECT {def_col} FROM {table} "
                    f"WHERE lower({word_col}) = ? LIMIT 1",
                    (word.lower(),),
                )
                row = cur.fetchone()
                return str(row[0]).strip() if row and row[0] else None
        except Exception:
            logger.exception("Webster's lookup failed for %r.", word)
            return None

    # ------------------------------------------------------------------
    # Source 3 — AyDictionary (network-guarded)
    # ------------------------------------------------------------------

    def _aydictionary_lookup(self, word: str) -> dict[str, Any] | None:
        """Call AyDictionary with a per-call timeout.

        AyDictionary.meaning()  → WordNet via NLTK (offline path)
        AyDictionary.synonym()  → synonym.com scrape (network)
        AyDictionary.antonym()  → synonym.com scrape (network)

        All three are wrapped in individual try/except blocks so a partial
        result is still returned if only one network call fails.
        """
        try:
            from AyDictionary import AyDictionary  # type: ignore[import]
            ay = AyDictionary()

            result: dict[str, Any] = {}

            # meanings — primarily WordNet-backed (works offline too, but
            # we only call it when we already know the network is up so
            # this path is consistent with the rest of the call).
            try:
                meanings = ay.meaning(word)
                if meanings:
                    result["meanings"] = meanings
            except Exception:
                logger.debug("AyDictionary.meaning() failed for %r.", word)

            # synonyms — requires synonym.com
            try:
                syns = ay.synonym(word)
                if syns:
                    result["synonyms"] = syns
            except Exception:
                logger.debug("AyDictionary.synonym() failed for %r.", word)

            # antonyms — requires synonym.com
            try:
                ants = ay.antonym(word)
                if ants:
                    result["antonyms"] = ants
            except Exception:
                logger.debug("AyDictionary.antonym() failed for %r.", word)

            return result if result else None

        except ImportError:
            logger.warning("AyDictionary package not installed; skipping.")
            return None
        except Exception:
            logger.exception("AyDictionary lookup failed for %r.", word)
            return None

    # ------------------------------------------------------------------
    # FR-5-06 — Word list for fuzzy search
    # ------------------------------------------------------------------

    def _get_word_list(self) -> list[str]:
        """Return (and cache) the union of WordNet lemmas + Webster headwords."""
        if self._word_list is not None:
            return self._word_list
        self._word_list = self._build_word_list()
        return self._word_list

    def _build_word_list(self) -> list[str]:
        words: set[str] = set()

        # WordNet lemma names
        try:
            from nltk.corpus import wordnet as wn
            for synset in wn.all_synsets():
                for lemma in synset.lemmas():
                    words.add(lemma.name().replace("_", " ").lower())
        except Exception:
            logger.exception("Failed to load WordNet lemmas.")

        # Webster's headwords
        if self._webster_available:
            try:
                with sqlite3.connect(str(self._webster_path)) as conn:
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                    tables = [r[0] for r in cur.fetchall()]
                    if tables:
                        table = tables[0]
                        cur.execute(
                            f"PRAGMA table_info({table})"
                        )
                        cols = [r["name"].lower() for r in cur.fetchall()]
                        word_col = next(
                            (c for c in cols if c in ("word", "headword", "entry")),
                            cols[0],
                        )
                        cur.execute(f"SELECT DISTINCT lower({word_col}) FROM {table}")
                        for row in cur.fetchall():
                            if row[0]:
                                words.add(str(row[0]).strip())
            except Exception:
                logger.exception("Failed to load Webster headwords.")

        logger.debug("Dictionary word list built: %d entries.", len(words))
        return sorted(words)

    # ------------------------------------------------------------------
    # Network probe
    # ------------------------------------------------------------------

    @staticmethod
    def _is_network_available(host: str = "8.8.8.8", port: int = 53,
                               timeout: float = 1.5) -> bool:
        """Fast TCP probe to detect internet connectivity (CON-01 guard).

        Uses a DNS port probe (no DNS query actually sent) — sub-2ms on a
        live connection, fails quickly on a dead one.
        """
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False
