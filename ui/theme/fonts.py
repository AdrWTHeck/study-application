"""Bundled-font loading and safe family resolution (RDG-01).

The dyslexia-friendly default font is bundled with the app rather than assumed
to be installed. If a requested family is unavailable (e.g. the asset hasn't
been added yet, or on a stripped-down system), ``resolve_family`` degrades
gracefully down a sensible chain instead of rendering missing glyphs.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtGui import QFontDatabase

logger = logging.getLogger(__name__)

# Most-preferred (dyslexia-friendly) first, then safe cross-platform sans faces.
FALLBACK_CHAIN = [
    "Atkinson Hyperlegible",
    "OpenDyslexic",
    "Segoe UI",
    "Helvetica Neue",
    "Arial",
    "Noto Sans",
    "DejaVu Sans",
]


def load_application_fonts(fonts_dir: Path) -> set[str]:
    """Register every .ttf/.otf in *fonts_dir*; return the loaded family names."""
    loaded: set[str] = set()
    if not fonts_dir.exists():
        logger.info("No bundled fonts dir at %s; using system fonts.", fonts_dir)
        return loaded
    for path in sorted(fonts_dir.iterdir()):
        if path.suffix.lower() not in (".ttf", ".otf"):
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id == -1:
            logger.warning("Failed to load bundled font: %s", path.name)
            continue
        loaded.update(QFontDatabase.applicationFontFamilies(font_id))
    if loaded:
        logger.info("Loaded bundled fonts: %s", ", ".join(sorted(loaded)))
    return loaded


def resolve_family(preferred: str) -> str:
    """Return *preferred* if available, else the first available fallback.

    Prevents missing-glyph ("tofu") rendering when the requested family isn't
    present on the system and hasn't been bundled.
    """
    available = set(QFontDatabase.families())
    if not available:  # headless/no-fonts environment — nothing to resolve to
        return preferred
    if preferred in available:
        return preferred
    for family in FALLBACK_CHAIN:
        if family in available:
            return family
    return sorted(available)[0]
