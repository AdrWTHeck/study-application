"""Tests for the standalone EPUB ↔ PDF converter.

Covers preflight validation ("many checks"), both conversion directions,
progress reporting, and cancellation/atomic-output guarantees.
"""
import io

import pytest

from converter import epub_to_pdf, pdf_to_epub


@pytest.fixture
def sample_epub(tmp_path):
    """A tiny two-chapter EPUB with one embedded image."""
    from ebooklib import epub
    from PIL import Image

    book = epub.EpubBook()
    book.set_identifier("test-epub")
    book.set_title("Test Book")
    book.set_language("en")
    book.add_author("Tester")

    buf = io.BytesIO()
    Image.new("RGB", (16, 16), (40, 90, 235)).save(buf, "PNG")
    book.add_item(epub.EpubItem(
        uid="img1", file_name="images/dot.png", media_type="image/png", content=buf.getvalue()
    ))

    c1 = epub.EpubHtml(title="Chapter One", file_name="c1.xhtml", lang="en")
    c1.content = (b"<html><body><h1>Chapter One</h1>"
                  b"<p>Hello world paragraph with enough words.</p>"
                  b"<p><img src='images/dot.png'/></p></body></html>")
    c2 = epub.EpubHtml(title="Chapter Two", file_name="c2.xhtml", lang="en")
    c2.content = (b"<html><body><h2>Chapter Two</h2>"
                  b"<p>Second chapter text.</p>"
                  b"<ul><li>one</li><li>two</li></ul></body></html>")
    for c in (c1, c2):
        book.add_item(c)
    book.toc = (epub.Link("c1.xhtml", "Chapter One", "c1"),
                epub.Link("c2.xhtml", "Chapter Two", "c2"))
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", c1, c2]

    path = tmp_path / "sample.epub"
    epub.write_epub(str(path), book)
    return path


# --- preflight validation ---------------------------------------------------

def test_missing_input_returns_false(tmp_path):
    assert epub_to_pdf(str(tmp_path / "nope.epub"), str(tmp_path / "out.pdf")) is False
    assert pdf_to_epub(str(tmp_path / "nope.pdf"), str(tmp_path / "out.epub")) is False


def test_wrong_extension_returns_false(sample_pdf, sample_epub, tmp_path):
    # PDF passed to the EPUB→PDF entry point, and vice versa.
    assert epub_to_pdf(str(sample_pdf), str(tmp_path / "out.pdf")) is False
    assert pdf_to_epub(str(sample_epub), str(tmp_path / "out.epub")) is False


def test_empty_input_returns_false(tmp_path):
    empty = tmp_path / "empty.epub"
    empty.write_bytes(b"")
    assert epub_to_pdf(str(empty), str(tmp_path / "out.pdf")) is False


def test_bad_output_dir_returns_false(sample_epub, tmp_path):
    bad = tmp_path / "does" / "not" / "exist" / "out.pdf"
    assert epub_to_pdf(str(sample_epub), str(bad)) is False


# --- happy path -------------------------------------------------------------

def test_epub_to_pdf_produces_valid_pdf(sample_epub, tmp_path):
    out = tmp_path / "out.pdf"
    events = []
    ok = epub_to_pdf(str(sample_epub), str(out),
                     {"include_images": True},
                     progress_callback=lambda p, m: events.append((p, m)))
    assert ok is True
    assert out.exists() and out.stat().st_size > 0
    assert out.read_bytes()[:5] == b"%PDF-"
    assert events and events[0][0] == 0 and events[-1][0] == 100


def test_pdf_to_epub_produces_valid_epub(sample_pdf, tmp_path):
    import ebooklib
    from ebooklib import epub

    out = tmp_path / "out.epub"
    events = []
    ok = pdf_to_epub(str(sample_pdf), str(out),
                     {"title": "Converted", "author": "Me"},
                     progress_callback=lambda p, m: events.append((p, m)))
    assert ok is True
    assert out.exists() and out.stat().st_size > 0

    book = epub.read_epub(str(out))
    assert (book.get_metadata("DC", "title")[0][0]) == "Converted"
    assert list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
    assert events[-1][0] == 100


def test_epub_to_pdf_handles_oversized_image(tmp_path):
    """A tall full-page image must be scaled to fit, not abort the conversion.

    Regression for the 729 MB real-run LayoutError ("Flowable Image too large").
    """
    from ebooklib import epub
    from PIL import Image

    book = epub.EpubBook()
    book.set_identifier("big-img")
    book.set_title("Big Image Book")
    book.set_language("en")
    book.add_author("Tester")

    buf = io.BytesIO()
    Image.new("RGB", (1000, 1500), (200, 50, 50)).save(buf, "PNG")  # taller than a page
    book.add_item(epub.EpubItem(
        uid="big", file_name="images/big.png", media_type="image/png", content=buf.getvalue()
    ))
    ch = epub.EpubHtml(title="Big", file_name="big.xhtml", lang="en")
    ch.content = b"<html><body><h1>Big</h1><p><img src='images/big.png'/></p></body></html>"
    book.add_item(ch)
    book.toc = (epub.Link("big.xhtml", "Big", "big"),)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", ch]

    src = tmp_path / "big.epub"
    epub.write_epub(str(src), book)

    out = tmp_path / "big.pdf"
    assert epub_to_pdf(str(src), str(out), {"include_images": True}) is True
    assert out.exists() and out.read_bytes()[:5] == b"%PDF-"


def test_round_trip_preserves_image(sample_epub, tmp_path):
    import ebooklib
    from ebooklib import epub

    pdf = tmp_path / "mid.pdf"
    assert epub_to_pdf(str(sample_epub), str(pdf), {"include_images": True})
    epub_out = tmp_path / "back.epub"
    assert pdf_to_epub(str(pdf), str(epub_out), {"include_images": True})

    book = epub.read_epub(str(epub_out))
    assert list(book.get_items_of_type(ebooklib.ITEM_IMAGE)), "image lost in round trip"


# --- cancellation / atomicity ----------------------------------------------

def test_cancel_aborts_and_leaves_no_partial(sample_pdf, tmp_path):
    out = tmp_path / "out.epub"
    ok = pdf_to_epub(str(sample_pdf), str(out), cancel_callback=lambda: True)
    assert ok is False
    assert not out.exists()
    assert not (tmp_path / "out.epub.part").exists()


def test_failure_leaves_no_partial(tmp_path):
    # Corrupt "pdf" that passes extension/size checks but fails to open.
    bogus = tmp_path / "bogus.pdf"
    bogus.write_bytes(b"not really a pdf" * 100)
    out = tmp_path / "out.epub"
    assert pdf_to_epub(str(bogus), str(out)) is False
    assert not out.exists()
    assert not (tmp_path / "out.epub.part").exists()
