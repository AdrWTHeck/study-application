"""Create custom note types (Advanced mode). Built-in types are seeded; this is
the user-facing creation path."""
from __future__ import annotations

from sqlalchemy.orm import Session

from data.models import CardTemplate, Field, NoteType
from data.repositories.note_type_repository import NoteTypeRepository


class NoteTypeService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.note_types = NoteTypeRepository(session)

    def create_type(
        self,
        name: str,
        field_names: list[str],
        templates: list[tuple[str, str, str]],
        is_cloze: bool = False,
        css: str = "",
    ) -> NoteType:
        """Create a note type. ``templates`` is a list of (name, front_html, back_html)."""
        note_type = NoteType(name=name.strip(), css=css, is_cloze=is_cloze, is_builtin=False)
        note_type.fields = [
            Field(name=field_name.strip(), ordinal=i)
            for i, field_name in enumerate(field_names)
            if field_name.strip()
        ]
        note_type.templates = [
            CardTemplate(name=t_name, front_html=front, back_html=back, ordinal=i)
            for i, (t_name, front, back) in enumerate(templates)
        ]
        self.session.add(note_type)
        self.session.flush()
        return note_type
