"""EPUB ↔ PDF converter.

Public API:
    epub_to_pdf(epub_path, output_pdf_path, options, progress_callback, cancel_callback) -> bool
    pdf_to_epub(pdf_path, output_epub_path, options, progress_callback, cancel_callback) -> bool

Design notes (see docs / plan):
  * Streaming — work proceeds one chapter (EPUB→PDF) or one page (PDF→EPUB) at a
    time so peak memory stays bounded, instead of loading a whole 1 GB file at
    once. Images are streamed to a temp dir at full resolution, never held all
    in RAM together.
  * Progress + cancellation — both entry points accept an optional
    ``progress_callback(percent, message)`` and ``cancel_callback() -> bool``.
    The caller (a Qt worker thread) bridges these to the GUI. The converter
    itself owns all the data on one thread, so there is no shared-memory lock on
    the data path; cancellation is a single synchronized flag checked between
    units of work.
  * Atomic output — the result is written to a temp file and renamed into place
    only on success, so a cancelled or failed run never leaves a half-written
    file behind.

All functions other than the two entry points are internal helpers.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
import warnings
from pathlib import Path
from typing import Callable

# EPUB chapter documents are XHTML; we parse them with the lxml HTML parser,
# which is intentional and reliable enough here. Silence bs4's nudge to use the
# XML parser so it doesn't spam the converter log on every chapter.
try:  # pragma: no cover - import guard
    from bs4 import XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
except Exception:  # bs4 not importable yet / older version without the warning
    pass

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_log_handler = logging.FileHandler("converter.log", encoding="utf-8")
_log_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(_log_handler)

# Warn (not fail) once an input crosses this size — large jobs are slow but valid.
_LARGE_FILE_WARN_BYTES = 250 * 1024 * 1024  # 250 MB

ProgressCallback = Callable[[int, str], None]
CancelCallback = Callable[[], bool]


class _Cancelled(Exception):
    """Raised internally to unwind cleanly when the caller requests cancel."""


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _emit(progress_callback: ProgressCallback | None, percent: int, message: str) -> None:
    """Report progress to the caller (if any) and mirror it to the log."""
    pct = max(0, min(100, int(percent)))
    logger.info("[%3d%%] %s", pct, message)
    if progress_callback is not None:
        try:
            progress_callback(pct, message)
        except Exception:  # never let a UI callback break the conversion
            logger.warning("progress_callback raised", exc_info=True)


def _check_cancel(cancel_callback: CancelCallback | None) -> None:
    """Raise :class:`_Cancelled` if the caller has asked to stop."""
    if cancel_callback is not None and cancel_callback():
        raise _Cancelled()


def _preflight(input_path: str, expected_ext: str, output_path: str) -> bool:
    """Validate inputs/outputs before doing any heavy work ("many checks")."""
    if not os.path.isfile(input_path):
        logger.error("Input file not found: %s", input_path)
        return False
    if not input_path.lower().endswith(expected_ext):
        logger.error("Expected a %s file: %s", expected_ext, input_path)
        return False

    try:
        size = os.path.getsize(input_path)
    except OSError as exc:
        logger.error("Cannot stat input file: %s", exc)
        return False
    if size == 0:
        logger.error("Input file is empty: %s", input_path)
        return False
    if size > _LARGE_FILE_WARN_BYTES:
        logger.warning("Large input (%.1f MB) — conversion may take a while: %s",
                       size / (1024 * 1024), input_path)

    out_dir = os.path.dirname(os.path.abspath(output_path)) or "."
    if not os.path.isdir(out_dir):
        logger.error("Output directory does not exist: %s", out_dir)
        return False
    if not os.access(out_dir, os.W_OK):
        logger.error("Output directory is not writable: %s", out_dir)
        return False

    # Verify there is plausibly enough free disk for the output (size of the
    # input is a generous lower bound for either direction).
    try:
        free = shutil.disk_usage(out_dir).free
        if free < size:
            logger.error("Not enough free disk in %s (%.1f MB free, need ~%.1f MB)",
                         out_dir, free / (1024 * 1024), size / (1024 * 1024))
            return False
    except OSError:
        pass  # disk_usage unsupported — skip rather than block

    return True


def _atomic_replace(tmp_path: str, output_path: str) -> None:
    """Move a fully written temp file into its final location atomically."""
    os.replace(tmp_path, output_path)


def _rl_escape(text: str) -> str:
    """Escape text for ReportLab's XML-based paragraph parser."""
    if not text:
        return ""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Strip non-printable control characters (keep tab, newline).
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


