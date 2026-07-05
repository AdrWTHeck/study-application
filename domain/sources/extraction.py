"""Structured PDF text extraction (RDG-03).

Improves on the previous iteration's plain paragraph split: uses PyMuPDF text
blocks (which are already separated by visual whitespace gaps) and classifies
each as a heading or body via font size, ALL-CAPS, or section numbering. The
result is readable, spaced study text with headings preserved.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from statistics import median

_MIN_BODY_WORDS = 4
_HEADING_MAX_WORDS = 14
_HEADING_SIZE_RATIO = 1.25
_NUMBERED = re.compile(r"^\d+(\.\d+)*[.)]?\s+\S")


@dataclass
class ExtractedSegment:
    page: int
    ordinal: int
    kind: str  # "heading" | "body"
    text: str


def _is_heading(text: str, size: float, body_size: float) -> bool:
    words = text.split()
    if not words or len(words) > _HEADING_MAX_WORDS:
        return False
    if body_size and size >= body_size * _HEADING_SIZE_RATIO:
        return True
    if text.isupper():
        return True
    if _NUMBERED.match(text):
        return True
    return False


def extract_segments(file_path: str) -> list[ExtractedSegment]:
    import fitz

    segments: list[ExtractedSegment] = []
    with fitz.open(file_path) as doc:
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            blocks: list[tuple[str, float]] = []
            sizes: list[float] = []

            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:  # text blocks only
                    continue
                lines: list[str] = []
                max_size = 0.0
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    line_text = "".join(s.get("text", "") for s in spans).strip()
                    if line_text:
                        lines.append(line_text)
                        max_size = max(max_size, *(s.get("size", 0.0) for s in spans))
                if not lines:
                    continue
                text = re.sub(r"\s+", " ", " ".join(lines)).strip()
                blocks.append((text, max_size))
                sizes.append(max_size)

            body_size = median(sizes) if sizes else 0.0
            ordinal = 0
            for text, size in blocks:
                heading = _is_heading(text, size, body_size)
                if not heading and len(text.split()) < _MIN_BODY_WORDS:
                    continue  # drop page numbers / stray short fragments
                segments.append(
                    ExtractedSegment(
                        page=page_index + 1,
                        ordinal=ordinal,
                        kind="heading" if heading else "body",
                        text=text,
                    )
                )
                ordinal += 1
    return segments
