"""Text cleaning and segmentation — Phase 2/3."""
from __future__ import annotations


class TextProcessor:
    def clean(self, text: str) -> str: raise NotImplementedError
    def segment(self, text: str) -> list[str]: raise NotImplementedError