# ---------------------------------------------------------------------------
# EPUB → PDF
# ---------------------------------------------------------------------------

def epub_to_pdf(
    epub_path: str,
    output_pdf_path: str,
    options: dict | None = None,
    progress_callback: ProgressCallback | None = None,
    cancel_callback: CancelCallback | None = None,
) -> bool:
    """Convert an EPUB file to PDF.

    Args:
        epub_path: Path to the source .epub file.
        output_pdf_path: Destination path for the generated .pdf file.
        options:
            font_size (int, default 12) — body text size in points.
            margin (int, default 40) — page margin in points.
            include_cover (bool, default True) — add a title/author cover page.
            include_toc (bool, default True) — add a table of contents page.
            include_images (bool, default True) — embed chapter images.
        progress_callback: optional ``(percent, message)`` reporter.
        cancel_callback: optional ``() -> bool``; return True to abort.

    Returns:
        True on success, False on any error/cancel (details in converter.log).
    """
    opts: dict = {
        "font_size": 12,
        "margin": 40,
        "include_cover": True,
        "include_toc": True,
        "include_images": True,
    }
    if options:
        opts.update(options)

    _emit(progress_callback, 0, "Validating…")
    if not _preflight(epub_path, ".epub", output_pdf_path):
        return False

    work_dir = tempfile.mkdtemp(prefix="conv_epub2pdf_")
    tmp_out = output_pdf_path + ".part"
    try:
        ok = _epub_to_pdf_streaming(
            epub_path, tmp_out, opts, work_dir, progress_callback, cancel_callback
        )
        if not ok:
            return False
        _atomic_replace(tmp_out, output_pdf_path)
        _emit(progress_callback, 100, "Done")
        logger.info("PDF written: %s", output_pdf_path)
        return True
    except _Cancelled:
        logger.info("epub_to_pdf cancelled by user")
        _emit(progress_callback, 0, "Cancelled")
        return False
    except Exception as exc:
        logger.error("epub_to_pdf failed: %s", exc, exc_info=True)
        return False
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        if os.path.exists(tmp_out):
            try:
                os.remove(tmp_out)
            except OSError:
                pass


