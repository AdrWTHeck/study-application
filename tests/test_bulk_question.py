"""Tests for the bulk question-generation parser + duplicate detection."""
from data.models.testing import MCQ, SHORT_ANSWER, TRUE_FALSE
from domain.testing.bulk_question_service import (
    MCQ_MODE,
    SHORT,
    TF,
    mark_duplicates,
    parse,
)


def test_parse_short_answer_with_alternatives():
    drafts = parse("Capital of France? | Paris / paris\nLargest planet? | Jupiter", SHORT)
    assert [d.qtype for d in drafts] == [SHORT_ANSWER, SHORT_ANSWER]
    assert drafts[0].accepted == ["Paris", "paris"]
    assert drafts[1].prompt == "Largest planet?"
    assert drafts[1].accepted == ["Jupiter"]


def test_parse_mcq_marks_correct_option():
    drafts = parse("2+2? | *4 | 5 | 6", MCQ_MODE)
    assert len(drafts) == 1
    d = drafts[0]
    assert d.qtype == MCQ
    assert d.options == [("4", True), ("5", False), ("6", False)]


def test_parse_mcq_defaults_first_when_none_marked():
    d = parse("Sky colour? | Blue | Green", MCQ_MODE)[0]
    assert d.options[0] == ("Blue", True)
    assert d.options[1] == ("Green", False)


def test_parse_true_false_values():
    drafts = parse("Water is wet. | true\nFire is cold. | false\nSun is hot.", TF)
    assert [d.qtype for d in drafts] == [TRUE_FALSE] * 3
    assert drafts[0].answer is True
    assert drafts[1].answer is False
    assert drafts[2].answer is True   # missing value defaults to true


def test_parse_empty_returns_nothing():
    assert parse("", SHORT) == []
    assert parse("  \n  ", MCQ_MODE) == []


def test_mark_duplicates_against_existing_deck(db, sample_test_deck):
    # sample_test_deck already has "Which organelle is the powerhouse of the cell?"
    drafts = parse(
        "Which organelle is the powerhouse of the cell? | Mitochondria\n"
        "Totally new question? | yes",
        SHORT,
    )
    with db.session() as s:
        mark_duplicates(s, sample_test_deck, drafts)
    assert drafts[0].duplicate is True
    assert drafts[1].duplicate is False


def test_summary_describes_answer():
    short = parse("Q | a / b", SHORT)[0]
    assert short.summary() == "a, b"
    mcq = parse("Q | *Right | Wrong", MCQ_MODE)[0]
    assert "Right" in mcq.summary()
    tf = parse("Q | false", TF)[0]
    assert tf.summary() == "False"
