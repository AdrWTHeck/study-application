"""Tests for CompanionService XP/level mechanics (§6.3)."""
import pytest

from data.models.companion import CompanionState, XP_PER_LEVEL
from domain.companion.companion_service import (
    CompanionService,
    XP_FOCUS_BLOCK,
    XP_DIAGNOSTIC_COMPLETE,
    XP_CONFIDENCE_IMPROVED,
    XP_RETURN_AFTER_GAP,
)


def _svc(db_session) -> tuple[CompanionService, CompanionState]:
    svc = CompanionService(db_session)
    companion = svc.get_or_create("tree")
    return svc, companion


def test_get_or_create_idempotent(db):
    with db.session() as session:
        svc = CompanionService(session)
        c1 = svc.get_or_create("tree")
        c2 = svc.get_or_create("tree")
        assert c1.id == c2.id


def test_award_xp_no_levelup(db):
    with db.session() as session:
        svc, companion = _svc(session)
        svc.award_xp(companion, 30)
        assert companion.xp == 30
        assert companion.level == 1


def test_award_xp_levelup(db):
    with db.session() as session:
        svc, companion = _svc(session)
        svc.award_xp(companion, XP_PER_LEVEL)
        assert companion.level == 2
        assert companion.xp == 0


def test_award_xp_multi_levelup(db):
    with db.session() as session:
        svc, companion = _svc(session)
        # Level 1 needs 100 XP, level 2 needs 200 XP — award 300 total.
        svc.award_xp(companion, 300)
        assert companion.level == 3


def test_record_focus_block(db):
    with db.session() as session:
        svc, companion = _svc(session)
        svc.record_focus_block(companion)
        assert companion.xp == XP_FOCUS_BLOCK


def test_record_diagnostic_with_improvement(db):
    with db.session() as session:
        svc, companion = _svc(session)
        svc.record_diagnostic_complete(companion, improved=True)
        assert companion.xp == XP_DIAGNOSTIC_COMPLETE + XP_CONFIDENCE_IMPROVED


def test_growth_state_progression(db):
    with db.session() as session:
        svc, companion = _svc(session)
        assert companion.growth_state == "seed"
        companion.level = 3
        assert companion.growth_state == "sprout"
        companion.level = 6
        assert companion.growth_state == "sapling"
        companion.level = 11
        assert companion.growth_state == "grown"
        companion.level = 21
        assert companion.growth_state == "flourishing"


def test_pet_growth_state(db):
    with db.session() as session:
        svc = CompanionService(session)
        companion = svc.get_or_create("pet")
        assert companion.growth_state == "egg"
        companion.level = 3
        assert companion.growth_state == "hatchling"