def _epub_to_pdf_streaming(
    epub_path: str,
    tmp_out: str,
    opts: dict,
    work_dir: str,
    progress_callback: ProgressCallback | None,
    cancel_callback: CancelCallback | None,
) -> bool:
    """Render the EPUB chapter-by-chapter into temp PDFs, then merge them.

    Peak memory stays at roughly one chapter: each chapter's flowables are built,
    written to its own temp PDF, then released before the next chapter. Images
    are extracted to disk up front (one at a time) so they are referenced by
    path during rendering rather than held in RAM.
    """
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup

    _emit(progress_callback, 3, "Opening EPUB…")
    book = epub.read_epub(epub_path, options={"ignore_ncx": True})

    meta_title = book.get_metadata("DC", "title")
    meta_author = book.get_metadata("DC", "creator")
    title = meta_title[0][0] if meta_title else Path(epub_path).stem
    author = meta_author[0][0] if meta_author else "Unknown"

    include_images = bool(opts.get("include_images", True))

    # Stream images to the temp dir one at a time, keyed by basename for
    # resolving <img src> references later. Never hold them all in memory.
    image_paths: dict[str, str] = {}
    if include_images:
        _emit(progress_callback, 6, "Extracting images…")
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            _check_cancel(cancel_callback)
            name = os.path.basename(item.get_name())
            if not name:
                continue
            dest = os.path.join(work_dir, f"img_{len(image_paths)}_{name}")
            try:
                with open(dest, "wb") as fh:
                    fh.write(item.get_content())
                image_paths[name] = dest
            except OSError:
                logger.warning("Could not write image %s", name)

    styles = _make_pdf_styles(int(opts.get("font_size", 12)))
    margin = int(opts.get("margin", 40))

    # Collect the parts to merge, in final document order.
    part_paths: list[str] = []

    # Cover (title/author text page).
    if bool(opts.get("include_cover", True)):
        cover_path = os.path.join(work_dir, "part_cover.pdf")
        _build_cover_pdf(title, author, cover_path, styles, margin)
        part_paths.append(cover_path)

    # First pass over the spine: render each chapter to its own temp PDF and
    # remember its title for the table of contents.
    spine_items = [iid for iid, _ in book.spine]
    chapter_titles: list[str] = []
    chapter_parts: list[str] = []
    total = max(1, len(spine_items))

    for idx, item_id in enumerate(spine_items):
        _check_cancel(cancel_callback)
        item = book.get_item_with_id(item_id)
        if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        html = item.get_content().decode("utf-8", errors="replace")
        blocks = _parse_html_to_blocks(html, BeautifulSoup)
        if not any(kind != "img" and text.strip() for kind, text in blocks):
            # Skip documents with no readable text (nav pages, blank spacers).
            if not any(kind == "img" for kind, _ in blocks):
                continue
        ch_title = _first_heading(blocks) or f"Chapter {len(chapter_titles) + 1}"
        chapter_titles.append(ch_title)

        part_path = os.path.join(work_dir, f"part_ch_{idx:04d}.pdf")
        _build_chapter_pdf(
            ch_title, blocks, part_path, styles, margin, image_paths if include_images else {}
        )
        chapter_parts.append(part_path)

        # 15..95% spread across chapters.
        pct = 15 + int(80 * (idx + 1) / total)
        _emit(progress_callback, pct, f"Rendering chapter {len(chapter_titles)} of {total}…")

    # Table of contents (built after titles are known; inserted after cover).
    if bool(opts.get("include_toc", True)) and chapter_titles:
        toc_path = os.path.join(work_dir, "part_toc.pdf")
        _build_toc_pdf(chapter_titles, toc_path, styles, margin)
        part_paths.append(toc_path)

    part_paths.extend(chapter_parts)

    if not part_paths:
        # Nothing renderable — emit a single placeholder page so output is valid.
        placeholder = os.path.join(work_dir, "part_empty.pdf")
        _build_chapter_pdf("(No content found)", [], placeholder, styles, margin, {})
        part_paths.append(placeholder)

    # Merge all parts into the final PDF with PyMuPDF (bounded memory).
    _emit(progress_callback, 96, "Assembling PDF…")
    _merge_pdfs(part_paths, tmp_out)
    return True


def _make_pdf_styles(font_size: int) -> dict:
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    base = getSampleStyleSheet()
    return {
        "normal": ParagraphStyle(
            "ConvNormal", parent=base["Normal"],
            fontSize=font_size, leading=font_size * 1.5, spaceAfter=6,
        ),
        "h1": ParagraphStyle(
            "ConvH1", parent=base["Heading1"],
            fontSize=font_size + 4, leading=(font_size + 4) * 1.4,
            spaceBefore=14, spaceAfter=8,
        ),
        "cover_title": ParagraphStyle(
            "ConvCoverTitle", parent=base["Title"],
            fontSize=font_size + 14, leading=(font_size + 14) * 1.3, alignment=TA_CENTER,
        ),
        "cover_author": ParagraphStyle(
            "ConvCoverAuthor", parent=base["Normal"],
            fontSize=font_size + 2, leading=(font_size + 2) * 1.5, alignment=TA_CENTER,
        ),
        "toc_heading": ParagraphStyle(
            "ConvTocHeading", parent=base["Heading2"], fontSize=font_size + 6, spaceAfter=12,
        ),
        "toc_entry": ParagraphStyle(
            "ConvTocEntry", parent=base["Normal"], fontSize=font_size, leading=font_size * 1.7,
        ),
    }


