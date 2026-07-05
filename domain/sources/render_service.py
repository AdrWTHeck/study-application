"""Render PDF pages to PNG bytes via PyMuPDF (fitz).

Returns raw PNG bytes (UI-agnostic — the viewer wraps them in a QPixmap), plus
pixel dimensions so the viewer can size/scroll. Zoom is a simple scale factor
(1.0 ≈ 72 DPI).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RenderedPage:
    png: bytes
    width: int
    height: int


def page_count(file_path: str) -> int:
    import fitz

    with fitz.open(file_path) as doc:
        return doc.page_count


def render_page(file_path: str, page_index: int, zoom: float = 1.5) -> RenderedPage:
    import fitz

    with fitz.open(file_path) as doc:
        page = doc.load_page(page_index)
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        return RenderedPage(png=pixmap.tobytes("png"), width=pixmap.width, height=pixmap.height)


def search_text_rects(file_path: str, page_index: int, text: str) -> list[dict]:
    """Find on-page rectangles where *text* appears, normalized to the page size.

    Used to map a text selection onto the rendered PDF so highlights can be
    painted as an overlay attached to the page — the original file is never
    modified. Each rect is stored as fractions of the page (0..1) so it redraws
    correctly at any zoom: {"x0","y0","x1","y1", "page_width","page_height"}.
    Returns [] when the text isn't found or on any error.
    """
    text = (text or "").strip()
    if not text:
        return []
    normalized = re.sub(r"\s+", " ", text).strip()
    try:
        import fitz

        with fitz.open(file_path) as doc:
            if page_index < 0 or page_index >= doc.page_count:
                return []
            page = doc.load_page(page_index)
            pw, ph = float(page.rect.width), float(page.rect.height)
            if pw <= 0 or ph <= 0:
                return []

            hits = page.search_for(normalized)
            if not hits:
                hits = page.search_for(normalized, flags=fitz.TEXT_DEHYPHENATE)

            rects: list[dict] = []
            for quad in hits:
                rects.append({
                    "x0": quad.x0 / pw, "y0": quad.y0 / ph,
                    "x1": quad.x1 / pw, "y1": quad.y1 / ph,
                    "page_width": pw, "page_height": ph,
                })
            return rects
    except Exception:  # noqa: BLE001
        logger.exception("search_text_rects failed for %s p%s", file_path, page_index)
        return []


def search_text_quads(file_path: str, page_index: int, text: str) -> list:
    """Return raw fitz.Quad objects for annotation creation.

    Uses a four-tier fallback strategy to handle whitespace mismatches between
    the PDF.js text layer (which may insert newlines at visual line breaks) and
    PyMuPDF's internal text stream (which uses spaces).

    Tier 1 — normalized exact match (fixes the common cross-line-break case)
    Tier 2 — dehyphenation flag (handles "suf-\\nfix" style splits)
    Tier 3 — per-segment search (user selected across paragraph boundaries)
    Tier 4 — word-anchor fallback (encoding mismatches in old/custom fonts)

    Returns [] on any error or when text is not found by any strategy.
    """
    text = (text or "").strip()
    if not text:
        return []
    normalized = re.sub(r"\s+", " ", text).strip()
    try:
        import fitz

        with fitz.open(file_path) as doc:
            if page_index < 0 or page_index >= doc.page_count:
                return []
            page = doc.load_page(page_index)

            # Tier 1: whitespace-normalized exact search
            quads = page.search_for(normalized, quads=True)
            if quads:
                return quads

            # Tier 2: dehyphenation — joins words split with a hyphen across lines
            quads = page.search_for(normalized, quads=True,
                                    flags=fitz.TEXT_DEHYPHENATE)
            if quads:
                return quads

            # Tier 3: per-segment — search each original line independently and
            # combine.  Used when the selection spans visually separate blocks.
            segments = [re.sub(r"\s+", " ", s).strip()
                        for s in text.splitlines() if s.strip()]
            if len(segments) > 1:
                combined: list = []
                for seg in segments:
                    combined.extend(page.search_for(seg, quads=True))
                if combined:
                    return combined

            # Tier 4: word-anchor fallback for custom-encoded fonts where PDF.js
            # and PyMuPDF disagree on the Unicode codepoint for a glyph.  Locate
            # words from PyMuPDF's own word list that contain the first or last
            # token of the selection and return their bounding quads.
            tokens = normalized.split()
            if tokens:
                first_tok = tokens[0].lower()
                last_tok  = tokens[-1].lower()
                wlist = page.get_text("words")  # (x0, y0, x1, y1, word, ...)
                hits_t4 = [w for w in wlist
                           if first_tok in w[4].lower() or last_tok in w[4].lower()]
                if hits_t4:
                    return [fitz.Quad(fitz.Rect(w[:4])) for w in hits_t4]

            return []
    except Exception:  # noqa: BLE001
        logger.exception("search_text_quads failed for %s p%s", file_path, page_index)
        return []
