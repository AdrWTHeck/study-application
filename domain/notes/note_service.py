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
from domain.search import indexer
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
        indexer.reindex_note(self.session, note)
        return note

    def update_values(self, note: Note, values: dict[str, str]) -> Note:
        for field_value in note.field_values:
            if field_value.field is not None and field_value.field.name in values:
                field_value.value = values[field_value.field.name]
        note.modified_at = now()
        self.session.flush()
        indexer.reindex_note(self.session, note)
        return note

    def set_tags(self, note: Note, names: list[str]) -> Note:
        note.tags = [self._get_or_create_tag(name) for name in names]
        self.session.flush()
        return note

    def move_to_deck(self, note: Note, deck_id: int) -> Note:
        note.deck_id = deck_id
        for card in note.cards:
            card.deck_id = deck_id
        note.modified_at = now()
        self.session.flush()
        indexer.reindex_note(self.session, note)  # title follows the deck name
        return note

    def delete_note(self, note: Note) -> None:
        note_id = note.id
        self.session.delete(note)
        self.session.flush()
        indexer.remove(self.session, "note", note_id)

    def copy_notes_by_ids(self, note_ids: list[int], dst_deck_id: int) -> int:
        """Copy specific notes into a deck as fresh cards. Returns the count copied."""
        copied = 0
        for note_id in dict.fromkeys(note_ids):
            note = self.notes.get(note_id)
            if note is None:
                continue
            values = note.values_by_field_name()
            tags = [tag.name for tag in note.tags]
            self.create_note(dst_deck_id, note.note_type_id, values, tags)
            copied += 1
        return copied

    def copy_notes_to_deck(self, src_deck_id: int, dst_deck_id: int) -> int:
        """Copy every note from one deck into another as fresh cards.

        Field values and tags are preserved; scheduling is reset (the copies are
        brand-new cards). Returns the number of notes copied.
        """
        source_notes = list(
            self.session.scalars(select(Note).where(Note.deck_id == src_deck_id))
        )
        copied = 0
        for note in source_notes:
            values = note.values_by_field_name()
            tags = [tag.name for tag in note.tags]
            self.create_note(dst_deck_id, note.note_type_id, values, tags)
            copied += 1
        return copied

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