def _new_doc(path: str, margin: int):
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate

    return SimpleDocTemplate(
        path, pagesize=letter,
        leftMargin=margin, rightMargin=margin, topMargin=margin, bottomMargin=margin,
    )


def _build_cover_pdf(title: str, author: str, path: str, styles: dict, margin: int) -> None:
    from reportlab.platypus import Paragraph, Spacer

    doc = _new_doc(path, margin)
    story = [
        Spacer(1, 120),
        Paragraph(_rl_escape(title), styles["cover_title"]),
        Spacer(1, 24),
        Paragraph(_rl_escape(author), styles["cover_author"]),
    ]
    doc.build(story)


def _build_toc_pdf(titles: list[str], path: str, styles: dict, margin: int) -> None:
    from reportlab.platypus import Paragraph, Spacer

    doc = _new_doc(path, margin)
    story = [Paragraph("Table of Contents", styles["toc_heading"]), Spacer(1, 8)]
    for i, t in enumerate(titles, 1):
        story.append(Paragraph(f"{i}.  {_rl_escape(t)}", styles["toc_entry"]))
    doc.build(story)


def _build_chapter_pdf(
    title: str,
    blocks: list[tuple[str, str]],
    path: str,
    styles: dict,
    margin: int,
    image_paths: dict[str, str],
) -> None:
    """Render a single chapter (heading + interleaved text/images) to its own PDF.

    Builds with images first; if ReportLab can't lay the chapter out (e.g. a
    pathological image), it retries text-only so one bad flowable can never abort
    the whole conversion. A fresh document + story is required for the retry
    because ReportLab consumes the story and a doc cannot be reused after a
    failed build.
    """
    try:
        _new_doc(path, margin).build(_chapter_story(title, blocks, styles, margin, image_paths))
    except Exception:
        logger.warning("Chapter '%s' failed to render with images; retrying text-only", title)
        _new_doc(path, margin).build(_chapter_story(title, blocks, styles, margin, {}))


