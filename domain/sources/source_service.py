"""Source management: import, extraction, notes, position, bookmarks,
deck association. The original PDF on disk is never modified.
Annotations are written to a working copy via AnnotationService.
"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path


from sqlalchemy import select
from sqlalchemy.orm import Session

from core.clock import now
from data.models import (
    Bookmark,
    Deck,
    SourceDocument,
    Tag,
    TextSegment,
)
from data.repositories.source_repository import SourceRepository
from domain.search import indexer
from domain.sources import extraction, plain_extraction, render_service


class SourceService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.sources = SourceRepository(session)

    # -- import / extraction -----------------------------------------------

    def import_pdf(self, file_path: str, title: str | None = None,
                   library_dir: str | None = None) -> SourceDocument:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(file_path)
        doc = SourceDocument(
            title=title or path.stem,
            file_path=str(path.resolve()),
            kind="pdf",
            page_count=render_service.page_count(str(path)),
        )
        self.session.add(doc)
        self.session.flush()
        self._extract(doc)
        self.session.flush()
        if library_dir:
            self._setup_working_copy(doc, str(path.resolve()), library_dir)
        indexer.reindex_source(self.session, doc)
        return doc

    def _setup_working_copy(self, doc: SourceDocument, original_path: str, library_dir: str) -> None:
        lib = Path(library_dir)
        working_dir = lib / "working"
        archive_dir = lib / "originals"
        working_dir.mkdir(parents=True, exist_ok=True)
        archive_dir.mkdir(parents=True, exist_ok=True)

        working = working_dir / f"{doc.id}.pdf"
        shutil.copy2(original_path, working)
        doc.working_copy_path = str(working)

        archive = archive_dir / f"{doc.id}.pdf.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            zf.write(original_path, arcname=Path(original_path).name)
        doc.original_archived = True
        self.session.flush()

    def import_text(self, file_path: str, title: str | None = None, kind: str = "text") -> SourceDocument:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(file_path)
        doc = SourceDocument(
            title=title or path.stem,
            file_path=str(path.resolve()),
            kind=kind,
            page_count=1,
        )
        self.session.add(doc)
        self.session.flush()
        self._extract_plain(doc)
        self.session.flush()
        indexer.reindex_source(self.session, doc)
        return doc

    def reextract(self, doc: SourceDocument) -> None:
        doc.segments.clear()
        self.session.flush()
        self._extract(doc)
        self.session.flush()

    def _extract(self, doc: SourceDocument) -> None:
        for seg in extraction.extract_segments(doc.file_path):
            doc.segments.append(
                TextSegment(page=seg.page, ordinal=seg.ordinal, kind=seg.kind, text=seg.text)
            )

    def _extract_plain(self, doc: SourceDocument) -> None:
        path = Path(doc.file_path)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="latin-1")
        if not text:
            return
        for seg in plain_extraction.extract_segments(text):
            doc.segments.append(
                TextSegment(page=seg.page, ordinal=seg.ordinal, kind=seg.kind, text=seg.text)
            )

    def delete(self, source_id: int) -> None:
        doc = self.sources.get(source_id)
        if doc is not None:
            self.sources.delete(doc)  # PDF file on disk is left untouched
            indexer.remove(self.session, "source", source_id)

    # -- notes / position ---------------------------------------------------

    def update_notes(self, source_id: int, text: str) -> SourceDocument | None:
        doc = self.sources.get(source_id)
        if doc is not None:
            doc.notes_text = text
            self.session.flush()
        return doc

    def update_position(self, source_id: int, page: int, scroll: float = 0.0) -> SourceDocument | None:
        doc = self.sources.get(source_id)
        if doc is not None:
            doc.last_opened_page = page
            doc.last_scroll = scroll
            doc.last_opened_at = now()
            self.session.flush()
        return doc

    def segments_for(self, source_id: int, page: int | None = None) -> list[TextSegment]:
        query = select(TextSegment).where(TextSegment.source_id == source_id)
        if page is not None:
            query = query.where(TextSegment.page == page)
        return list(self.session.scalars(query.order_by(TextSegment.page, TextSegment.ordinal)))

    # -- bookmarks ----------------------------------------------------------

    def add_bookmark(self, source_id: int, page: int, label: str = "") -> Bookmark:
        bookmark = Bookmark(source_id=source_id, page=page, label=label)
        self.session.add(bookmark)
        self.session.flush()
        return bookmark

    def remove_bookmark(self, bookmark_id: int) -> None:
        bookmark = self.session.get(Bookmark, bookmark_id)
        if bookmark is not None:
            self.session.delete(bookmark)
            self.session.flush()

    def bookmarks_for(self, source_id: int) -> list[Bookmark]:
        return list(
            self.session.scalars(
                select(Bookmark).where(Bookmark.source_id == source_id).order_by(Bookmark.page)
            )
        )

    # -- deck association ---------------------------------------------------

    def associate_deck(self, source_id: int, deck_id: int) -> None:
        doc = self.sources.get(source_id)
        deck = self.session.get(Deck, deck_id)
        if doc is not None and deck is not None and deck not in doc.decks:
            doc.decks.append(deck)
            self.session.flush()

    # -- organization (favorite / category / tags / rename) -----------------

    def rename(self, source_id: int, title: str) -> SourceDocument | None:
        doc = self.sources.get(source_id)
        if doc is not None and title.strip():
            doc.title = title.strip()
            self.session.flush()
        return doc

    def set_favorite(self, source_id: int, favorite: bool) -> SourceDocument | None:
        doc = self.sources.get(source_id)
        if doc is not None:
            doc.is_favorite = favorite
            self.session.flush()
        return doc

    def set_category(self, source_id: int, category: str | None) -> SourceDocument | None:
        doc = self.sources.get(source_id)
        if doc is not None:
            doc.category = (category or "").strip() or None
            self.session.flush()
        return doc

    def set_tags(self, source_id: int, names: list[str]) -> SourceDocument | None:
        doc = self.sources.get(source_id)
        if doc is not None:
            doc.tags = [self._get_or_create_tag(n) for n in names]
            self.session.flush()
        return doc

    def categories(self) -> list[str]:
        rows = self.session.scalars(
            select(SourceDocument.category)
            .where(SourceDocument.category.is_not(None))
            .distinct()
        )
        return sorted({c for c in rows if c})

    def list_sources(self) -> list[SourceDocument]:
        """Favorites first, then by category, then title."""
        docs = self.sources.all_ordered()
        return sorted(
            docs,
            key=lambda d: (not d.is_favorite, (d.category or "￿").lower(), d.title.lower()),
        )

    def _get_or_create_tag(self, name: str) -> Tag:
        tag = self.session.scalar(select(Tag).where(Tag.name == name))
        if tag is None:
            tag = Tag(name=name)
            self.session.add(tag)
            self.session.flush()
        return tag
