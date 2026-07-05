"""Tests for the in-process event bus."""
from app.events import AppEvent, EventBus


def test_publish_calls_subscriber_with_payload():
    bus = EventBus()
    seen = []
    bus.subscribe(AppEvent.CARD_REVIEWED, lambda p: seen.append(p))
    bus.publish(AppEvent.CARD_REVIEWED, 42)
    assert seen == [42]


def test_multiple_subscribers_all_called():
    bus = EventBus()
    calls = []
    bus.subscribe(AppEvent.QUIZ_COMPLETED, lambda _p: calls.append("a"))
    bus.subscribe(AppEvent.QUIZ_COMPLETED, lambda _p: calls.append("b"))
    bus.publish(AppEvent.QUIZ_COMPLETED)
    assert calls == ["a", "b"]


def test_unsubscribe_stops_delivery():
    bus = EventBus()
    seen = []
    off = bus.subscribe(AppEvent.COMPANION_UPDATED, lambda _p: seen.append(1))
    bus.publish(AppEvent.COMPANION_UPDATED)
    off()
    bus.publish(AppEvent.COMPANION_UPDATED)
    assert seen == [1]


def test_subscriber_exception_is_isolated():
    bus = EventBus()
    seen = []

    def boom(_p):
        raise RuntimeError("subscriber failure")

    bus.subscribe(AppEvent.CARD_REVIEWED, boom)
    bus.subscribe(AppEvent.CARD_REVIEWED, lambda _p: seen.append("ok"))
    # Must not raise, and the healthy subscriber still runs.
    bus.publish(AppEvent.CARD_REVIEWED)
    assert seen == ["ok"]


def test_publish_with_no_subscribers_is_safe():
    EventBus().publish(AppEvent.DEADLINE_CHANGED)  # no raise


def test_clear_removes_all_subscribers():
    bus = EventBus()
    seen = []
    bus.subscribe(AppEvent.CARD_CREATED, lambda _p: seen.append(1))
    bus.clear()
    bus.publish(AppEvent.CARD_CREATED)
    assert seen == []


def test_app_context_has_event_bus_by_default(db, app_context):
    # The fixture-built context must expose a usable bus.
    assert isinstance(app_context.events, EventBus)
    fired = []
    app_context.events.subscribe(AppEvent.CARD_REVIEWED, lambda _p: fired.append(1))
    app_context.events.publish(AppEvent.CARD_REVIEWED)
    assert fired == [1]
