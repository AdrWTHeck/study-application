"""Quiz session assembly — Phase 3."""
from __future__ import annotations


class QuizBuilder:
    def build(self, scope, count: int, distribution: dict): raise NotImplementedError
    def build_comprehensive(self, deck_ids: list[int], total_count: int): raise NotImplementedError
