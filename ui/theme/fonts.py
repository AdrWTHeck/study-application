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

# The redesign's bundled UI face first, then the dyslexia-friendly options,
# then safe cross-platform sans faces.
FALLBACK_CHAIN = [
    "IBM Plex Sans",
    "Atkinson Hyperlegible",
    "OpenDyslexic",
    "Segoe UI",
    "Helvetica Neue",
    "Arial",
    "Noto Sans",
    "DejaVu Sans",
]

# Monospace chain for eyebrow/section labels and mono badges.
MONO_FALLBACK_CHAIN = [
    "IBM Plex Mono",
    "Consolas",
    "Courier New",
]


# Folders inside bundled font packages whose contents must not be loaded
# (licensing) or are archive cruft.
_SKIP_PARTS = {"For Professional Use Only", "__MACOSX"}


def load_application_fonts(fonts_dir: Path) -> set[str]:
    """Register every .ttf/.otf under *fonts_dir* (recursively); return families.

    Skips license-restricted ("For Professional Use Only") and archive
    (`__MACOSX`) subfolders so only freely usable fonts are registered.
    """
    loaded: set[str] = set()
    if not fonts_dir.exists():
        logger.info("No bundled fonts dir at %s; using system fonts.", fonts_dir)
        return loaded
    for path in sorted(fonts_dir.rglob("*")):
        if path.suffix.lower() not in (".ttf", ".otf"):
            continue
        if _SKIP_PARTS.intersection(path.parts):
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


def resolve_mono(preferred: str = "IBM Plex Mono") -> str:
    """Like :func:`resolve_family`, but down the monospace chain."""
    available = set(QFontDatabase.families())
    if not available:
        return preferred
    if preferred in available:
        return preferred
    for family in MONO_FALLBACK_CHAIN:
        if family in available:
            return family
    return resolve_family(preferred)
