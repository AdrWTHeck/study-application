"""Abstract base for question generators — Phase 3."""
from __future__ import annotations
from abc import ABC, abstractmethod


class BaseGenerator(ABC):
    @abstractmethod
    def generate(self, segment: str) -> list: ...

    @abstractmethod
    def generator_type(self) -> str: ...
