"""PDF upload, extraction, source management — Phase 2."""
from __future__ import annotations


class PDFService:
    def upload(self, file_path: str): raise NotImplementedError
    def extract(self, source_id: int) -> list: raise NotImplementedError
    def retry_extraction(self, source_id: int) -> None: raise NotImplementedError
    def delete_source(self, source_id: int) -> None: raise NotImplementedError
    def associate_deck(self, source_id: int, deck_id: int) -> None: raise NotImplementedError
    def disassociate_deck(self, source_id: int, deck_id: int) -> None: raise NotImplementedError
    def extract_tables(self, file_path: str) -> list:
        """Stub — returns [] in Sprint 1 (FR-2-08)."""
        return []
