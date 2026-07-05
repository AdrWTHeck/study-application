"""A tiny synchronous in-process event bus.

Lets views and services announce that something happened (a card was reviewed, a
quiz finished, the companion grew) without holding references to every other
view that might care. Subscribers register a callback per event type; publishing
calls them synchronously in registration order.

Deliberately minimal: no threads, no async, no priorities. One misbehaving
subscriber must not break the others or the publisher, so exceptions raised by a
callback are logged and swallowed.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

Callback = Callable[[Any], None]


class AppEvent(Enum):
    """Domain-level events broadcast across the app."""

    CARD_CREATED = "card_created"
    CARD_REVIEWED = "card_reviewed"
    DECK_IMPORTED = "deck_imported"
    SOURCE_IMPORTED = "source_imported"
    QUESTION_CREATED = "question_created"
    QUIZ_COMPLETED = "quiz_completed"
    STUDY_SESSION_COMPLETED = "study_session_completed"
    DIAGNOSTIC_COMPLETED = "diagnostic_completed"
    DEADLINE_CHANGED = "deadline_changed"
    COMPANION_UPDATED = "companion_updated"
    SETTINGS_CHANGED = "settings_changed"


class EventBus:
    """Synchronous publish/subscribe keyed by :class:`AppEvent`."""

    def __init__(self) -> None:
        self._subscribers: dict[AppEvent, list[Callback]] = {}

    def subscribe(self, event: AppEvent, callback: Callback) -> Callable[[], None]:
        """Register *callback* for *event*; returns a function that unsubscribes it."""
        self._subscribers.setdefault(event, []).append(callback)

        def _unsubscribe() -> None:
            handlers = self._subscribers.get(event)
            if handlers and callback in handlers:
                handlers.remove(callback)

        return _unsubscribe

    def publish(self, event: AppEvent, payload: Any = None) -> None:
        """Call every subscriber of *event* synchronously. Subscriber errors are
        logged and swallowed so one failure can't cascade."""
        for callback in list(self._subscribers.get(event, ())):
            try:
                callback(payload)
            except Exception:  # noqa: BLE001 — isolate subscriber failures
                logger.exception("Event subscriber for %s failed", event)

    def clear(self) -> None:
        """Drop all subscriptions (mainly for tests/teardown)."""
        self._subscribers.clear()
