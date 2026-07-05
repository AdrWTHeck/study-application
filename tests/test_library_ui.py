from sqlalchemy import select

from app.context import AppContext
from core.settings import Settings
from data.models import SourceDocument
from domain.sources.annotation_service import AnnotationService
from domain.srs import make_engine
from domain.sources.source_service import SourceService
from ui.views.library_view import LibraryView
from ui.views.reader_view import ReaderView


def _ctx(db, tmp_path) -> AppContext:
    return AppContext(
        db=db, engine=make_engine(),
        settings=Settings.load(tmp_path / "s.json"), tts=None, dictionary=None,
    )


def _import(db, sample_pdf, tmp_path) -> int:
    with db.session() as s:
        return SourceService(s).import_pdf(
            str(sample_pdf), title="Doc",
            library_dir=str(tmp_path / "library"),
        ).id


def _annot_path(db, source_id: int) -> str:
    with db.session() as s:
        doc = s.get(SourceDocument, source_id)
        return doc.working_copy_path or doc.file_path


def test_library_lists_sources(qapp, db, tmp_path, sample_pdf):
    _import(db, sample_pdf, tmp_path)
    view = LibraryView(_ctx(db, tmp_path))
    assert view._list_layout.count() >= 1


def test_reader_opens_and_renders_page(qapp, db, tmp_path, sample_pdf):
    source_id = _import(db, sample_pdf, tmp_path)
    reader = ReaderView(_ctx(db, tmp_path))
    reader.open_source(source_id)
    # Verify page state is set correctly; QWebEngineView rendering is not
    # testable headlessly, so we only check Python-side state.
    assert reader._page == 1 and reader._page_count == 1
    reader._finish()


def test_reader_notes_autosave(qapp, db, tmp_path, sample_pdf):
    source_id = _import(db, sample_pdf, tmp_path)
    reader = ReaderView(_ctx(db, tmp_path))
    reader.open_source(source_id)
    reader._notes.setPlainText("hello notes")
    reader._save_notes()
    reader._finish()
    with db.session() as s:
        assert s.get(SourceDocument, source_id).notes_text == "hello notes"


def test_reader_highlight_from_selection(qapp, db, tmp_path, sample_pdf):
    source_id = _import(db, sample_pdf, tmp_path)
    reader = ReaderView(_ctx(db, tmp_path))
    reader.open_source(source_id)
    # _annotate_text calls AnnotationService directly — no JS required.
    reader._annotate_text("CHAPTER ONE", "highlight")
    reader._finish()
    annots = AnnotationService.get_all_annotations(_annot_path(db, source_id))
    assert len(annots) >= 1


def test_reader_highlight_creates_side_panel_entry(qapp, db, tmp_path, sample_pdf):
    source_id = _import(db, sample_pdf, tmp_path)
    reader = ReaderView(_ctx(db, tmp_path))
    reader.open_source(source_id)
    reader._annotate_text("CHAPTER ONE", "highlight")
    # Side panel should have at least one annotation item (row 0 = page separator).
    data_rows = [
        reader._side_highlights.item(r).data(0x0100)
        for r in range(reader._side_highlights.count())
        if reader._side_highlights.item(r).data(0x0100)
    ]
    assert len(data_rows) >= 1
    reader._finish()


def test_reader_erase_removes_annotation(qapp, db, tmp_path, sample_pdf):
    source_id = _import(db, sample_pdf, tmp_path)
    reader = ReaderView(_ctx(db, tmp_path))
    reader.open_source(source_id)
    reader._annotate_text("CHAPTER ONE", "highlight")
    assert AnnotationService.get_all_annotations(_annot_path(db, source_id))

    # Row 0 is the page separator, row 1 is the annotation item.
    reader._side_highlights.setCurrentRow(1)
    reader._delete_annotation_from_list()

    annots = AnnotationService.get_all_annotations(_annot_path(db, source_id))
    assert annots == []
    reader._finish()


