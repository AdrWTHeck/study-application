from domain.sources import render_service
from domain.sources.extraction import extract_segments


def test_detects_heading_and_body(sample_pdf):
    segments = extract_segments(str(sample_pdf))
    assert any(s.kind == "heading" and "CHAPTER ONE" in s.text for s in segments)
    assert any(s.kind == "body" and "first body paragraph" in s.text for s in segments)


def test_drops_lone_page_number(sample_pdf):
    segments = extract_segments(str(sample_pdf))
    assert not any(s.text.strip() == "5" for s in segments)


def test_pages_are_one_based(sample_pdf):
    segments = extract_segments(str(sample_pdf))
    assert segments and all(s.page == 1 for s in segments)


def test_render_page_returns_png(sample_pdf):
    assert render_service.page_count(str(sample_pdf)) == 1
    rendered = render_service.render_page(str(sample_pdf), 0, zoom=1.0)
    assert rendered.png[:8] == b"\x89PNG\r\n\x1a\n"
    assert rendered.width > 0 and rendered.height > 0
