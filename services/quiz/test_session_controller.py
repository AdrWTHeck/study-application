"""Test session controller — Phase 3."""
from __future__ import annotations


class TestSessionController:
    def start(self, deck_ids: list[int], total_count: int, scope_type: str): raise NotImplementedError
    def resume(self, session_id: int): raise NotImplementedError
    def get_next_question(self, session): raise NotImplementedError
    def submit_answer(self, session, question, answer: str, presented_at) -> None: raise NotImplementedError
    def discard(self, session_id: int) -> None: raise NotImplementedError
    def get_results(self, session): raise NotImplementedError
    def start_drill_down(self, session): raise NotImplementedError
