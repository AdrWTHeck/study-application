from sqlalchemy import select

from data.models import Deck, SourceDocument
from domain.sources.source_service import SourceService


def test_import_creates_source_with_segments(db, sample_pdf):
    with db.session() as s:
        doc = SourceService(s).import_pdf(str(sample_pdf), title="Sample")
        assert doc.id is not None
        assert doc.page_count == 1
        assert len(doc.segments) >= 2


def test_import_text_creates_source_with_segments(db, tmp_path):
    text_file = tmp_path / "notes.txt"
    text_file.write_text("My heading\n\nThis is a plain text paragraph.\n", encoding="utf-8")
    with db.session() as s:
        doc = SourceService(s).import_text(str(text_file))
        assert doc.kind == "text"
        assert doc.page_count == 1
        assert len(doc.segments) >= 2
        assert doc.segments[0].kind == "heading"


def test_import_markdown_preserves_headings(db, tmp_path):
    markdown_file = tmp_path / "notes.md"
    markdown_file.write_text("# Heading\n\nParagraph text.\n", encoding="utf-8")
    with db.session() as s:
        doc = SourceService(s).import_text(str(markdown_file), kind="markdown")
        assert doc.kind == "markdown"
        assert doc.page_count == 1
        assert any(seg.kind == "heading" for seg in doc.segments)


def test_notes_and_position_persist(db, sample_pdf):
    with db.session() as s:
        svc = SourceService(s)
        doc = svc.import_pdf(str(sample_pdf))
        svc.update_notes(doc.id, "my notes")
        svc.update_position(doc.id, 1, 0.5)
        reloaded = svc.sources.get(doc.id)
        assert reloaded.notes_text == "my notes"
        assert reloaded.last_scroll == 0.5
        assert reloaded.last_opened_at is not None


def test_import_creates_working_copy(db, sample_pdf, tmp_path):
    lib = str(tmp_path / "library")
    with db.session() as s:
        svc = SourceService(s)
        doc = svc.import_pdf(str(sample_pdf), library_dir=lib)
        assert doc.working_copy_path is not None
        assert doc.original_archived is True
        from pathlib import Path
        assert Path(doc.working_copy_path).exists()
        assert (Path(lib) / "originals" / f"{doc.id}.pdf.zip").exists()


def test_bookmarks(db, sample_pdf):
    with db.session() as s:
        svc = SourceService(s)
        doc = svc.import_pdf(str(sample_pdf))
        svc.add_bookmark(doc.id, page=1, label="intro")
        assert len(svc.bookmarks_for(doc.id)) == 1


def test_deck_association(db, sample_pdf):
    with db.session() as s:
        svc = SourceService(s)
        doc = svc.import_pdf(str(sample_pdf))
        deck = s.scalar(select(Deck).where(Deck.is_default.is_(True)))
        svc.associate_deck(doc.id, deck.id)
        assert deck in svc.sources.get(doc.id).decks


def test_delete_keeps_file_on_disk(db, sample_pdf):
    with db.session() as s:
        svc = SourceService(s)
        doc = svc.import_pdf(str(sample_pdf))
        source_id = doc.id
        svc.delete(source_id)
        assert svc.sources.get(source_id) is None
    assert sample_pdf.exists()  # original PDF is never deleted


def test_favorite_category_tags(db, sample_pdf):
    with db.session() as s:
        svc = SourceService(s)
        doc = svc.import_pdf(str(sample_pdf))
        svc.set_favorite(doc.id, True)
        svc.set_category(doc.id, "Biology")
        svc.set_tags(doc.id, ["exam", "ch1"])
        reloaded = svc.sources.get(doc.id)
        assert reloaded.is_favorite is True
        assert reloaded.category == "Biology"
        assert {t.name for t in reloaded.tags} == {"exam", "ch1"}


def test_set_category_blank_clears(db, sample_pdf):
    with db.session() as s:
        svc = SourceService(s)
        doc = svc.import_pdf(str(sample_pdf))
        svc.set_category(doc.id, "X")
        svc.set_category(doc.id, "")
        assert svc.sources.get(doc.id).category is None


def test_rename_source(db, sample_pdf):
    with db.session() as s:
        svc = SourceService(s)
        doc = svc.import_pdf(str(sample_pdf), title="Old")
        svc.rename(doc.id, "New")
        assert svc.sources.get(doc.id).title == "New"


def test_categories_and_favorites_first_ordering(db, sample_pdf):
    with db.session() as s:
        svc = SourceService(s)
        a = svc.import_pdf(str(sample_pdf), title="Alpha")
        b = svc.import_pdf(str(sample_pdf), title="Beta")
        c = svc.import_pdf(str(sample_pdf), title="Gamma")
        svc.set_category(a.id, "Zoology")
        svc.set_category(b.id, "Anatomy")
        svc.set_favorite(c.id, True)
        assert svc.categories() == ["Anatomy", "Zoology"]
        ordered = [d.title for d in svc.list_sources()]
        assert ordered[0] == "Gamma"  # favorite first
        assert ordered.index("Beta") < ordered.index("Alpha")  # Anatomy before Zoology
