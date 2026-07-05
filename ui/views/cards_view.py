"""The Cards page: a two-pane deck browser → guided review.

Left pane: the collapsible Anki-style deck tree (names with '::' separators
nest automatically; parent nodes aggregate subtree counts) plus search.
Right pane: the selected deck's detail — title, counts, study-action cards
(Review / Quick pass / Cram) and the embedded per-note browser.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QShowEvent
from PyQt6.QtWidgets import (
    QColorDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from domain.deadlines.deadline_service import DeadlineService
from domain.decks.deck_service import DeckService, DeckSummary
from ui.components.badges import StateBadges
from ui.components.folder_tree import FolderTreeWidget
from ui.utils.layouts import _resolve_tokens, apply_page_margins
from ui.views.note_form import AddNoteDialog
from ui.views.note_type_editor import NoteTypeEditor
from ui.views.notes_view import NotesView
from ui.views.review_view import ReviewView
from ui.views.cram_view import CramView
from ui.views.quick_pass_view import QuickPassView
from ui.views.companion.focus_session_view import FocusSessionView

_DECKS_PAGE = 0
_REVIEW_PAGE = 1
_CRAM_PAGE = 2
_FOCUS_PAGE = 3
_QUICK_PASS_PAGE = 4


class StudyActionCard(QPushButton):
    """Large study-action button (Review / Quick pass / Cram) with a title
    over a hint line; the whole card is one click target."""

    def __init__(self, title: str, hint: str, *, accent: bool = False,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StudyActionCard")
        if accent:
            self.setProperty("accent", "true")
        self.setAccessibleName(f"{title}: {hint}")
        column = QVBoxLayout(self)
        column.setContentsMargins(6, 4, 6, 4)
        column.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("StudyActionTitle")
        title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        hint_lbl = QLabel(hint)
        hint_lbl.setObjectName("StudyActionHint")
        hint_lbl.setWordWrap(True)
        hint_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        column.addWidget(title_lbl)
        column.addWidget(hint_lbl)

    # QPushButton's own sizeHint ignores child layouts, which clips the
    # wrapped hint line at narrow widths — defer to the layout instead.
    def sizeHint(self):  # type: ignore[override]
        layout = self.layout()
        return layout.sizeHint() if layout is not None else super().sizeHint()

    def minimumSizeHint(self):  # type: ignore[override]
        layout = self.layout()
        return layout.minimumSize() if layout is not None else super().minimumSizeHint()

    def hasHeightForWidth(self) -> bool:  # type: ignore[override]
        layout = self.layout()
        return layout.hasHeightForWidth() if layout is not None else False

    def heightForWidth(self, width: int) -> int:  # type: ignore[override]
        layout = self.layout()
        return layout.heightForWidth(width) if layout is not None else -1


def _walk_flat(nodes: list[dict]) -> list[dict]:
    result: list[dict] = []
    for node in nodes:
        result.append(node)
        result.extend(_walk_flat(node["children"]))
    return result


def _flatten_for_tree(
    roots: list[dict],
    query: str,
    deadline_per_deck: dict,
) -> list[dict]:
    """Convert list_summaries_tree output into items for FolderTreeWidget.populate().

    Virtual parent nodes get aggregated counts; leaf nodes get their own counts
    plus an optional deadline tooltip.  When *query* is non-empty, only nodes
    whose subtree contains a matching leaf (plus those ancestors) are included.
    """
    items: list[dict] = []

    def _subtree_has_match(node: dict) -> bool:
        s = node["data"]["summary"] if node["data"] is not None else None
        if s is not None:
            if query in s.deck.name.lower() or query in (s.deck.category or "").lower():
                return True
        return any(_subtree_has_match(c) for c in node["children"])

    def _walk(node: dict) -> None:
        if query and not _subtree_has_match(node):
            return
        agg = node["agg"]
        summary: DeckSummary | None = (
            node["data"]["summary"] if node["data"] is not None else None
        )
        item: dict = {"path": node["path"], "data": summary}
        if summary is not None:
            item["badges"] = [
                ("new", agg["new"]),
                ("learning", agg["learning"]),
                ("review", agg["review"]),
            ]
            item["fav"] = getattr(summary.deck, "is_favorite", False)
            dl = deadline_per_deck.get(summary.deck.id)
            if dl is not None and not dl.is_past and dl.daily_target is not None:
                n = dl.daily_target
                item["tip"] = f"{dl.name}: {n} card{'s' if n != 1 else ''}/day"
        items.append(item)
        for child in node["children"]:
            _walk(child)

    for root in roots:
        _walk(root)
    return items


class CardsView(QWidget):
    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setObjectName("Page")
        self.setAccessibleName("Cards")
        self._review_return = _DECKS_PAGE
        self._cram_return = _DECKS_PAGE
        self._sel_deck_ids: list[int] = []
        self._sel_summary: DeckSummary | None = None

        self._stack = QStackedWidget()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._stack)

        # Embedded in the browser's right pane (not a stack page of its own).
        self._notes = NotesView(context, embedded=True)
        self._notes.review_requested.connect(lambda did: self._start_review(did, _DECKS_PAGE))

        self._browser = self._build_browser()
        self._review = ReviewView(context)
        self._review.finished.connect(self._on_review_finished)
        self._cram = CramView(context)
        self._cram.finished.connect(self._on_cram_finished)
        self._focus = FocusSessionView(context)
        self._focus.finished.connect(self._on_focus_finished)
        self._quick_pass = QuickPassView(context)
        self._quick_pass.finished.connect(self._on_quick_pass_finished)

        self._stack.addWidget(self._browser)      # 0
        self._stack.addWidget(self._review)       # 1
        self._stack.addWidget(self._cram)         # 2
        self._stack.addWidget(self._focus)        # 3
        self._stack.addWidget(self._quick_pass)   # 4

        self.refresh()

    # -- deck browser -------------------------------------------------------

    def _build_browser(self) -> QWidget:
        tokens = _resolve_tokens(self._context)
        d = tokens.density

        page = QWidget()
        page.setObjectName("Page")
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # -- left pane: deck list ------------------------------------------
        left = QWidget()
        left.setObjectName("DeckListPane")
        left.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        left.setFixedWidth(tokens.layout.deck_pane_width)
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(d.space(2), d.space(2), d.space(2), d.space(2))
        left_l.setSpacing(d.space(1.5))

        list_header = QHBoxLayout()
        title = QLabel("Decks")
        title.setObjectName("DeckTitle")
        new_deck = QPushButton("New")
        new_deck.setObjectName("PrimaryButton")
        new_deck.setAccessibleName("New deck")
        new_deck.clicked.connect(self._new_deck)
        more = QPushButton("More…")
        more.setObjectName("GhostButton")
        more.setAccessibleName("More card actions")
        self._more_menu = QMenu(self)
        self._more_menu.addAction("Add note…", self._add_note)
        self._more_menu.addAction("Bulk add from text…", self._bulk_add)
        self._more_menu.addAction("Generate cloze deck…", self._generate_cloze)
        self._new_type_action = self._more_menu.addAction(
            "New note type…", self._new_note_type
        )
        more.setMenu(self._more_menu)
        list_header.addWidget(title)
        list_header.addStretch(1)
        list_header.addWidget(new_deck)
        list_header.addWidget(more)
        left_l.addLayout(list_header)

        self._search = QLineEdit()
        self._search.setObjectName("DeckSearch")
        self._search.setPlaceholderText("Search decks…")
        self._search.setAccessibleName("Search decks")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self.refresh)
        left_l.addWidget(self._search)

        self._deck_tree = FolderTreeWidget(context=self._context)
        self._deck_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._deck_tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self._deck_tree.item_selected.connect(self._on_tree_item_selected)
        left_l.addWidget(self._deck_tree, 1)

        self._no_decks_label = QLabel("")
        self._no_decks_label.setObjectName("PageSubtitle")
        self._no_decks_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_decks_label.setWordWrap(True)
        self._no_decks_label.setVisible(False)
        left_l.addWidget(self._no_decks_label)

        layout.addWidget(left, 0)

        # -- right pane: selected deck detail -------------------------------
        right = QWidget()
        right.setObjectName("Page")
        right_l = QVBoxLayout(right)
        apply_page_margins(right_l, self._context)
        right_l.setSpacing(tokens.layout.gap)

        self._detail_empty = QLabel("Select a deck to see its cards.")
        self._detail_empty.setObjectName("PageSubtitle")
        self._detail_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_l.addWidget(self._detail_empty, 1)

        self._detail = QWidget()
        self._detail.setObjectName("Page")
        detail_l = QVBoxLayout(self._detail)
        detail_l.setContentsMargins(0, 0, 0, 0)
        detail_l.setSpacing(tokens.layout.gap)

        detail_header = QHBoxLayout()
        detail_header.setSpacing(d.space(1.5))
        self._detail_title = QLabel("")
        self._detail_title.setObjectName("TopTitle")
        self._detail_kind = QLabel("DECK")
        self._detail_kind.setObjectName("DeckKindTag")
        self._detail_kind.setAccessibleName("Deck")
        self._detail_badges = StateBadges()
        self._detail_badges.setAccessibleName("Card counts by state")
        detail_header.addWidget(self._detail_title)
        detail_header.addWidget(self._detail_kind)
        detail_header.addWidget(self._detail_badges)
        detail_header.addStretch(1)
        self._focus_btn = QPushButton("Focus")
        self._focus_btn.setObjectName("GhostButton")
        self._focus_btn.setAccessibleName("Start focus session for this deck")
        self._focus_btn.setVisible(False)
        self._focus_btn.clicked.connect(self._on_focus_clicked)
        add_note = QPushButton("Add note")
        add_note.setAccessibleName("Add note to this deck")
        add_note.clicked.connect(self._add_note_to_selected)
        self._deck_more_btn = QPushButton("More…")
        self._deck_more_btn.setObjectName("GhostButton")
        self._deck_more_btn.setAccessibleName("More actions for this deck")
        self._deck_more_btn.clicked.connect(self._open_deck_menu)
        detail_header.addWidget(self._focus_btn)
        detail_header.addWidget(add_note)
        detail_header.addWidget(self._deck_more_btn)
        detail_l.addLayout(detail_header)

        actions = QHBoxLayout()
        actions.setSpacing(d.space(1.5))
        self._review_card = StudyActionCard(
            "Review", "Scheduled study — FSRS picks what's due", accent=True)
        self._review_card.clicked.connect(self._on_review_clicked)
        self._quick_pass_card = StudyActionCard(
            "Quick pass", "Fast yes/no run over due cards")
        self._quick_pass_card.clicked.connect(self._on_quick_pass_clicked)
        self._cram_card = StudyActionCard(
            "Cram", "Untracked practice — nothing is rescheduled")
        self._cram_card.clicked.connect(self._on_cram_clicked)
        for card in (self._review_card, self._quick_pass_card, self._cram_card):
            card.setMinimumHeight(int(d.min_target * 1.4))
            actions.addWidget(card, 1)
        detail_l.addLayout(actions)

        detail_l.addWidget(self._notes, 1)

        self._detail.setVisible(False)
        right_l.addWidget(self._detail, 1)
        layout.addWidget(right, 1)

        return page

    # -- detail-pane helpers --------------------------------------------------

    def _add_note_to_selected(self) -> None:
        if self._context.db is None:
            return
        deck_id = self._sel_deck_ids[0] if len(self._sel_deck_ids) == 1 else None
        if AddNoteDialog(self._context, deck_id=deck_id, parent=self).exec():
            self.refresh()

    def _open_deck_menu(self) -> None:
        if len(self._sel_deck_ids) != 1 or self._sel_summary is None:
            return
        deck = self._sel_summary.deck
        self._deck_menu(
            deck.id, deck.name, deck.is_favorite, deck.is_default,
            self._deck_more_btn.mapToGlobal(self._deck_more_btn.rect().bottomLeft()),
        )

    def _generate_cloze(self) -> None:
        from ui.views.cloze_generator_dialog import ClozeGeneratorDialog

        if self._context.db is None:
            return
        if ClozeGeneratorDialog(self._context, self).exec():
            self.refresh()

    def _bulk_add(self) -> None:
        from ui.views.bulk_generate_dialog import BulkGenerateDialog

        if self._context.db is None:
            return
        if BulkGenerateDialog(self._context, self).exec():
            self.refresh()

    def refresh(self) -> None:
        self._new_type_action.setVisible(self._context.settings.get("mode") == "advanced")

        if self._context.db is None:
            self._deck_tree.setVisible(False)
            self._no_decks_label.setText("No database available.")
            self._no_decks_label.setVisible(True)
            self._show_detail_empty("No database available.")
            return

        with self._context.db.session() as session:
            roots = DeckService(session).list_summaries_tree("card")
            all_leaf_ids = [
                n["data"]["summary"].deck.id
                for n in _walk_flat(roots)
                if n["data"] is not None
            ]
            deadline_per_deck = DeadlineService(session).deadlines_for_decks(all_leaf_ids)

        query = self._search.text().strip().lower()
        items = _flatten_for_tree(roots, query, deadline_per_deck)

        if not roots:
            self._deck_tree.setVisible(False)
            self._no_decks_label.setText("No decks yet. Create one to get started.")
            self._no_decks_label.setVisible(True)
            self._show_detail_empty("Create a deck to get started.")
            return
        if not items:
            self._deck_tree.setVisible(False)
            self._no_decks_label.setText("No decks match your search.")
            self._no_decks_label.setVisible(True)
            self._show_detail_empty("No decks match your search.")
            return

        self._no_decks_label.setVisible(False)
        self._deck_tree.setVisible(True)
        self._deck_tree.populate(items)

        # Keep the detail pane pointing at a live selection: reuse the current
        # one when it still exists, else auto-select the first leaf so the
        # pane is never blank.
        if not self._reselect(self._sel_deck_ids):
            self._select_first_leaf()

    # -- tree interaction ---------------------------------------------------

    def _select_first_leaf(self) -> None:
        def _first_leaf(item):
            if item.data(0, Qt.ItemDataRole.UserRole) is not None:
                return item
            for i in range(item.childCount()):
                found = _first_leaf(item.child(i))
                if found is not None:
                    return found
            return None

        for i in range(self._deck_tree.topLevelItemCount()):
            leaf = _first_leaf(self._deck_tree.topLevelItem(i))
            if leaf is not None:
                self._deck_tree.setCurrentItem(leaf)
                # The tree only emits item_selected on user clicks.
                self._on_tree_item_selected(leaf.data(0, Qt.ItemDataRole.UserRole))
                return
        self._show_detail_empty("Select a deck to see its cards.")

    def _reselect(self, deck_ids: list[int]) -> bool:
        """Re-select the tree row for a previously selected single deck."""
        if len(deck_ids) != 1:
            return False
        target = deck_ids[0]

        def _find(item):
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data is not None and data.deck.id == target:
                return item
            for i in range(item.childCount()):
                found = _find(item.child(i))
                if found is not None:
                    return found
            return None

        for i in range(self._deck_tree.topLevelItemCount()):
            item = _find(self._deck_tree.topLevelItem(i))
            if item is not None:
                self._deck_tree.setCurrentItem(item)
                self._on_tree_item_selected(item.data(0, Qt.ItemDataRole.UserRole))
                return True
        return False

    def _show_detail_empty(self, message: str) -> None:
        self._sel_deck_ids = []
        self._sel_summary = None
        self._detail.setVisible(False)
        self._detail_empty.setText(message)
        self._detail_empty.setVisible(True)

    def _on_tree_item_selected(self, data: DeckSummary | None) -> None:
        if data is not None:
            self._sel_summary = data
            self._sel_deck_ids = [data.deck.id]
        else:
            self._sel_summary = None
            self._sel_deck_ids = [s.deck.id for s in self._deck_tree.selected_all_data()]
        if not self._sel_deck_ids:
            self._show_detail_empty("Select a deck to see its cards.")
            return
        self._update_detail()

    def _update_detail(self) -> None:
        single = self._sel_summary is not None and len(self._sel_deck_ids) == 1
        if single:
            deck = self._sel_summary.deck
            self._detail_title.setText(deck.name)
            self._detail_kind.setText("DECK")
            self._detail_kind.setAccessibleName("Deck")
        else:
            n = len(self._sel_deck_ids)
            self._detail_title.setText(f"{n} decks")
            self._detail_kind.setText("GROUP")
            self._detail_kind.setAccessibleName("Deck group")

        new = learning = review = 0
        if self._context.db is not None:
            with self._context.db.session() as session:
                cards = DeckService(session).cards
                for deck_id in self._sel_deck_ids:
                    counts = cards.state_counts(deck_id)
                    new += counts["new"]
                    learning += counts["learning"]
                    review += counts["review"]
        self._detail_badges.set_counts(new, learning, review)

        self._deck_more_btn.setVisible(single)
        self._focus_btn.setVisible(
            single and bool(self._context.settings.get("companion_enabled"))
        )

        # Only a single concrete deck gets the embedded note browser.
        if single:
            self._notes.open_deck(self._sel_deck_ids[0], self._sel_summary.deck.name)
            self._notes.setVisible(True)
        else:
            self._notes.setVisible(False)

        self._detail_empty.setVisible(False)
        self._detail.setVisible(True)

    def _on_tree_context_menu(self, pos) -> None:
        item = self._deck_tree.itemAt(pos)
        if item is None:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None:
            return  # no menu for virtual parent nodes
        deck = data.deck
        self._deck_menu(deck.id, deck.name, deck.is_favorite, deck.is_default,
                        self._deck_tree.mapToGlobal(pos))

    def _on_review_clicked(self) -> None:
        if self._sel_summary is not None:
            self._start_review(self._sel_summary.deck.id, _DECKS_PAGE)
        elif self._sel_deck_ids:
            self._start_review_multi(list(self._sel_deck_ids), _DECKS_PAGE)

    def _on_cram_clicked(self) -> None:
        if self._sel_summary is not None:
            self._start_cram(self._sel_summary.deck.id)
        elif self._sel_deck_ids:
            self._start_cram_multi(list(self._sel_deck_ids))

    def _on_quick_pass_clicked(self) -> None:
        if self._sel_summary is not None:
            self._start_quick_pass(self._sel_summary.deck.id)
        elif self._sel_deck_ids:
            self._start_quick_pass_multi(list(self._sel_deck_ids))

    def _on_focus_clicked(self) -> None:
        if self._sel_summary is not None:
            self._start_focus(self._sel_summary.deck.id, self._sel_summary.deck.name)

    def _deck_menu(self, deck_id, name, is_favorite, is_default, global_pos) -> None:
        menu = QMenu(self)
        menu.addAction("Unfavorite" if is_favorite else "Favorite",
                       lambda: self._set_favorite(deck_id, not is_favorite))
        menu.addAction("Rename…", lambda: self._rename(deck_id, name))
        menu.addAction("Set category…", lambda: self._set_category(deck_id))
        menu.addAction("Set color…", lambda: self._set_color(deck_id))
        menu.addAction("Duplicate deck", lambda: self._duplicate_deck(deck_id, name))
        menu.addAction("Quick pass…", lambda: self._start_quick_pass(deck_id))
        menu.addAction("Cram deck…", lambda: self._start_cram(deck_id))
        if self._context.settings.get("companion_enabled"):
            menu.addAction("Focus session…", lambda: self._start_focus(deck_id, name))
        if not is_default:
            menu.addSeparator()
            menu.addAction("Delete", lambda: self._delete_deck(deck_id, name))
        menu.exec(global_pos)

    # -- deck actions -------------------------------------------------------

    def _with_decks(self, fn) -> None:
        with self._context.db.session() as session:
            fn(DeckService(session))
        self.refresh()

    def _new_deck(self) -> None:
        if self._context.db is None:
            return
        name, ok = QInputDialog.getText(self, "New deck", "Deck name:")
        if not ok or not name.strip():
            return
        deck_id: int
        with self._context.db.session() as session:
            deck = DeckService(session).create(name.strip())
            deck_id = deck.id
            upcoming = DeadlineService(session).upcoming()
            deadline_opts = [(dl.id, dl.name) for dl in upcoming]

        # Offer to link the new deck to an upcoming deadline.
        if deadline_opts:
            items = ["(no deadline)"] + [n for _, n in deadline_opts]
            choice, ok2 = QInputDialog.getItem(
                self, "Link to deadline",
                f"Link \"{name.strip()}\" to an upcoming deadline?",
                items, 0, False,
            )
            if ok2 and choice != "(no deadline)":
                chosen_idx = items.index(choice) - 1
                dl_id = deadline_opts[chosen_idx][0]
                with self._context.db.session() as session:
                    DeadlineService(session).attach_deck(dl_id, deck_id)
        self.refresh()

    def _set_favorite(self, deck_id, favorite) -> None:
        self._with_decks(lambda svc: svc.set_favorite(deck_id, favorite))

    def _rename(self, deck_id, current) -> None:
        name, ok = QInputDialog.getText(self, "Rename deck", "New name:", text=current)
        if ok and name.strip():
            self._with_decks(lambda svc: svc.rename(deck_id, name.strip()))

    def _set_category(self, deck_id) -> None:
        category, ok = QInputDialog.getText(self, "Set category", "Category (blank to clear):")
        if ok:
            self._with_decks(lambda svc: svc.set_category(deck_id, category.strip() or None))

    def _set_color(self, deck_id) -> None:
        color = QColorDialog.getColor(QColor("#5c7cfa"), self, "Deck color")
        if color.isValid():
            self._with_decks(lambda svc: svc.set_color(deck_id, color.name()))

    def _duplicate_deck(self, deck_id, name) -> None:
        from domain.notes.note_service import NoteService

        if self._context.db is None:
            return
        with self._context.db.session() as session:
            new_deck = DeckService(session).create(
                f"{name} (copy)",
                category=self._deck_category(session, deck_id),
            )
            copied = NoteService(session, self._context.engine).copy_notes_to_deck(
                deck_id, new_deck.id
            )
        QMessageBox.information(
            self, "Duplicate deck",
            f"Created “{name} (copy)” with {copied} card{'s' if copied != 1 else ''}.",
        )
        self.refresh()

    @staticmethod
    def _deck_category(session, deck_id):
        deck = DeckService(session).decks.get(deck_id)
        return deck.category if deck is not None else None

    def _delete_deck(self, deck_id, name) -> None:
        with self._context.db.session() as session:
            counts = DeckService(session).cards.state_counts(deck_id)
        total = counts["new"] + counts["learning"] + counts["review"]
        confirm = QMessageBox.question(
            self, "Delete deck",
            f"Delete “{name}” and its {total} card{'s' if total != 1 else ''}?\n\n"
            "This cannot be undone.",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self._with_decks(lambda svc: svc.delete(deck_id))

    def _add_note(self) -> None:
        if self._context.db is None:
            return
        if AddNoteDialog(self._context, parent=self).exec():
            self.refresh()

    def _new_note_type(self) -> None:
        if self._context.db is None:
            return
        NoteTypeEditor(self._context, parent=self).exec()

    # -- navigation ---------------------------------------------------------

    def _deck_names(self, deck_ids: list[int]) -> list[str]:
        if self._context.db is None:
            return []
        with self._context.db.session() as session:
            decks = DeckService(session).decks
            return [d.name for deck_id in deck_ids
                    if (d := decks.get(deck_id)) is not None]

    def _start_review(self, deck_id, return_page) -> None:
        self._review_return = return_page
        names = self._deck_names([deck_id])
        self._review.start(deck_id, deck_name=names[0] if names else None)
        self._stack.setCurrentIndex(_REVIEW_PAGE)

    def _start_review_multi(self, deck_ids: list[int], return_page: int) -> None:
        self._review_return = return_page
        self._review.start_multi(deck_ids, deck_names=self._deck_names(deck_ids))
        self._stack.setCurrentIndex(_REVIEW_PAGE)

    def _start_cram(self, deck_id) -> None:
        self._cram_return = _DECKS_PAGE
        self._cram.start(deck_id)
        self._stack.setCurrentIndex(_CRAM_PAGE)

    def _start_cram_multi(self, deck_ids: list[int]) -> None:
        self._cram_return = _DECKS_PAGE
        self._cram.start_multi(deck_ids)
        self._stack.setCurrentIndex(_CRAM_PAGE)

    def _start_quick_pass(self, deck_id) -> None:
        self._quick_pass.start(deck_id)
        self._stack.setCurrentIndex(_QUICK_PASS_PAGE)

    def _start_quick_pass_multi(self, deck_ids: list[int]) -> None:
        self._quick_pass.start_multi(deck_ids)
        self._stack.setCurrentIndex(_QUICK_PASS_PAGE)

    def _on_quick_pass_finished(self) -> None:
        self._stack.setCurrentIndex(_DECKS_PAGE)
        self.refresh()

    def _start_focus(self, deck_id, name) -> None:
        self._focus.start(deck_id, name)
        self._stack.setCurrentIndex(_FOCUS_PAGE)

    def _on_focus_finished(self) -> None:
        self._stack.setCurrentIndex(_DECKS_PAGE)
        self.refresh()

    def _on_review_finished(self) -> None:
        self._stack.setCurrentIndex(self._review_return)
        self.refresh()

    def _on_cram_finished(self) -> None:
        self._stack.setCurrentIndex(self._cram_return)
        self.refresh()

    def showEvent(self, event: QShowEvent) -> None:  # type: ignore[override]
        super().showEvent(event)
        if self._stack.currentIndex() == _DECKS_PAGE:
            self.refresh()
