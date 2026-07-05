"""Manage customizable note flags and their assignment to notes."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from data.models import Note, NoteFlag, note_flag_assignments


class FlagService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_flags(self) -> list[NoteFlag]:
        return list(self.session.scalars(select(NoteFlag).order_by(NoteFlag.ordinal, NoteFlag.id)))

    def create_flag(self, name: str, color: str = "#868e96") -> NoteFlag:
        next_ordinal = (self.session.scalar(select(func.max(NoteFlag.ordinal))) or -1) + 1
        flag = NoteFlag(name=name.strip(), color=color, ordinal=next_ordinal, is_builtin=False)
        self.session.add(flag)
        self.session.flush()
        return flag

    def update_flag(self, flag_id: int, name: str | None = None, color: str | None = None) -> NoteFlag | None:
        flag = self.session.get(NoteFlag, flag_id)
        if flag is not None:
            if name is not None:
                flag.name = name.strip()
            if color is not None:
                flag.color = color
            self.session.flush()
        return flag

    def delete_flag(self, flag_id: int) -> None:
        flag = self.session.get(NoteFlag, flag_id)
        if flag is not None:
            self.session.delete(flag)
            self.session.flush()

    def set_note_flags(self, note_id: int, flag_ids: list[int]) -> Note | None:
        note = self.session.get(Note, note_id)
        if note is not None:
            flags = [self.session.get(NoteFlag, fid) for fid in flag_ids]
            note.flags = [f for f in flags if f is not None]
            self.session.flush()
        return note

    def flags_for_note(self, note_id: int) -> list[NoteFlag]:
        note = self.session.get(Note, note_id)
        return list(note.flags) if note is not None else []

    def notes_with_flag(self, flag_id: int) -> list[Note]:
        note_ids = [
            row.note_id
            for row in self.session.execute(
                select(note_flag_assignments.c.note_id).where(
                    note_flag_assignments.c.flag_id == flag_id
                )
            )
        ]
        if not note_ids:
            return []
        return list(self.session.scalars(select(Note).where(Note.id.in_(note_ids))))
