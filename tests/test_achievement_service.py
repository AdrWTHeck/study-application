from sqlalchemy import select

from data.models import Deck, NoteType, ReviewLog
from domain.achievements.achievement_service import AchievementService
from domain.notes.note_service import NoteService
from domain.srs import make_engine


def test_achievement_service_evaluates_unlocks(db):
    with db.session() as session:
        service = AchievementService(session)
        states = {a.code: a for a in service.list_achievements()}
        assert states["first-review"].unlocked_at is None
        assert states["first-deck"].unlocked_at is None
        # Locked, non-hidden achievements expose a progress string.
        assert states["first-review"].progress == "0/1"

        default_deck = session.scalar(select(Deck).where(Deck.is_default.is_(True)))
        note_type = session.scalar(select(NoteType).limit(1))
        assert note_type is not None

        note_service = NoteService(session, make_engine())
        note = note_service.create_note(
            default_deck.id, note_type.id, {"Front": "One", "Back": "Two"},
        )
        review = ReviewLog(
            card_id=note.cards[0].id, rating=4, prev_state="new", new_state="learning",
            prev_interval=0.0, new_interval=1.0, prev_ease=2.5, new_ease=2.5, elapsed_ms=12000,
        )
        session.add(review)
        session.flush()

        newly = service.evaluate()
        assert "first-review" in newly and "first-deck" in newly

        unlocked = {a.code: a for a in service.list_achievements()}
        assert unlocked["first-review"].unlocked_at is not None
        assert unlocked["first-deck"].unlocked_at is not None
        assert unlocked["steady-sprout"].unlocked_at is None  # needs a 3-day streak


def test_hidden_achievements_are_marked(db):
    with db.session() as session:
        states = {a.code: a for a in AchievementService(session).list_achievements()}
        # A legendary hidden achievement starts hidden+locked (mystery box).
        marathon = states["marathon-gardener"]
        assert marathon.hidden is True
        assert marathon.is_hidden_locked is True
        # A normal achievement is not hidden.
        assert states["first-review"].is_hidden_locked is False
