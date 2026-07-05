"""Layout utility functions shared across views."""
from __future__ import annotations

from PyQt6.QtWidgets import QLayout

from ui.theme.tokens import Tokens, build_tokens


def clear_layout(layout: QLayout) -> None:
    """Recursively remove and schedule deletion of all items in a QLayout."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
            continue
        child = item.layout()
        if child is not None:
            clear_layout(child)


def _resolve_tokens(source: object) -> Tokens:
    """Resolve a Tokens from a Tokens, an AppContext-like, or None.

    Views may run with a theme-less AppContext (notably in tests), so fall back
    to default comfortable tokens instead of dereferencing a missing theme.
    """
    if isinstance(source, Tokens):
        return source
    theme = getattr(source, "theme", None)
    tokens = getattr(theme, "tokens", None)
    if isinstance(tokens, Tokens):
        return tokens
    return build_tokens()


def apply_page_margins(layout: QLayout, source: object) -> None:
    """Apply token-driven outer page padding (margins only) to a page root.

    ``source`` may be a Tokens or an AppContext (its active theme tokens are
    used). Centralises the page gutter so a density change tightens every page
    from one place; the spacing *between* a page's sections stays the view's
    own decision.
    """
    lay = _resolve_tokens(source).layout
    layout.setContentsMargins(
        lay.page_margin_x, lay.page_margin_y, lay.page_margin_x, lay.page_margin_y
    )


def apply_card_margins(layout: QLayout, source: object) -> None:
    """Apply token-driven inner padding (margins only) to a card/row layout."""
    d = _resolve_tokens(source).density
    layout.setContentsMargins(d.space(2), d.space(1.5), d.space(2), d.space(1.5))
