"""Tests for the customizable dashboard widget framework (§6.7)."""
from app.navigation import Destination
from ui.views.dashboard.registry import (
    DEFAULT_BOARD_ACCESSIBILITY,
    DEFAULT_BOARD_ADVANCED,
    WIDGETS,
    resolve_board,
)
from ui.views.dashboard.widgets import CardStatesWidget, HeroWidget, StickyNoteWidget
from ui.views.dashboard_view import DashboardView


def test_resolve_board_uses_mode_default(app_context):
    app_context.settings.set("mode", "accessibility")
    app_context.settings.set("dashboard_widgets", None)
    assert resolve_board(app_context.settings) == DEFAULT_BOARD_ACCESSIBILITY

    app_context.settings.set("mode", "advanced")
    assert resolve_board(app_context.settings) == DEFAULT_BOARD_ADVANCED


def test_resolve_board_respects_saved_list_and_drops_unknown(app_context):
    app_context.settings.set("dashboard_widgets", ["study", "bogus", "streak"])
    assert resolve_board(app_context.settings) == ["study", "streak"]


def test_dashboard_builds_all_board_widgets(qapp, db, app_context, sample_deck, sample_test_deck):
    app_context.settings.set("mode", "advanced")
    app_context.settings.set("dashboard_widgets", None)
    view = DashboardView(app_context)
    view.show()
    # Every advanced-board key (companion excluded if disabled) has a live widget.
    expected = [k for k in DEFAULT_BOARD_ADVANCED
                if k != "companion" or app_context.settings.get("companion_enabled")]
    assert set(view._widgets.keys()) == set(expected)


def test_companion_widget_hidden_when_disabled(qapp, db, app_context, sample_deck):
    app_context.settings.set("mode", "advanced")
    app_context.settings.set("companion_enabled", False)
    app_context.settings.set("dashboard_widgets", None)
    view = DashboardView(app_context)
    view.show()
    assert "companion" not in view._widgets


def test_card_states_widget_summarizes_distribution(qapp, db, app_context, sample_deck):
    w = CardStatesWidget(app_context)
    w.refresh()
    # sample_deck created 5 new cards → summary mentions them as a text alternative.
    assert "5 new" in w._summary.text()
    assert "cards total" in w._summary.text()


def test_sticky_note_persists_text(qapp, db, app_context):
    w = StickyNoteWidget(app_context)
    w._editor.setPlainText("Remember mitochondria")
    w._save()  # bypass the debounce timer
    assert app_context.settings.get("dashboard_sticky_note") == "Remember mitochondria"


def test_hero_widget_registered_and_on_both_default_boards():
    assert "hero" in WIDGETS
    assert DEFAULT_BOARD_ACCESSIBILITY[0] == "hero"
    assert DEFAULT_BOARD_ADVANCED[0] == "hero"


def test_hero_widget_shows_counts(qapp, db, app_context, sample_deck):
    w = HeroWidget(app_context)
    w.refresh()
    # sample_deck creates 5 new cards.
    assert w._new_value.text() == "5"
    assert "5 new cards" in w._new_value.accessibleName()
    assert w._due_value.text().isdigit()


def test_hero_start_studying_navigates_to_cards(qapp, db, app_context, sample_deck):
    from PyQt6.QtWidgets import QPushButton

    seen = []
    w = HeroWidget(app_context, navigate=seen.append)
    buttons = {b.text(): b for b in w.findChildren(QPushButton)}
    buttons["Start studying"].click()
    assert seen == [Destination.CARDS]


def test_board_change_rebuilds_grid(qapp, db, app_context, sample_deck):
    app_context.settings.set("dashboard_widgets", ["study", "streak"])
    view = DashboardView(app_context)
    view.show()
    assert set(view._widgets) == {"study", "streak"}

    app_context.settings.set("dashboard_widgets", ["study"])
    view.refresh()
    assert set(view._widgets) == {"study"}
