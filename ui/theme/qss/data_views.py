"""List/item views, tab bars, and scrollbars."""
from __future__ import annotations

from ui.theme.tokens import Tokens
from ui.theme.qss.primitives import join_rules, rule


def rules(tokens: Tokens) -> str:
    p = tokens.palette
    t = tokens.typography
    d = tokens.density
    body_pt = f"{t.size('body')}pt"

    return join_rules([
        # Abstract item views (QListWidget, QListView, QTreeView, etc.)
        rule("QAbstractItemView", {
            "background-color": p.bg_raised,
            "color": p.text_primary,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius_sm}px",
            "selection-background-color": p.accent_muted,
            "selection-color": p.text_primary,
            "outline": "none",
            "font-size": body_pt,
        }),
        rule("QAbstractItemView::item", {
            "color": p.text_primary,
            "background": "transparent",
            "padding": f"{d.space(0.5)}px {d.space(1)}px",
            "min-height": f"{d.space(4)}px",
        }),
        rule("QAbstractItemView::item:hover", {
            "background-color": p.bg_hover,
        }),
        rule("QAbstractItemView::item:selected", {
            "background-color": p.accent_muted,
            "color": p.text_primary,
        }),
        rule("QAbstractItemView::item:selected:active", {
            "background-color": p.accent_muted,
            "color": p.text_primary,
        }),
        rule("QAbstractItemView::item:selected:!active", {
            "background-color": p.bg_hover,
            "color": p.text_primary,
        }),

        # Deck/folder tree — rows are painted by _DeckRowDelegate, so the view and
        # item backgrounds stay transparent and the delegate draws the rounded
        # selection/hover band plus the count badges.
        rule("QTreeWidget#DeckTree", {
            "background": "transparent",
            "border": "none",
        }),
        rule("QTreeWidget#DeckTree::item", {
            "background": "transparent",
            "border": "none",
            "padding": "0px",
        }),
        rule("QTreeWidget#DeckTree::item:selected, QTreeWidget#DeckTree::item:hover", {
            "background": "transparent",
        }),

        # Tab widget (Library, Reader)
        rule("QTabWidget::pane", {
            "background-color": p.bg_surface,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius_sm}px",
        }),
        rule("QTabBar", {
            "background": "transparent",
        }),
        rule("QTabBar::tab", {
            "background-color": p.bg_raised,
            "color": p.text_secondary,
            "border": f"1px solid {p.border}",
            "border-bottom": "none",
            "border-top-left-radius": f"{d.radius_sm}px",
            "border-top-right-radius": f"{d.radius_sm}px",
            "padding": f"{d.space(0.75)}px {d.space(2)}px",
            "margin-right": f"{d.space(0.5)}px",
            "min-height": f"{d.min_target}px",
            "font-size": body_pt,
        }),
        rule("QTabBar::tab:selected", {
            "background-color": p.bg_surface,
            "color": p.text_primary,
            "font-weight": "600",
            "border-bottom": f"2px solid {p.accent}",
        }),
        rule("QTabBar::tab:hover:!selected", {
            "background-color": p.bg_hover,
            "color": p.text_primary,
        }),
        rule("QTabBar::tab:focus", {
            "border": f"{d.focus_width}px solid {p.focus}",
        }),

        # ── Reader toolbar ────────────────────────────────────────────────
        rule("QWidget#ReaderTopBar", {
            "background-color": p.bg_surface,
            "border-bottom": f"1px solid {p.border}",
        }),
        # Icon-style buttons for the reader toolbar. Hit targets meet the global
        # accessibility minimum (KBD-02 / WCAG 2.5.5) so the page-nav arrows,
        # zoom, and bookmark controls are reliably clickable and keyboard-reachable.
        rule("QPushButton#ReaderToolBtn", {
            "background": "transparent",
            "border": "none",
            "border-radius": f"{d.radius_sm}px",
            "color": p.text_primary,
            "font-size": body_pt,
            "padding": f"3px {d.space(1.5)}px",
            "min-height": f"{d.min_target}px",
            "min-width": f"{d.min_target}px",
        }),
        rule("QPushButton#ReaderToolBtn:hover", {
            "background-color": p.bg_hover,
        }),
        rule("QPushButton#ReaderToolBtn:focus", {
            "border": f"{d.focus_width}px solid {p.focus}",
        }),
        rule("QPushButton#ReaderToolBtn:pressed", {
            "background-color": p.accent_muted,
        }),
        # Thin vertical hairline between toolbar button groups.
        rule("QWidget#ReaderToolSep", {
            "background-color": p.border,
            "min-width": "1px",
            "max-width": "1px",
        }),
        rule("QLabel#ReaderTitle", {
            "color": p.text_primary,
            "font-size": f"{t.size('card_title')}pt",
            "font-weight": "600",
            "background": "transparent",
        }),
        rule("QLabel#ReaderPageLabel", {
            "color": p.text_secondary,
            "font-size": f"{t.size('caption')}pt",
            "min-width": "72px",
            "background": "transparent",
        }),
        # Left outline sidebar.
        rule("QWidget#ReaderSidePanel", {
            "background-color": p.bg_surface,
            "border-right": f"1px solid {p.border}",
        }),
        # Centre page pane — dark background so the white page pops.
        rule("QWidget#ReaderPagePane", {
            "background-color": p.bg_base,
        }),
        # Right tools panel — inherits tab widget pane styling;
        # add a left border to visually separate it from the page.
        rule("QTabWidget#ReaderTools::pane", {
            "border": "none",
            "border-left": f"1px solid {p.border}",
            "background-color": p.bg_surface,
        }),

        # Vertical scrollbar
        rule("QScrollBar:vertical", {
            "background": "transparent",
            "width": "10px",
            "margin": "0px",
        }),
        rule("QScrollBar::handle:vertical", {
            "background": p.bg_hover,
            "border-radius": "5px",
            "min-height": "30px",
        }),
        rule("QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical", {
            "height": "0px",
        }),

        # Horizontal scrollbar
        rule("QScrollBar:horizontal", {
            "background": "transparent",
            "height": "10px",
            "margin": "0px",
        }),
        rule("QScrollBar::handle:horizontal", {
            "background": p.bg_hover,
            "border-radius": "5px",
            "min-width": "30px",
        }),
        rule("QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal", {
            "width": "0px",
        }),
    ])
