"""Card CRUD and session helpers — Phase 4."""
from __future__ import annotations


class CardService:
    def create(self, front: str, back: str, deck_id: int): raise NotImplementedError
    def edit(self, card_id: int, **fields): raise NotImplementedError
    def delete(self, card_id: int) -> None: raise NotImplementedError
    def move(self, card_id: int, target_deck_id: int): raise NotImplementedError
    def promote_to_question(self, card_id: int) -> dict: raise NotImplementedError
    def get_due_review(self, deck_id: int) -> list: raise NotImplementedError
    def get_due_learning(self, deck_id: int) -> list: raise NotImplementedError
    def get_new(self, deck_id: int, limit: int) -> list: raise NotImplementedError
