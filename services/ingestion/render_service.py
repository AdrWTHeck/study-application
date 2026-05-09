"""PDF page rendering — Phase 2."""
from __future__ import annotations


class RenderService:
    def render_page(self, file_path: str, page_number: int, dpi: int): raise NotImplementedError
