"""Tests for the bulk card-generation parser + duplicate detection."""
from domain.cards.bulk_generation_service import (
    CLOZE,
    PAIRS,
    QA,
    mark_duplicates,
    parse,
)


def test_parse_pairs_pipe_tab_comma():
    text = "Mitochondria | powerhouse\nDNA\tgenetic code\nOsmosis, water movement"
    drafts = parse(text, PAIRS)
    assert [(d.front, d.back) for d in drafts] == [
        ("Mitochondria", "powerhouse"),
        ("DNA", "genetic code"),
        ("Osmosis", "water movement"),
    ]
    assert all(d.kind == "basic" for d in drafts)


def test_parse_pairs_front_only_when_no_delimiter():
    drafts = parse("Just a front", PAIRS)
    assert drafts[0].front == "Just a front" and drafts[0].back == ""


def test_parse_qa_blocks():
    text = "Q: What is osmosis?\nA: Movement of water\n\nQ: Capital of France?\nA: Paris"
    drafts = parse(text, QA)
    assert [(d.front, d.back) for d in drafts] == [
        ("What is osmosis?", "Movement of water"),
        ("Capital of France?", "Paris"),
    ]


def test_parse_cloze_only_lines_with_markup():
    text = "The {{c1::mitochondria}} is the powerhouse.\nNo cloze here.\n{{c1::Paris}} is the capital."
    drafts = parse(text, CLOZE)
    assert len(drafts) == 2
    assert all(d.kind == "cloze" for d in drafts)
    assert drafts[0].front.startswith("The {{c1::mitochondria}}")


def test_parse_empty_returns_nothing():
    assert parse("", PAIRS) == []
    assert parse("   \n  \n", QA) == []


def test_mark_duplicates_against_existing_deck(db, sample_deck):
    # sample_deck already contains a "What is the powerhouse of the cell?" front.
    drafts = parse(
        "What is the powerhouse of the cell? | Mitochondria\nBrand new card | yes",
        PAIRS,
    )
    with db.session() as s:
        mark_duplicates(s, sample_deck, drafts)
    assert drafts[0].duplicate is True
    assert drafts[1].duplicate is False


def test_mark_duplicates_within_batch(db, sample_deck):
    drafts = parse("Photosynthesis | a\nphotosynthesis | b", PAIRS)
    with db.session() as s:
        mark_duplicates(s, sample_deck, drafts)
    # Second occurrence in the same batch is flagged (case-insensitive).
    assert drafts[1].duplicate is True
