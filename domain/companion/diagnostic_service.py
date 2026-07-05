"""Backing data for the diagnostic confidence sweep (§6.3).

Extracted from the dialog so the query lives in the domain layer, not the UI,
and so a deck-scoped sweep still only samples *due* cards — a previous
deck-scoped code path dropped the due filter entirely, which meant a deck
diagnostic rated arbitrary cards instead of the ones actually due for review.
"""
from __future__ import annotations

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session


class DiagnosticService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def due_card_fronts(self, deck_id: int | None, limit: int) -> list[tuple[int | None, str]]:
        """Up to *limit* (note_id, front_text) pairs for due cards.

        When *deck_id* is given the sweep is scoped to that deck, but the due
        filter still applies in both cases — a deck-scoped diagnostic should
        rate cards the user is actually about to review, not any card in the
        deck.
        """
        where = "AND c.due <= datetime('now')"
        params: dict = {"limit": limit}
        if deck_id is not None:
            where += " AND n.deck_id = :deck_id"
            params["deck_id"] = deck_id

        rows = self.session.execute(
            sa_text(
                f"""
                SELECT n.id, nfv.value
                FROM cards c
                JOIN notes n ON n.id = c.note_id
                JOIN note_types nt ON nt.id = n.note_type_id
                JOIN fields f ON f.note_type_id = nt.id
                JOIN note_field_values nfv ON nfv.note_id = n.id
                    AND nfv.field_id = f.id
                WHERE f.ordinal = 0
                    {where}
                ORDER BY c.due ASC
                LIMIT :limit
                """
            ),
            params,
        ).fetchall()
        return [(row[0], str(row[1])) for row in rows]
