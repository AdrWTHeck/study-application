"""Card session controller — Phase 4."""
from __future__ import annotations


class CardSessionController:
    def start(self, deck_id: int): raise NotImplementedError
    def resume(self, session_id: int): raise NotImplementedError
    def get_next_card(self): raise NotImplementedError
    def submit_rating(self, session, card, rating, consecutive_good: int) -> None: raise NotImplementedError
    def discard(self, session_id: int) -> None: raise NotImplementedError