def test_annotation_panel_color_background(qapp, db, tmp_path, sample_pdf):
    source_id = _import(db, sample_pdf, tmp_path)
    reader = ReaderView(_ctx(db, tmp_path))
    reader.open_source(source_id)
    reader._annotate_text("CHAPTER ONE", "highlight")
    item = None
    for row in range(reader._side_highlights.count()):
        it = reader._side_highlights.item(row)
        if it and it.data(0x0100):
            item = it
            break
    assert item is not None
    bg = item.background().color().name()
    assert bg == "#ffd43b"
    reader._finish()


def test_search_text_rects_normalized(sample_pdf):
    from domain.sources import render_service

    rects = render_service.search_text_rects(str(sample_pdf), 0, "CHAPTER")
    assert rects, "expected to find the heading text on the page"
    r = rects[0]
    assert all(0.0 <= r[k] <= 1.0 for k in ("x0", "y0", "x1", "y1"))
    assert r["page_width"] > 0 and r["page_height"] > 0
    assert render_service.search_text_rects(str(sample_pdf), 0, "zzz-not-here") == []


# ── Text capture reliability tests (whitespace normalization + fallbacks) ─────

def test_search_text_quads_exact(sample_pdf):
    """Baseline: single-word exact match returns quads."""
    from domain.sources import render_service

    quads = render_service.search_text_quads(str(sample_pdf), 0, "CHAPTER")
    assert quads, "should find single-word heading"


def test_search_text_quads_embedded_newline(sample_pdf):
    """Quads found even when query has a newline where the PDF has a space.

    This mirrors the bug: PDF.js text spans (white-space:pre) produce literal
    \\n between visual lines; PyMuPDF stores spaces.  Tier 1 normalization
    must collapse the newline before calling search_for().
    """
    from domain.sources import render_service

    quads = render_service.search_text_quads(str(sample_pdf), 0, "CHAPTER\nONE")
    assert quads, "should find quads even with embedded newline in query"


def test_search_text_quads_multi_word_phrase(sample_pdf):
    """Multi-word phrase found across a continuous text span."""
    from domain.sources import render_service

    quads = render_service.search_text_quads(str(sample_pdf), 0, "first body paragraph")
    assert quads, "should find multi-word phrase from body text"


def test_search_text_quads_extra_spaces(sample_pdf):
    """Extra whitespace in the query is collapsed before matching."""
    from domain.sources import render_service

    quads = render_service.search_text_quads(str(sample_pdf), 0, "CHAPTER  ONE")
    assert quads, "double-space query should still find the text"


def test_search_text_quads_not_found_returns_empty(sample_pdf):
    """Missing text returns [] without raising."""
    from domain.sources import render_service

    quads = render_service.search_text_quads(str(sample_pdf), 0, "zzz-not-in-pdf")
    assert quads == []


def test_annotate_text_shows_status_on_failure(qapp, db, tmp_path, sample_pdf):
    """_annotate_text() populates the status label when text is not found.

    isVisible() requires all ancestors to be shown, which doesn't hold in
    headless tests, so we check that the label text was set instead.
    """
    source_id = _import(db, sample_pdf, tmp_path)
    reader = ReaderView(_ctx(db, tmp_path))
    reader.open_source(source_id)
    reader._annotate_text("zzz-not-in-pdf", "highlight")
    assert "not found" in reader._annot_status.text().lower(), (
        "status label should describe the failure"
    )
    reader._finish()


def test_pdf_annotation_creates_service_record(qapp, db, tmp_path, sample_pdf):
    source_id = _import(db, sample_pdf, tmp_path)
    reader = ReaderView(_ctx(db, tmp_path))
    reader.open_source(source_id)
    reader._annotate_text("CHAPTER ONE", "highlight")
    annots = AnnotationService.get_all_annotations(_annot_path(db, source_id))
    assert annots
    assert annots[0].subject and "CHAPTER" in annots[0].subject
    reader._finish()


