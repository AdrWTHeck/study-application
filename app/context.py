"""A small container passed to views so they can open sessions and build services."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.events import EventBus
from core.settings import Settings
from data.db import Database
from domain.accessibility.tts_service import TTSService
from domain.dictionary.service import DictionaryService
from domain.srs.srs_base import SrsEngine
from ui.theme.tokens import PALETTES, Palette

if TYPE_CHECKING:
    from ui.theme.theme_controller import ThemeController


@dataclass
class AppContext:
    db: Database | None
    engine: SrsEngine
    settings: Settings
    tts: TTSService | None = None
    dictionary: DictionaryService | None = None
    theme: "ThemeController" | None = None
    palette: Palette = field(default_factory=lambda: PALETTES["dark"])
    # In-process pub/sub so views can react to domain events (card reviewed,
    # quiz finished, companion grew) without referencing each other directly.
    events: EventBus = field(default_factory=EventBus)
