"""Deck CRUD + the per-deck New/Learning/Review counts the browser/dashboard show."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.clock import now
from data.models import Deck, Tag
from data.repositories.card_repository import CardRepository
from data.repositories.deck_repository import DeckRepository
from domain.decks.hierarchy import SEP, build_tree, display_name, is_child_of, split_path


@dataclass
class DeckSummary:
    deck: Deck
    new: int
    learning: int
    review: int

    @property
    def total(self) -> int:
        return self.new + self.learning + self.review


class DeckService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.decks = DeckRepository(session)
        self.cards = CardRepository(session)

    def create(self, name: str, deck_type: str = "card",
               category: str | None = None, color: str | None = None) -> Deck:
        deck = Deck(name=name.strip(), deck_type=deck_type, category=category, color=color)
        return self.decks.add(deck)

    def rename(self, deck_id: int, name: str) -> Deck | None:
        deck = self.decks.get(deck_id)
        if deck is not None:
            deck.name = name.strip()
            deck.modified_at = now()
            self.session.flush()
        return deck

    def set_favorite(self, deck_id: int, favorite: bool) -> Deck | None:
        deck = self.decks.get(deck_id)
        if deck is not None:
            deck.is_favorite = favorite
            self.session.flush()
        return deck

    def set_category(self, deck_id: int, category: str | None) -> Deck | None:
        deck = self.decks.get(deck_id)
        if deck is not None:
            deck.category = category
            self.session.flush()
        return deck

    def set_color(self, deck_id: int, color: str | None) -> Deck | None:
        deck = self.decks.get(deck_id)
        if deck is not None:
            deck.color = color
            self.session.flush()
        return deck

    def set_tags(self, deck_id: int, names: list[str]) -> Deck | None:
        deck = self.decks.get(deck_id)
        if deck is not None:
            deck.tags = [self._get_or_create_tag(name) for name in names]
            self.session.flush()
        return deck

    def delete(self, deck_id: int) -> None:
        deck = self.decks.get(deck_id)
        if deck is not None:
            self.decks.delete(deck)

    def _get_or_create_tag(self, name: str) -> Tag:
        tag = self.session.scalar(select(Tag).where(Tag.name == name))
        if tag is None:
            tag = Tag(name=name)
            self.session.add(tag)
            self.session.flush()
        return tag

    def list_summaries(self, deck_type: str = "card") -> list[DeckSummary]:
        summaries = []
        for deck in self.decks.by_type(deck_type):
            counts = self.cards.state_counts(deck.id)
            summaries.append(
                DeckSummary(deck=deck, new=counts["new"],
                            learning=counts["learning"], review=counts["review"])
            )
        return summaries

    # ── Hierarchy helpers ─────────────────────────────────────────────────────

    def subtree_ids(self, name: str, deck_type: str = "card") -> list[int]:
        """Return IDs of all decks whose name equals *name* or is nested under it.

        "Science" → IDs of Science, Science::Biology, Science::Biology::Genetics …
        """
        return [d.id for d in self.decks.by_name_prefix(name, deck_type)]

    def aggregated_counts(self, name: str, deck_type: str = "card") -> dict[str, int]:
        """Sum New/Learning/Review counts for *name* and all its descendants."""
        ids = self.subtree_ids(name, deck_type)
        return self.cards.state_counts_multi(ids)

    def list_summaries_tree(self, deck_type: str = "card") -> list[dict]:
        """Return summaries arranged as a tree using the build_tree helper.

        Each node in the returned tree has the standard build_tree shape:
            {
                "segment":  "Biology",
                "path":     "Science::Biology",
                "data":     DeckSummary | None,   # None for virtual parents
                "children": [...],
                "agg":      {"new": N, "learning": N, "review": N},
            }

        The "agg" dict is the aggregated count for the node and ALL descendants,
        so virtual parents get meaningful counts for display in the deck tree.
        """
        leaf_summaries = self.list_summaries(deck_type)
        # Build the raw tree from deck names as paths
        items = [{"path": s.deck.name, "summary": s} for s in leaf_summaries]
        roots = build_tree(items, path_key="path")

        # Annotate each node with aggregated counts (bottom-up)
        def _annotate(node: dict) -> None:
            for child in node["children"]:
                _annotate(child)
            item = node.get("data")
            if item is not None:
                # Real deck — own counts
                s: DeckSummary = item["summary"]
                own = {"new": s.new, "learning": s.learning, "review": s.review}
            else:
                own = {"new": 0, "learning": 0, "review": 0}
            # Add children's aggregated counts
            agg = dict(own)
            for child in node["children"]:
                for k in ("new", "learning", "review"):
                    agg[k] += child["agg"][k]
            node["agg"] = agg

        for root in roots:
            _annotate(root)

        return roots