def test_pdf_annotation_clears_on_delete(qapp, db, tmp_path, sample_pdf):
    source_id = _import(db, sample_pdf, tmp_path)
    reader = ReaderView(_ctx(db, tmp_path))
    reader.open_source(source_id)
    reader._annotate_text("CHAPTER ONE", "highlight")
    assert AnnotationService.get_all_annotations(_annot_path(db, source_id))

    reader._side_highlights.setCurrentRow(1)
    reader._delete_annotation_from_list()
    assert AnnotationService.get_all_annotations(_annot_path(db, source_id)) == []
    reader._finish()


def test_reader_bookmark_with_label(qapp, db, tmp_path, sample_pdf):
    from data.models import Bookmark

    source_id = _import(db, sample_pdf, tmp_path)
    reader = ReaderView(_ctx(db, tmp_path))
    reader.open_source(source_id)
    reader._add_bookmark("Important diagram")
    reader._finish()
    with db.session() as s:
        bm = s.scalars(select(Bookmark)).first()
    assert bm is not None and bm.label == "Important diagram"


def test_reader_highlight_uses_selected_color(qapp, db, tmp_path, sample_pdf):
    source_id = _import(db, sample_pdf, tmp_path)
    reader = ReaderView(_ctx(db, tmp_path))
    reader.open_source(source_id)
    names = [reader._color_combo.itemText(i) for i in range(reader._color_combo.count())]
    reader._color_combo.setCurrentIndex(names.index("Green"))
    reader._annotate_text("CHAPTER ONE", "highlight")
    reader._finish()
    annots = AnnotationService.get_all_annotations(_annot_path(db, source_id))
    assert annots and annots[0].color_hex == "#b2f2bb"


def test_reader_position_saved_on_finish(qapp, db, tmp_path, sample_pdf):
    source_id = _import(db, sample_pdf, tmp_path)
    reader = ReaderView(_ctx(db, tmp_path))
    reader.open_source(source_id)
    reader._finish()
    with db.session() as s:
        assert s.get(SourceDocument, source_id).last_opened_at is not None


def _folder_tree_data(view) -> list:
    """Collect all UserRole data values from the library's folder tree."""
    from PyQt6.QtCore import Qt
    results = []
    def _collect(item):
        results.append(item.data(0, Qt.ItemDataRole.UserRole))
        for i in range(item.childCount()):
            _collect(item.child(i))
    for i in range(view._folder_tree.topLevelItemCount()):
        _collect(view._folder_tree.topLevelItem(i))
    return results


def test_library_category_filter(qapp, db, tmp_path, sample_pdf):
    """Folder tree shows category folders and filtering by one shows only its source."""
    with db.session() as s:
        svc = SourceService(s)
        a = svc.import_pdf(str(sample_pdf), title="A")
        svc.set_category(a.id, "Math")
        b = svc.import_pdf(str(sample_pdf), title="B")
        svc.set_category(b.id, "History")
    view = LibraryView(_ctx(db, tmp_path))
    folder_keys = _folder_tree_data(view)
    assert "Math" in folder_keys and "History" in folder_keys
    # Select Math folder → only source A should show
    view._select_folder_key("Math")
    view._render_rows()
    assert view._list_layout.count() == 1


def test_folder_sidebar_all_and_uncategorized(qapp, db, tmp_path, sample_pdf):
    """Sidebar has 'All Sources' entry and 'Uncategorized' when sources lack a category."""
    with db.session() as s:
        svc = SourceService(s)
        svc.import_pdf(str(sample_pdf), title="No folder")
    view = LibraryView(_ctx(db, tmp_path))
    folder_keys = _folder_tree_data(view)
    assert "__all__" in folder_keys
    assert "__uncategorized__" in folder_keys


def test_folder_filter_favorites(qapp, db, tmp_path, sample_pdf):
    """Selecting the Favorites folder shows only starred sources."""
    with db.session() as s:
        svc = SourceService(s)
        a = svc.import_pdf(str(sample_pdf), title="Starred")
        svc.set_favorite(a.id, True)
        svc.import_pdf(str(sample_pdf), title="Not starred")
    view = LibraryView(_ctx(db, tmp_path))
    view._select_folder_key("__favorites__")
    view._render_rows()
    assert view._list_layout.count() == 1


