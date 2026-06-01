"""Seed built-in note types and a default deck on first launch (idempotent)."""
from __future__ import annotations

from sqlalchemy import func, select

from data.db import Database
from data.models import CardTemplate, Deck, Field, NoteType


def seed_defaults(db: Database) -> None:
    with db.session() as session:
        if session.scalar(select(func.count()).select_from(NoteType)) == 0:
            session.add_all(_builtin_note_types())
        has_default = session.scalar(
            select(func.count()).select_from(Deck).where(Deck.is_default.is_(True))
        )
        if not has_default:
            session.add(Deck(name="Default", deck_type="card", is_default=True))


def _builtin_note_types() -> list[NoteType]:
    basic = NoteType(name="Basic", is_builtin=True)
    basic.fields = [Field(name="Front", ordinal=0), Field(name="Back", ordinal=1)]
    basic.templates = [
        CardTemplate(name="Card 1", front_html="{{Front}}",
                     back_html="{{Front}}<hr>{{Back}}", ordinal=0)
    ]

    reversed_ = NoteType(name="Basic (and reversed)", is_builtin=True)
    reversed_.fields = [Field(name="Front", ordinal=0), Field(name="Back", ordinal=1)]
    reversed_.templates = [
        CardTemplate(name="Card 1", front_html="{{Front}}",
                     back_html="{{Front}}<hr>{{Back}}", ordinal=0),
        CardTemplate(name="Card 2", front_html="{{Back}}",
                     back_html="{{Back}}<hr>{{Front}}", ordinal=1),
    ]

    cloze = NoteType(name="Cloze", is_builtin=True, is_cloze=True)
    cloze.fields = [Field(name="Text", ordinal=0), Field(name="Extra", ordinal=1)]
    cloze.templates = [
        CardTemplate(name="Cloze", front_html="{{cloze:Text}}",
                     back_html="{{cloze:Text}}<hr>{{Extra}}", ordinal=0)
    ]

    return [basic, reversed_, cloze]
