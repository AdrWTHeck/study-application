"""Headless UI tests for the achievements tile grid."""
from ui.views.achievements_view import (
    AchievementsView,
    AchievementDetailDialog,
    AchievementTile,
)


def test_grid_shows_a_tile_per_definition(qapp, db, app_context):
    from domain.achievements.definitions import DEFINITIONS

    view = AchievementsView(app_context)
    tiles = view._grid_host.findChildren(AchievementTile)
    assert len(tiles) == len(DEFINITIONS)


def test_hidden_locked_tile_masks_title(qapp, db, app_context):
    view = AchievementsView(app_context)
    tiles = view._grid_host.findChildren(AchievementTile)
    hidden = [t for t in tiles if t._state.is_hidden_locked]
    assert hidden, "expected at least one hidden, locked achievement"
    # Its accessible name must not leak the real title.
    assert "Hidden" in hidden[0].accessibleName()


def test_unlocked_tile_gets_border(qapp, db, app_context, sample_deck):
    # Unlock 'first-deck' by having a deck, then evaluating via refresh().
    view = AchievementsView(app_context)
    view.refresh()
    tiles = {t._state.code: t for t in view._grid_host.findChildren(AchievementTile)}
    first_deck = tiles["first-deck"]
    assert first_deck._state.is_unlocked is True
    # Earned tiles carry an inline border style (gold by default).
    assert "border" in first_deck.styleSheet()


def test_detail_dialog_builds_for_state(qapp, db, app_context):
    view = AchievementsView(app_context)
    state = view._grid_host.findChildren(AchievementTile)[0]._state
    dlg = AchievementDetailDialog(state)
    assert dlg is not None