def test_move_to_folder_via_set(qapp, db, tmp_path, sample_pdf):
    """Moving a source to a folder (set_category) appears under that folder in tree."""
    with db.session() as s:
        svc = SourceService(s)
        doc = svc.import_pdf(str(sample_pdf), title="Doc")
        svc.set_category(doc.id, "Physics")
    view = LibraryView(_ctx(db, tmp_path))
    assert "Physics" in _folder_tree_data(view)
    view._select_folder_key("Physics")
    view._render_rows()
    assert view._list_layout.count() == 1


def test_rename_folder_updates_all_sources(qapp, db, tmp_path, sample_pdf):
    """Renaming a folder re-categorizes all its sources to the new name."""
    with db.session() as s:
        svc = SourceService(s)
        a = svc.import_pdf(str(sample_pdf), title="A")
        svc.set_category(a.id, "OldName")
        b = svc.import_pdf(str(sample_pdf), title="B")
        svc.set_category(b.id, "OldName")
    view = LibraryView(_ctx(db, tmp_path))
    with view._context.db.session() as s:
        svc = SourceService(s)
        for r in view._rows:
            if r.category == "OldName":
                svc.set_category(r.id, "NewName")
    view.refresh()
    folder_keys = _folder_tree_data(view)
    assert "NewName" in folder_keys
    assert "OldName" not in folder_keys


def test_nested_category_appears_in_tree(qapp, db, tmp_path, sample_pdf):
    """A source with category 'Science::Biology' shows both 'Science' and 'Science::Biology'."""
    with db.session() as s:
        svc = SourceService(s)
        doc = svc.import_pdf(str(sample_pdf), title="Bio")
        svc.set_category(doc.id, "Science::Biology")
    view = LibraryView(_ctx(db, tmp_path))
    folder_keys = _folder_tree_data(view)
    assert "Science::Biology" in folder_keys  # leaf
    assert "Science" in folder_keys            # virtual parent created automatically
    # Selecting the parent "Science" also shows the source (is_child_of match)
    view._select_folder_key("Science")
    view._render_rows()
    assert view._list_layout.count() == 1


def test_delete_folder_uncategorizes_sources(qapp, db, tmp_path, sample_pdf):
    """Deleting a folder moves its sources to Uncategorized."""
    with db.session() as s:
        svc = SourceService(s)
        doc = svc.import_pdf(str(sample_pdf), title="Doc")
        svc.set_category(doc.id, "ToDelete")
    view = LibraryView(_ctx(db, tmp_path))
    with view._context.db.session() as s:
        svc = SourceService(s)
        for r in view._rows:
            if r.category == "ToDelete":
                svc.set_category(r.id, "")
    view.refresh()
    folder_keys = _folder_tree_data(view)
    assert "ToDelete" not in folder_keys
    assert "__uncategorized__" in folder_keys


# ── merge_line_rects() unit tests ─────────────────────────────────────────────
# These test the pure Python merge function with no PDF or Qt required.

import pytest
from ui.views.reader_view import merge_line_rects


def test_merge_single_line_three_spans():
    """Three word-level rects on same line collapse into one wide rect."""
    rects = [
        {"x0": 0.10, "y0": 0.100, "x1": 0.20, "y1": 0.115},
        {"x0": 0.22, "y0": 0.101, "x1": 0.35, "y1": 0.115},
        {"x0": 0.37, "y0": 0.100, "x1": 0.50, "y1": 0.114},
    ]
    merged = merge_line_rects(rects)
    assert len(merged) == 1
    assert merged[0]["x0"] == pytest.approx(0.10)
    assert merged[0]["x1"] == pytest.approx(0.50)


def test_merge_two_lines_stays_two():
    """Rects on two distinct visual lines remain as two merged rects."""
    rects = [
        {"x0": 0.10, "y0": 0.10,  "x1": 0.30, "y1": 0.115},
        {"x0": 0.32, "y0": 0.10,  "x1": 0.50, "y1": 0.115},
        {"x0": 0.10, "y0": 0.20,  "x1": 0.40, "y1": 0.215},  # separate line
    ]
    merged = merge_line_rects(rects)
    assert len(merged) == 2


