"""Abstract base for question generators."""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseGenerator(ABC):
    @abstractmethod
    def generate(self, segment: str) -> list[dict]:
        """Return a list of raw question dicts for the given text segment.

        Each dict has keys: question_text, answer, type, distractors.
        """

    @abstractmethod
    def generator_type(self) -> str:
        """Return the generator_type value to store on the Question model."""
