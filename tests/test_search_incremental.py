"""Incremental search index maintenance (§ search #7).

Once the index is built, creating/editing/deleting content keeps it fresh via
the per-transaction indexer — no full rebuild needed. ``ensure_built`` builds
once then no-ops; ``repair`` does a full rebuild.
"""
from sqlalchemy import select, text

from data.models import Deck, NoteType
from domain.notes.note_service import NoteService
from domain.search.search_service import SearchService
from domain.srs import make_engine


def _basic(s):
    deck = s.scalar(select(Deck).where(Deck.is_default.is_(True)))
    basic = s.scalar(select(NoteType).where(NoteType.name == "Basic"))
    return deck, basic


def test_ensure_built_is_idempotent(db):
    service = SearchService(db)
    service.ensure_built()
    # Second call must not raise and must leave the built flag set.
    service.ensure_built()
    with db.session() as s:
        built = s.execute(text("SELECT built FROM search_meta")).scalar()
    assert built == 1


def test_new_note_indexed_without_full_rebuild(db):
    # Build the (empty-ish) index first.
    service = SearchService(db)
    service.ensure_built()

    # Create a note AFTER the build — incremental upsert should index it.
    with db.session() as s:
        deck, basic = _basic(s)
        NoteService(s, make_engine()).create_note(
            deck.id, basic.id, {"Front": "Mitochondria", "Back": "powerhouse"}
        )

    # No rebuild() call here — relies on incremental indexing.
    results = service.search("mitochondria")
    assert any(r.type == "note" for r in results)


def test_deleted_note_removed_from_index(db):
    service = SearchService(db)
    with db.session() as s:
        deck, basic = _basic(s)
        note = NoteService(s, make_engine()).create_note(
            deck.id, basic.id, {"Front": "Ribosome", "Back": "protein synthesis"}
        )
        note_id = note.id
    service.ensure_built()
    assert any(r.type == "note" for r in service.search("ribosome"))

    with db.session() as s:
        NoteService(s, make_engine()).delete_note_by_id(note_id)

    assert not any(r.type == "note" for r in service.search("ribosome"))


def test_edited_note_reindexed(db):
    service = SearchService(db)
    with db.session() as s:
        deck, basic = _basic(s)
        note = NoteService(s, make_engine()).create_note(
            deck.id, basic.id, {"Front": "Osmosis", "Back": "water movement"}
        )
        note_id = note.id
    service.ensure_built()

    with db.session() as s:
        svc = NoteService(s, make_engine())
        note = svc.notes.get(note_id)
        svc.update_values(note, {"Front": "Diffusion", "Back": "particle spread"})

    assert not any(r.type == "note" for r in service.search("osmosis"))
    assert any(r.type == "note" for r in service.search("diffusion"))


def test_repair_rebuilds_from_scratch(db, sample_deck):
    # sample_deck created its notes before any build → index is empty/unbuilt.
    service = SearchService(db)
    service.repair()
    results = service.search("mitochondria")
    assert any(r.type == "note" for r in results)