def test_merge_empty_input():
    assert merge_line_rects([]) == []


def test_merge_single_rect_unchanged():
    rects = [{"x0": 0.1, "y0": 0.1, "x1": 0.5, "y1": 0.12}]
    assert merge_line_rects(rects) == rects


def test_merge_covers_inter_span_gap():
    """Merged rect bridges the DOM-empty gap between two spans on the same line.

    Simulates: monospace 'char' span (x 0.05–0.15) + gap + description span
    (x 0.25–0.70).  After merge the gap 0.15–0.25 is covered by a single quad.
    """
    rects = [
        {"x0": 0.05, "y0": 0.100, "x1": 0.15, "y1": 0.115},
        {"x0": 0.25, "y0": 0.100, "x1": 0.70, "y1": 0.115},
    ]
    merged = merge_line_rects(rects)
    assert len(merged) == 1
    assert merged[0]["x0"] == pytest.approx(0.05)
    assert merged[0]["x1"] == pytest.approx(0.70)


def test_merge_four_lines():
    """Simulates selecting the char/int/float/double type table (4 lines)."""
    rects = []
    for i, y in enumerate([0.10, 0.14, 0.18, 0.22]):
        # keyword span + description span on each line
        rects.append({"x0": 0.05, "y0": y,        "x1": 0.12, "y1": y + 0.012})
        rects.append({"x0": 0.20, "y0": y + 0.001,"x1": 0.75, "y1": y + 0.013})
    merged = merge_line_rects(rects)
    assert len(merged) == 4
    for m in merged:
        assert m["x0"] == pytest.approx(0.05)
        assert m["x1"] == pytest.approx(0.75)


# ── Character type variety (search_text_quads with code_pdf) ──────────────────

def test_quads_char_keyword(code_pdf):
    from domain.sources import render_service
    assert render_service.search_text_quads(str(code_pdf), 0, "char")


def test_quads_int_keyword(code_pdf):
    from domain.sources import render_service
    assert render_service.search_text_quads(str(code_pdf), 0, "int")


def test_quads_float_keyword(code_pdf):
    from domain.sources import render_service
    assert render_service.search_text_quads(str(code_pdf), 0, "float")


def test_quads_double_keyword(code_pdf):
    from domain.sources import render_service
    assert render_service.search_text_quads(str(code_pdf), 0, "double")


def test_quads_escape_tab(code_pdf):
    """Escape character notation '\\t' is locatable in the PDF."""
    from domain.sources import render_service
    assert render_service.search_text_quads(str(code_pdf), 0, "'\\t'")


def test_quads_escape_newline(code_pdf):
    from domain.sources import render_service
    assert render_service.search_text_quads(str(code_pdf), 0, "'\\n'")


def test_quads_null_char(code_pdf):
    from domain.sources import render_service
    assert render_service.search_text_quads(str(code_pdf), 0, "'\\0'")


def test_quads_operator_eq(code_pdf):
    from domain.sources import render_service
    assert render_service.search_text_quads(str(code_pdf), 0, "==")


def test_quads_operator_neq(code_pdf):
    from domain.sources import render_service
    assert render_service.search_text_quads(str(code_pdf), 0, "!=")


# ── Font size variation — quad height reflects fontsize ───────────────────────

def test_quad_height_heading_larger_than_body(code_pdf):
    """18 pt heading quad is taller than 11 pt body text quad."""
    from domain.sources import render_service
    h = render_service.search_text_quads(str(code_pdf), 0, "Basic Types and Operators")
    b = render_service.search_text_quads(str(code_pdf), 0, "Normal body text")
    assert h and b
    assert h[0].rect.height > b[0].rect.height