def _chapter_story(
    title: str,
    blocks: list[tuple[str, str]],
    styles: dict,
    margin: int,
    image_paths: dict[str, str],
) -> list:
    """Build a fresh ReportLab flowable list for one chapter.

    Images are scaled to fit the *true* usable frame: ReportLab insets each Frame
    by ~6 pt per side, so we fit within (page area − 12 pt) × a small safety
    factor — guaranteeing an image never overflows and triggers a LayoutError.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import Paragraph, Spacer, Image as RLImage

    # Usable frame = page minus margins minus ReportLab's per-side frame padding.
    max_w = (letter[0] - 2 * margin - 12) * 0.98
    max_h = (letter[1] - 2 * margin - 12) * 0.98

    story: list = [Paragraph(_rl_escape(title), styles["h1"])]

    for kind, value in blocks:
        if kind == "img":
            img_path = image_paths.get(os.path.basename(value))
            if not img_path or not os.path.isfile(img_path):
                continue
            size = _validated_image_size(img_path)
            if size is None:  # corrupt/unsupported — skip rather than fail the page
                logger.warning("Skipping unreadable image %s", value)
                continue
            iw, ih = size
            scale = min(max_w / iw, max_h / ih, 1.0)
            w, h = iw * scale, ih * scale
            try:
                story.append(RLImage(img_path, width=w, height=h))
                story.append(Spacer(1, 6))
            except Exception:
                logger.warning("Skipping image that failed to render %s", value)
            continue

        text = value.strip()
        if not text:
            continue
        if kind == "h":
            story.append(Paragraph(_rl_escape(text), styles["h1"]))
        elif kind == "li":
            story.append(Paragraph("• " + _rl_escape(text), styles["normal"]))
        else:  # "p"
            story.append(Paragraph(_rl_escape(text), styles["normal"]))
            story.append(Spacer(1, 3))

    return story


def _validated_image_size(img_path: str) -> tuple[int, int] | None:
    """Fully decode an image with PIL to confirm it is renderable.

    Returns (width, height) if the image loads cleanly, else None. Forcing a
    full ``load()`` here means a corrupt or truncated image is rejected *before*
    it can reach ReportLab's ``build()`` and abort the whole conversion.
    """
    try:
        from PIL import Image
        with Image.open(img_path) as im:
            im.load()
            w, h = im.size
        return (w, h) if w > 0 and h > 0 else None
    except Exception:
        return None


def _merge_pdfs(part_paths: list[str], output_path: str) -> None:
    import fitz  # PyMuPDF

    merged = fitz.open()
    try:
        for part in part_paths:
            with fitz.open(part) as src:
                merged.insert_pdf(src)
        merged.save(output_path)
    finally:
        merged.close()


def _parse_html_to_blocks(html_content: str, beautifulsoup) -> list[tuple[str, str]]:
    """Parse chapter HTML into ordered blocks: ("h"|"p"|"li"|"img", value).

    Text blocks carry their text; image blocks carry the raw ``src`` reference.
    Order is preserved so the PDF reads like the source.
    """
    from bs4 import NavigableString, Tag

    # EPUB documents are XHTML; parsing them with the lxml *HTML* parser is fine
    # and reliable here. Suppress bs4's "use the XML parser" nudge locally so it
    # never reaches the log/test output regardless of global warning filters.
    with warnings.catch_warnings():
        try:
            from bs4 import XMLParsedAsHTMLWarning
            warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        except Exception:
            warnings.simplefilter("ignore")
        soup = beautifulsoup(html_content, "lxml")
    body = soup.find("body") or soup
    blocks: list[tuple[str, str]] = []

    def emit_imgs(node: "Tag") -> None:
        for img in node.find_all("img"):
            src = img.get("src") or ""
            if src:
                blocks.append(("img", src))

    def walk(node: object) -> None:
        if isinstance(node, NavigableString) or not isinstance(node, Tag):
            return
        tag = (node.name or "").lower()
        if tag in {"style", "script", "head"}:
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            blocks.append(("h", node.get_text(" ", strip=True)))
            emit_imgs(node)
            return
        if tag == "p":
            text = node.get_text(" ", strip=True)
            if text:
                blocks.append(("p", text))
            emit_imgs(node)
            return
        if tag == "li":
            text = node.get_text(" ", strip=True)
            if text:
                blocks.append(("li", text))
            emit_imgs(node)
            return
        if tag == "img":
            src = node.get("src") or ""
            if src:
                blocks.append(("img", src))
            return
        for child in node.children:
            walk(child)

    walk(body)
    return blocks


def _first_heading(blocks: list[tuple[str, str]]) -> str:
    for kind, value in blocks:
        if kind == "h" and value.strip():
            return value.strip()
    return ""


# ---------------------------------------------------------------------------
# PDF → EPUB
# ---------------------------------------------------------------------------

def pdf_to_epub(
    pdf_path: str,
    output_epub_path: str,
    options: dict | None = None,
    progress_callback: ProgressCallback | None = None,
    cancel_callback: CancelCallback | None = None,
) -> bool:
    """Convert a PDF file to EPUB.

    Args:
        pdf_path: Path to the source .pdf file.
        output_epub_path: Destination path for the generated .epub file.
        options:
            title (str | None) — override book title (falls back to metadata).
            author (str | None) — override author (falls back to metadata).
            include_images (bool, default True) — embed raster images.
            pages_per_chapter (int, default 1) — how many PDF pages per chapter.
        progress_callback: optional ``(percent, message)`` reporter.
        cancel_callback: optional ``() -> bool``; return True to abort.

    Returns:
        True on success, False on any error/cancel (details in converter.log).
    """
    opts: dict = {
        "title": None,
        "author": None,
        "include_images": True,
        "pages_per_chapter": 1,
    }
    if options:
        opts.update(options)

    _emit(progress_callback, 0, "Validating…")
    if not _preflight(pdf_path, ".pdf", output_epub_path):
        return False

    work_dir = tempfile.mkdtemp(prefix="conv_pdf2epub_")
    tmp_out = output_epub_path + ".part"
    try:
        ok = _pdf_to_epub_streaming(
            pdf_path, tmp_out, opts, work_dir, progress_callback, cancel_callback
        )
        if not ok:
            return False
        _atomic_replace(tmp_out, output_epub_path)
        _emit(progress_callback, 100, "Done")
        logger.info("EPUB written: %s", output_epub_path)
        return True
    except _Cancelled:
        logger.info("pdf_to_epub cancelled by user")
        _emit(progress_callback, 0, "Cancelled")
        return False
    except Exception as exc:
        logger.error("pdf_to_epub failed: %s", exc, exc_info=True)
        return False
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        if os.path.exists(tmp_out):
            try:
                os.remove(tmp_out)
            except OSError:
                pass


def _pdf_to_epub_streaming(
    pdf_path: str,
    tmp_out: str,
    opts: dict,
    work_dir: str,
    progress_callback: ProgressCallback | None,
    cancel_callback: CancelCallback | None,
) -> bool:
    """Stream the PDF page-by-page into EPUB chapters.

    PyMuPDF opens the PDF lazily, so iterating pages keeps memory bounded. Text
    is accumulated per chapter only; images are extracted at full resolution one
    at a time and deduped by xref (a logo repeated on every page is embedded
    once), so only unique images are ever held — never the whole document.
    """
    import fitz  # PyMuPDF
    from ebooklib import epub

    _emit(progress_callback, 3, "Opening PDF…")
    doc = fitz.open(pdf_path)
    try:
        page_count = doc.page_count
        if page_count <= 0:
            logger.error("PDF has no pages: %s", pdf_path)
            return False

        metadata = doc.metadata or {}
        title = opts.get("title") or metadata.get("title") or Path(pdf_path).stem
        author = opts.get("author") or metadata.get("author") or "Unknown"
        include_images = bool(opts.get("include_images", True))
        per_chapter = max(1, int(opts.get("pages_per_chapter", 1)))

        book = epub.EpubBook()
        book.set_identifier(f"conv_{abs(hash(title + author))}")
        book.set_title(title)
        book.set_language("en")
        book.add_author(author)

        toc_links: list = []
        spine: list = ["nav"]
        seen_xrefs: set[int] = set()           # dedup images across the document
        embedded_images: dict[int, str] = {}   # xref -> epub image file name
        chapter_idx = 0

        for start in range(0, page_count, per_chapter):
            _check_cancel(cancel_callback)
            chapter_idx += 1
            end = min(start + per_chapter, page_count)

            text_parts: list[str] = []
            img_refs: list[str] = []

            for pno in range(start, end):
                page = doc.load_page(pno)
                text_parts.append(page.get_text())

                if include_images:
                    for info in page.get_images(full=True):
                        xref = info[0]
                        if xref in seen_xrefs:
                            # Already embedded earlier — just reference it again.
                            if xref in embedded_images:
                                img_refs.append(embedded_images[xref])
                            continue
                        seen_xrefs.add(xref)
                        fname = _extract_pdf_image(doc, xref, book)
                        if fname:
                            embedded_images[xref] = fname
                            img_refs.append(fname)

            chapter_text = "\n".join(text_parts).strip()
            ch_title = _chapter_title(chapter_text, chapter_idx)

            html = _build_chapter_html(ch_title, chapter_text, img_refs)
            file_name = f"ch_{chapter_idx:04d}.xhtml"
            chapter = epub.EpubHtml(title=ch_title, file_name=file_name, lang="en")
            chapter.content = html.encode("utf-8")
            book.add_item(chapter)
            toc_links.append(epub.Link(file_name, ch_title, f"ch{chapter_idx}"))
            spine.append(chapter)

            pct = 5 + int(85 * end / page_count)
            _emit(progress_callback, pct, f"Converting page {end} of {page_count}…")

        if chapter_idx == 0:
            placeholder = epub.EpubHtml(title="Document", file_name="ch_0001.xhtml", lang="en")
            placeholder.content = _build_chapter_html(
                "Document", "(No readable content found in this PDF.)", []
            ).encode("utf-8")
            book.add_item(placeholder)
            toc_links.append(epub.Link("ch_0001.xhtml", "Document", "ch1"))
            spine.append(placeholder)

        book.toc = tuple(toc_links)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = spine

        _emit(progress_callback, 92, "Writing EPUB…")
        epub.write_epub(tmp_out, book)
        return True
    finally:
        doc.close()


def _extract_pdf_image(doc, xref: int, book) -> str | None:
    """Extract one image at full resolution and add it to the EPUB.

    Returns the EPUB-internal file name to reference, or None on failure.
    Images are deduped by ``xref`` so a logo repeated on every page is embedded
    once; the pixmap/bytes for each unique image are released as soon as the
    EPUB item is created.
    """
    import fitz
    from ebooklib import epub

    try:
        extracted = doc.extract_image(xref)  # keeps original encoding/quality
        img_bytes = extracted["image"]
        ext = (extracted.get("ext") or "png").lower()
    except Exception:
        # Fallback: render via pixmap (e.g. for image masks / odd encodings).
        try:
            pix = fitz.Pixmap(doc, xref)
            if pix.n > 4:  # CMYK / alpha → RGB
                pix = fitz.Pixmap(fitz.csRGB, pix)
            img_bytes = pix.tobytes("png")
            ext = "png"
            pix = None
        except Exception:
            logger.warning("Could not extract image xref %s", xref)
            return None

    if ext in {"jpx", "jp2"}:  # not broadly supported by readers → normalise
        ext = "png"
    media = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
             "gif": "image/gif", "bmp": "image/bmp", "tiff": "image/tiff"}.get(ext, "image/png")

    file_name = f"images/img_{xref}.{ext}"
    item = epub.EpubItem(
        uid=f"img_{xref}", file_name=file_name, media_type=media, content=img_bytes
    )
    book.add_item(item)
    return file_name


def _chapter_title(chapter_text: str, idx: int) -> str:
    for line in chapter_text.splitlines():
        line = line.strip()
        if line:
            return line[:80]
    return f"Page {idx}"


def _build_chapter_html(title: str, text: str, image_refs: list[str]) -> str:
    body = _text_to_html_paragraphs(text)
    imgs = "".join(
        f'<p><img src="{_html_escape(ref)}" alt="figure"/></p>' for ref in image_refs
    )
    return (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<html xmlns='http://www.w3.org/1999/xhtml'><head>"
        f"<title>{_html_escape(title)}</title></head>"
        f"<body><h1>{_html_escape(title)}</h1>{body}{imgs}</body></html>"
    )


def _text_to_html_paragraphs(text: str) -> str:
    """Convert plain text to HTML paragraph markup."""
    parts: list[str] = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("•"):
            items = [ln.lstrip("• ").strip() for ln in block.splitlines() if ln.strip()]
            parts.append("<ul>" + "".join(f"<li>{_html_escape(it)}</li>" for it in items) + "</ul>")
        else:
            parts.append(f"<p>{_html_escape(block)}</p>")
    return "\n".join(parts)
