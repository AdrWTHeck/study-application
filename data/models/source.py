"""PDF sources and their derived data: text segments, bookmarks.

A SourceDocument references a PDF on disk (the original file is never modified).
A working copy is created on import; annotations are written into that copy as
real PDF annotation objects via PyMuPDF. The original is archived as a zip.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.clock import now
from data.db import Base

if TYPE_CHECKING:
    from data.models.deck import Deck
    from data.models.tag import Tag

deck_sources = Table(
    "deck_sources",
    Base.metadata,
    Column("deck_id", ForeignKey("decks.id", ondelete="CASCADE"), primary_key=True),
    Column("source_id", ForeignKey("source_documents.id", ondelete="CASCADE"), primary_key=True),
)

source_tags = Table(
    "source_tags",
    Base.metadata,
    Column("source_id", ForeignKey("source_documents.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), default="pdf", server_default="pdf", nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    last_opened_page: Mapped[int] = mapped_column(Integer, default=1)
    last_scroll: Mapped[float] = mapped_column(Float, default=0.0)
    notes_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # --- organization (mirrors decks: favorite + category + tags)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    # --- PDF working copy (annotations written here; original archived as zip)
    working_copy_path: Mapped[str | None] = mapped_column(String(1024), nullable=True, default=None)
    original_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    segments: Mapped[list["TextSegment"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    tags: Mapped[list["Tag"]] = relationship(secondary=source_tags)
    bookmarks: Mapped[list["Bookmark"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    decks: Mapped[list["Deck"]] = relationship(secondary=deck_sources)


class TextSegment(Base):
    __tablename__ = "text_segments"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id", ondelete="CASCADE"))
    page: Mapped[int] = mapped_column(Integer, default=1)
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    kind: Mapped[str] = mapped_column(String(10), default="body")  # heading | body
    text: Mapped[str] = mapped_column(Text, default="", nullable=False)

    source: Mapped["SourceDocument"] = relationship(back_populates="segments")


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id", ondelete="CASCADE"))
    page: Mapped[int] = mapped_column(Integer, default=1)
    label: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    source: Mapped["SourceDocument"] = relationship(back_populates="bookmarks")
