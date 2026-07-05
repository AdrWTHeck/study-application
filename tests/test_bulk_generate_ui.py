"""Headless UI tests for the bulk-add dialog."""
from sqlalchemy import func, select

from data.models import Card, Note
from ui.views.bulk_generate_dialog import BulkGenerateDialog


def test_preview_then_create_basic_cards(qapp, db, app_context, sample_deck):
    dlg = BulkGenerateDialog(app_context)
    # Target the existing sample deck (index of "Biology").
    names = [name for _, name in dlg._decks]
    dlg.deck_combo.setCurrentIndex(names.index("Biology"))
    dlg.mode_combo.setCurrentIndex(0)  # pairs
    dlg.text.setPlainText("Brand New Term | its definition\nAnother Term | another def")

    dlg._preview()
    assert dlg._stack.currentIndex() == 1
    assert len(dlg._rows) == 2

    dlg._create()
    assert dlg.created_count == 2
    with db.session() as s:
        # The two new notes were added to the Biology deck (5 seeded + 2 = 7).
        count = s.scalar(
            select(func.count()).select_from(Note).where(Note.deck_id == sample_deck)
        )
    assert count == 7


def test_duplicate_is_unticked_and_skipped(qapp, db, app_context, sample_deck):
    dlg = BulkGenerateDialog(app_context)
    names = [name for _, name in dlg._decks]
    dlg.deck_combo.setCurrentIndex(names.index("Biology"))
    dlg.mode_combo.setCurrentIndex(0)
    # First line duplicates an existing sample_deck front.
    dlg.text.setPlainText(
        "What is the powerhouse of the cell? | Mitochondria\nUnique new card | def"
    )
    dlg._preview()

    # Duplicate row starts unticked; only the unique card is created.
    states = [(check.isChecked(), draft.duplicate) for check, draft in dlg._rows]
    assert states[0] == (False, True)
    assert states[1] == (True, False)

    dlg._create()
    assert dlg.created_count == 1


def test_cloze_mode_creates_cloze_notes(qapp, db, app_context, sample_deck):
    dlg = BulkGenerateDialog(app_context)
    names = [name for _, name in dlg._decks]
    dlg.deck_combo.setCurrentIndex(names.index("Biology"))
    dlg.mode_combo.setCurrentIndex(2)  # cloze
    dlg.text.setPlainText("The {{c1::nucleus}} stores DNA.\nNo markup line.")
    dlg._preview()
    # Only the line with cloze markup is parsed.
    assert len(dlg._rows) == 1
    dlg._create()
    assert dlg.created_count == 1
    with db.session() as s:
        assert s.scalar(select(func.count()).select_from(Card)) >= 1
