"""PDF ingestion service — Phase 2 (FR-2-01 through FR-2-08).

Build order within this file matches the SDD:
  upload → extract → retry_extraction → delete_source → associate/disassociate_deck
"""
from __future__ import annotations

import logging
from pathlib import Path

import pdfplumber

from models import get_session
from models.deck import Deck
from models.source_document import SourceDocument, TextSegment
from services.ingestion.text_processor import TextProcessor

logger = logging.getLogger(__name__)


class PDFService:
    """Owns all PDF lifecycle operations.

    Each public method manages its own session, commits on success, and
    rolls back on unexpected failure.  This keeps the service stateless and
    safe to call from any context.
    """

    def __init__(self) -> None:
        self._processor = TextProcessor()

    # ------------------------------------------------------------------
    # FR-2-01 — Upload
    # ------------------------------------------------------------------

    def upload(self, file_path: str) -> SourceDocument:
        """Create a SourceDocument and immediately run text extraction.

        Returns the persisted SourceDocument with extraction_status set to
        either "complete" or "failed".
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")

        # Get page count before opening a DB session so any pdfplumber error
        # surfaces cleanly.
        try:
            with pdfplumber.open(str(path)) as pdf:
                page_count = len(pdf.pages)
        except Exception:
            logger.exception("Could not open PDF for page count: %s", path)
            raise

        session = get_session()
        try:
            doc = SourceDocument(
                filename=path.name,
                file_path=str(path),
                page_count=page_count,
                extraction_status="pending",
            )
            session.add(doc)
            session.flush()  # assigns doc.id without committing

            self._extract_with_session(session, doc)
            session.commit()
            session.refresh(doc)
            logger.info(
                "Uploaded %r — %d page(s), status=%s, segments=%d",
                doc.filename,
                page_count,
                doc.extraction_status,
                len(doc.text_segments),
            )
            return doc
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ------------------------------------------------------------------
    # FR-2-02 — Extraction (public re-entry point)
    # ------------------------------------------------------------------

    def extract(self, source_id: int) -> list[TextSegment]:
        """Run (or re-run) extraction for an existing SourceDocument.

        Returns the list of TextSegment records created.
        """
        session = get_session()
        try:
            doc = session.get(SourceDocument, source_id)
            if doc is None:
                raise ValueError(f"SourceDocument {source_id} not found.")
            self._extract_with_session(session, doc)
            session.commit()
            return (
                session.query(TextSegment)
                .filter(TextSegment.source_document_id == source_id)
                .order_by(TextSegment.page_number, TextSegment.segment_index)
                .all()
            )
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def retry_extraction(self, source_id: int) -> None:
        """Re-run extraction on a previously failed SourceDocument (FR-2-02).

        Sets extraction_status to "complete" or "failed" and commits.
        Never raises on extraction errors — status reflects the outcome.
        """
        session = get_session()
        try:
            doc = session.get(SourceDocument, source_id)
            if doc is None:
                raise ValueError(f"SourceDocument {source_id} not found.")
            self._extract_with_session(session, doc)
            session.commit()
        except ValueError:
            session.rollback()
            raise
        except Exception:
            # _extract_with_session already set status="failed" and flushed.
            try:
                session.commit()
            except Exception:
                session.rollback()
            raise
        finally:
            session.close()

    # ------------------------------------------------------------------
    # FR-2-03 — Delete source
    # ------------------------------------------------------------------

    def delete_source(self, source_id: int) -> None:
        """Delete SourceDocument, its TextSegments, and deck_sources entries.

        The original PDF file on disk is NOT deleted (CON-10).
        TextSegments are removed by the cascade defined on the ORM model.
        deck_sources entries are removed by the DB-level ON DELETE CASCADE.
        """
        session = get_session()
        try:
            doc = session.get(SourceDocument, source_id)
            if doc is None:
                return
            session.delete(doc)
            session.commit()
            logger.info("Deleted SourceDocument id=%d (%r).", source_id, doc.filename)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ------------------------------------------------------------------
    # FR-2-04 — Deck association
    # ------------------------------------------------------------------

    def associate_deck(self, source_id: int, deck_id: int) -> None:
        """Add a deck_sources link between *source_id* and *deck_id*."""
        session = get_session()
        try:
            doc = session.get(SourceDocument, source_id)
            deck = session.get(Deck, deck_id)
            if doc is None or deck is None:
                raise ValueError(
                    f"SourceDocument {source_id} or Deck {deck_id} not found."
                )
            if deck not in doc.decks:
                doc.decks.append(deck)
                session.commit()
                logger.debug("Associated source %d with deck %d.", source_id, deck_id)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def disassociate_deck(self, source_id: int, deck_id: int) -> None:
        """Remove the deck_sources link between *source_id* and *deck_id*."""
        session = get_session()
        try:
            doc = session.get(SourceDocument, source_id)
            deck = session.get(Deck, deck_id)
            if doc is None or deck is None:
                return
            if deck in doc.decks:
                doc.decks.remove(deck)
                session.commit()
                logger.debug("Disassociated source %d from deck %d.", source_id, deck_id)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ------------------------------------------------------------------
    # FR-2-08 — Table extraction stub
    # ------------------------------------------------------------------

    def extract_tables(self, file_path: str) -> list:
        """Returns [] in Sprint 1.  Reserved for Sprint 2 table recognition."""
        return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_with_session(self, session, doc: SourceDocument) -> None:
        """Core extraction logic; sets doc.extraction_status and flushes.

        Deletes any existing segments for *doc* before re-extracting so this
        method is safe to call on both first-time extraction and retries.
        Never raises on pdfplumber/TextProcessor errors — status reflects
        the outcome.  Callers are responsible for commit/rollback.
        """
        # Clear stale segments.
        session.query(TextSegment).filter(
            TextSegment.source_document_id == doc.id
        ).delete(synchronize_session="fetch")

        try:
            segment_count = 0
            with pdfplumber.open(doc.file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    raw_text = page.extract_text() or ""
                    cleaned = self._processor.clean(raw_text)
                    chunks = self._processor.segment(cleaned)

                    for idx, chunk in enumerate(chunks):
                        session.add(
                            TextSegment(
                                source_document_id=doc.id,
                                page_number=page_num,
                                segment_index=idx,
                                text=chunk,
                            )
                        )
                        segment_count += 1

            doc.extraction_status = "complete"
            logger.debug(
                "Extracted %d segment(s) from source_id=%d.", segment_count, doc.id
            )
        except Exception:
            doc.extraction_status = "failed"
            logger.exception("Extraction failed for source_id=%d.", doc.id)

        session.flush()
