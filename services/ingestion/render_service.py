"""PDF page rendering via PyMuPDF (FR-2-05).

Returns raw PNG bytes so the UI layer (Phase 5) can load them into a
QPixmap without this service knowing anything about PyQt6.
"""
from __future__ import annotations

import logging
from pathlib import Path

import fitz  # PyMuPDF

from config.constants import PDF_RENDER_DPI

logger = logging.getLogger(__name__)


class RenderService:
    """Renders individual pages of a PDF file to PNG image bytes."""

    def render_page(
        self,
        file_path: str,
        page_number: int,
        dpi: int = PDF_RENDER_DPI,
    ) -> bytes:
        """Render *page_number* (1-indexed) of *file_path* at *dpi*.

        Returns PNG bytes that can be passed directly to
        ``QPixmap.loadFromData()`` in the UI layer.

        Raises ``FileNotFoundError`` if the PDF is missing (NFR-12 — text
        features continue from stored data, but the visual viewer degrades
        gracefully when the file is absent).
        Raises ``IndexError`` if *page_number* is out of range.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")

        doc = fitz.open(str(path))
        try:
            if page_number < 1 or page_number > len(doc):
                raise IndexError(
                    f"Page {page_number} out of range for {path.name} "
                    f"({len(doc)} page(s))."
                )
            page = doc[page_number - 1]          # fitz is 0-indexed
            zoom = dpi / 72.0                    # 72 dpi is fitz default
            matrix = fitz.Matrix(zoom, zoom)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            png_bytes: bytes = pixmap.tobytes("png")
            logger.debug(
                "Rendered %s page %d at %d dpi — %d bytes.",
                path.name, page_number, dpi, len(png_bytes),
            )
            return png_bytes
        finally:
            doc.close()

    def get_page_count(self, file_path: str) -> int:
        """Return the total number of pages in *file_path*.

        Used by the PDF viewer to set up navigation controls.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")
        doc = fitz.open(str(path))
        try:
            return len(doc)
        finally:
            doc.close()
