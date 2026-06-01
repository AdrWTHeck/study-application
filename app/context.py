"""A small container passed to views so they can open sessions and build services."""
from __future__ import annotations

from dataclasses import dataclass

from core.settings import Settings
from data.db import Database
from domain.accessibility.tts_service import TTSService
from domain.srs.srs_base import SrsEngine


@dataclass
class AppContext:
    db: Database | None
    engine: SrsEngine
    settings: Settings
    tts: TTSService | None = None
