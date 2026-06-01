"""Create/edit notes and (re)generate their cards.

One card is generated per card template of the note type (Basic → 1, Basic+
reversed → 2, Cloze → 1). New cards start in the engine's fresh state.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.clock import now
from data.models import Card, Note, NoteFieldValue, NoteType, Tag
from data.repositories.note_repository import NoteRepository
from data.repositories.note_type_repository import NoteTypeRepository
from domain.srs.mapping import apply_state
from domain.srs.srs_base import SrsEngine


class NoteService:
    def __init__(self, session: Session, engine: SrsEngine) -> None:
        self.session = session
        self.engine = engine
        self.notes = NoteRepository(session)
        self.note_types = NoteTypeRepository(session)

    def create_note(
        self,
        deck_id: int,
        note_type_id: int,
        values: dict[str, str],
        tags: list[str] | None = None,
    ) -> Note:
        note_type = self.note_types.get(note_type_id)
        if note_type is None:
            raise ValueError(f"Unknown note type {note_type_id}")

        note = Note(note_type_id=note_type_id, deck_id=deck_id)
        for field in note_type.fields:
            note.field_values.append(
                NoteFieldValue(field_id=field.id, value=values.get(field.name, ""))
            )
        if tags:
            note.tags = [self._get_or_create_tag(name) for name in tags]
        self.session.add(note)
        self.session.flush()

        self._generate_cards(note, note_type)
        self.session.flush()
        return note

    def update_values(self, note: Note, values: dict[str, str]) -> Note:
        for field_value in note.field_values:
            if field_value.field is not None and field_value.field.name in values:
                field_value.value = values[field_value.field.name]
        note.modified_at = now()
        self.session.flush()
        return note

    def move_to_deck(self, note: Note, deck_id: int) -> Note:
        note.deck_id = deck_id
        for card in note.cards:
            card.deck_id = deck_id
        note.modified_at = now()
        self.session.flush()
        return note

    def delete_note(self, note: Note) -> None:
        self.session.delete(note)
        self.session.flush()

    def delete_note_by_id(self, note_id: int) -> None:
        note = self.notes.get(note_id)
        if note is not None:
            self.delete_note(note)

    # -- internals ----------------------------------------------------------

    def _generate_cards(self, note: Note, note_type: NoteType) -> None:
        moment = now()
        for template in note_type.templates:
            state = self.engine.new_state(moment)
            card = Card(template_id=template.id, deck_id=note.deck_id)
            apply_state(card, state)
            note.cards.append(card)  # cascade persists; keeps note.cards populated

    def _get_or_create_tag(self, name: str) -> Tag:
        tag = self.session.scalar(select(Tag).where(Tag.name == name))
        if tag is None:
            tag = Tag(name=name)
            self.session.add(tag)
            self.session.flush()
        return tag
