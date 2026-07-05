"""Tests for companion daily-growth tracking (§6.3)."""
from domain.companion.companion_service import (
    CompanionService,
    XP_FOCUS_BLOCK,
    _today_str,
)


def test_growth_today_accumulates(db):
    with db.session() as session:
        svc = CompanionService(session)
        companion = svc.get_or_create("tree")
        assert svc.growth_today(companion) == 0
        svc.record_focus_block(companion)
        assert svc.growth_today(companion) == XP_FOCUS_BLOCK
        svc.record_focus_block(companion)
        assert svc.growth_today(companion) == XP_FOCUS_BLOCK * 2


def test_growth_resets_on_date_rollover(db):
    with db.session() as session:
        svc = CompanionService(session)
        companion = svc.get_or_create("tree")
        # Simulate yesterday's growth.
        companion.xp_today = 100
        companion.xp_today_date = "2000-01-01"
        # growth_today should report 0 because the stored date is stale.
        assert svc.growth_today(companion) == 0
        # Awarding XP today resets the daily counter first.
        svc.award_xp(companion, 30)
        assert companion.xp_today == 30
        assert companion.xp_today_date == _today_str()
        assert svc.growth_today(companion) == 30


def test_lifetime_xp_independent_of_daily(db):
    with db.session() as session:
        svc = CompanionService(session)
        companion = svc.get_or_create("tree")
        svc.award_xp(companion, 50)
        companion.xp_today_date = "2000-01-01"  # pretend a day passed
        svc.award_xp(companion, 40)
        # Daily counter reset to just today's 40...
        assert companion.xp_today == 40
        # ...but lifetime xp still reflects both awards (90, no level-up yet).
        assert companion.xp == 90
