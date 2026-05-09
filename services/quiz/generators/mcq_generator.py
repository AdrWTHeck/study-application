"""MCQ generator — Phase 3."""
from __future__ import annotations
from .base_generator import BaseGenerator


class MCQGenerator(BaseGenerator):
    def generate(self, segment: str) -> list: raise NotImplementedError
    def generator_type(self) -> str: return "rule_based"
