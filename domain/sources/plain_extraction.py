"""Plain text and Markdown extraction for simple imported documents."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExtractedSegment:
    page: int
    ordinal: int
    kind: str
    text: str


def extract_segments(text: str) -> list[ExtractedSegment]:
    lines = text.splitlines()
    segments: list[ExtractedSegment] = []
    ordinal = 0
    buffer: list[str] = []

    def flush(kind: str = "body"):
        nonlocal ordinal
        if not buffer:
            return
        segment_text = " ".join(buffer).strip()
        if segment_text:
            segments.append(ExtractedSegment(page=1, ordinal=ordinal, kind=kind, text=segment_text))
            ordinal += 1
        buffer.clear()

    def is_heading(text: str, next_text: str | None = None) -> bool:
        if text.startswith("#"):
            return True
        if text.isupper() and 1 < len(text.split()) <= 8 and not text.endswith("."):
            return True
        if next_text == "" and 0 < len(text) <= 60 and len(text.split()) <= 8 and not text.endswith((".", "?", "!")):
            return True
        return False

    for index, line in enumerate(lines):
        stripped = line.strip()
        next_text = lines[index + 1].strip() if index + 1 < len(lines) else None
        if stripped == "":
            flush("body")
            continue
        if is_heading(stripped, next_text):
            flush("body")
            heading = stripped.lstrip("#").strip()
            if heading:
                segments.append(ExtractedSegment(page=1, ordinal=ordinal, kind="heading", text=heading))
                ordinal += 1
            continue
        buffer.append(stripped)

    flush("body")
    return segments