def test_quad_height_body_larger_than_footnote(code_pdf):
    """11 pt body quad is taller than 8 pt footnote quad."""
    from domain.sources import render_service
    b = render_service.search_text_quads(str(code_pdf), 0, "Normal body text")
    f = render_service.search_text_quads(str(code_pdf), 0, "See also")
    assert b and f
    assert b[0].rect.height > f[0].rect.height


def test_quad_height_medium_heading_between(code_pdf):
    """14 pt section heading quad height is between 18 pt and 11 pt."""
    from domain.sources import render_service
    large  = render_service.search_text_quads(str(code_pdf), 0, "Basic Types and Operators")
    medium = render_service.search_text_quads(str(code_pdf), 0, "Integer Types")
    body   = render_service.search_text_quads(str(code_pdf), 0, "Normal body text")
    assert large and medium and body
    assert large[0].rect.height > medium[0].rect.height > body[0].rect.height


# ── Mixed-font annotation (monospace + proportional on same line) ─────────────

def test_annotate_mixed_font_description(qapp, db, tmp_path, code_pdf):
    """Annotating the description text beside a monospace keyword finds quads."""
    source_id = _import(db, code_pdf, tmp_path)
    reader = ReaderView(_ctx(db, tmp_path))
    reader.open_source(source_id)
    reader._annotate_text("ASCII character type, 8 bits.", "highlight")
    reader._finish()
    annots = AnnotationService.get_all_annotations(_annot_path(db, source_id))
    assert annots


def test_annotate_inline_monospace_keyword(qapp, db, tmp_path, code_pdf):
    """Annotating standalone monospace 'char' keyword produces a quad."""
    source_id = _import(db, code_pdf, tmp_path)
    reader = ReaderView(_ctx(db, tmp_path))
    reader.open_source(source_id)
    reader._annotate_text("char", "highlight")
    reader._finish()
    annots = AnnotationService.get_all_annotations(_annot_path(db, source_id))
    assert annots


def test_annotate_escape_chars(qapp, db, tmp_path, code_pdf):
    """Highlighting escape character notation does not raise."""
    source_id = _import(db, code_pdf, tmp_path)
    reader = ReaderView(_ctx(db, tmp_path))
    reader.open_source(source_id)
    reader._annotate_text("'\\t' tab, '\\n' newline", "highlight")
    reader._finish()
    annots = AnnotationService.get_all_annotations(_annot_path(db, source_id))
    assert annots


def test_annotate_operator_symbols(qapp, db, tmp_path, code_pdf):
    """Operator symbols can be highlighted."""
    source_id = _import(db, code_pdf, tmp_path)
    reader = ReaderView(_ctx(db, tmp_path))
    reader.open_source(source_id)
    reader._annotate_text("==", "highlight")
    reader._finish()
    annots = AnnotationService.get_all_annotations(_annot_path(db, source_id))
    assert annots


# ── Position-path: pre-merged rects produce expected quad count ───────────────

def test_rects_to_quads_one_wide_rect(qapp, db, tmp_path, code_pdf):
    """A single wide merged rect (as JS sends after merge) → one quad."""
    source_id = _import(db, code_pdf, tmp_path)
    reader = ReaderView(_ctx(db, tmp_path))
    reader.open_source(source_id)
    wide = [{"x0": 0.09, "y0": 0.14, "x1": 0.88, "y1": 0.16}]
    quads = reader._rects_to_quads(wide, 0)
    assert len(quads) == 1
    reader._finish()


def test_rects_to_quads_four_line_selection(qapp, db, tmp_path, code_pdf):
    """Four merged line rects (one per type-table row) → four quads."""
    source_id = _import(db, code_pdf, tmp_path)
    reader = ReaderView(_ctx(db, tmp_path))
    reader.open_source(source_id)
    # Approx normalised y positions for the four type-table rows in code_pdf
    line_rects = [
        {"x0": 0.09, "y0": y, "x1": 0.88, "y1": y + 0.018}
        for y in [0.148, 0.178, 0.208, 0.238]
    ]
    quads = reader._rects_to_quads(line_rects, 0)
    assert len(quads) == 4
    reader._finish()
