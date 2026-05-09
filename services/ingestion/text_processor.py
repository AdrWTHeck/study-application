"""Text cleaning and paragraph-level segmentation for extracted PDF text.

Phase 2 uses simple heuristic segmentation (paragraph splits).
Phase 3 will add spaCy sentence-level segmentation for question generation.
"""
from __future__ import annotations

import re
import logging
from typing import Pattern

from config.constants import CLEANING_PATTERNS, MIN_SEGMENT_WORD_COUNT

logger = logging.getLogger(__name__)


class TextProcessor:
    """Stateless text cleaner and segmenter.

    Patterns from CLEANING_PATTERNS are split into two buckets at init:
    - *line filters*: anchored with ``^...$`` — matching lines are dropped.
    - *inline subs*: all others — replaced with a single space.
    """

    def __init__(self) -> None:
        self._line_filters: list[Pattern] = []
        self._inline_subs: list[Pattern] = []

        for raw in CLEANING_PATTERNS:
            compiled = re.compile(raw)
            if raw.startswith("^") and raw.endswith("$"):
                self._line_filters.append(compiled)
            else:
                self._inline_subs.append(compiled)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clean(self, text: str) -> str:
        """Remove noise (headers, footers, page numbers, excess whitespace).

        Applies inline substitutions first, then drops lines that match a
        full-line filter pattern.
        """
        # 1. Inline substitutions (e.g. collapse runs of whitespace).
        for pattern in self._inline_subs:
            text = pattern.sub(" ", text)

        # 2. Line-by-line filtering.
        lines: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if any(f.fullmatch(stripped) for f in self._line_filters):
                continue
            lines.append(stripped)

        return "\n".join(lines)

    def segment(self, text: str) -> list[str]:
        """Split *text* into paragraph-level segments.

        Paragraphs are separated by one or more blank lines.  Segments with
        fewer than MIN_SEGMENT_WORD_COUNT words are discarded (FR-2-07).
        """
        # Split on blank lines (paragraph breaks).
        raw_chunks = re.split(r"\n\s*\n", text)
        segments: list[str] = []

        for chunk in raw_chunks:
            # Re-join wrapped lines within a paragraph into a single string.
            merged = " ".join(
                line.strip() for line in chunk.splitlines() if line.strip()
            )
            if not merged:
                continue
            word_count = len(merged.split())
            if word_count < MIN_SEGMENT_WORD_COUNT:
                logger.debug(
                    "Discarded short segment (%d words): %r", word_count, merged[:60]
                )
                continue
            segments.append(merged)

        return segments
