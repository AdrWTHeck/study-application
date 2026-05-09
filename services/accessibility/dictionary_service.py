"""Offline dictionary service (WordNet + Webster) — Phase 5."""
from __future__ import annotations


class DictionaryService:
    def lookup(self, word: str): raise NotImplementedError
    def search(self, query: str, threshold: int) -> list[str]: raise NotImplementedError
