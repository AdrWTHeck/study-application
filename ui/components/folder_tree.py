"""Collapsible folder/deck tree with a custom row renderer.

Derives hierarchy from '::'-separated path strings — the same convention Anki
uses for nested decks. Each leaf item carries arbitrary *data* (emitted on
click), an optional *fav* flag, and optional *badges* — a list of
``(role, count)`` pairs rendered as state-coloured count pills. Virtual parent
nodes (no matching leaf) are drawn as muted folder headers.

The rows are painted by :class:`_DeckRowDelegate` so decks read as clean,
roomy rows with badges instead of a bare data grid.

Usage::

    tree = FolderTreeWidget(context=ctx)
    tree.populate([
        {"path": "Science::Biology", "data": deck_id, "fav": True,
         "badges": [("new", 2), ("learning", 0), ("review", 3)]},
        {"path": "Math", "data": deck_id3, "badges": [("count", 12)]},
    ])
    tree.item_selected.connect(lambda data: ...)
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QStyle, QStyledItemDelegate, QTreeWidget, QTreeWidgetItem

from domain.decks.hierarchy import SEP, split_path

# Item data roles (kept on column 0 of each QTreeWidgetItem).
_ROLE_DATA = Qt.ItemDataRole.UserRole
_ROLE_PATH = Qt.ItemDataRole.UserRole + 1
_ROLE_BADGES = Qt.ItemDataRole.UserRole + 2
_ROLE_FAV = Qt.ItemDataRole.UserRole + 3

# Badge role → (palette attribute for the colour, short label shown in the pill).
_BADGE_SPEC: dict[str, tuple[str, str]] = {
    "new": ("state_new", "new"),
    "learning": ("state_learning", "lrn"),
    "review": ("state_review", "due"),
    "count": ("accent", ""),
}


class _DeckRowDelegate(QStyledItemDelegate):
    """Paints a deck/folder row: rounded selection, favourite star, name, badges."""

    def __init__(self, tree: "FolderTreeWidget") -> None:
        super().__init__(tree)
        self._tree = tree

    def sizeHint(self, option, index):  # noqa: N802 (Qt signature)
        size = super().sizeHint(option, index)
        size.setHeight(max(size.height(), self._tree.row_height()))
        return size

    def paint(self, painter: QPainter, option, index) -> None:  # noqa: N802
        pal = self._tree.tokens_palette()
        if pal is None:  # no theme available (e.g. bare unit test) — default paint
            super().paint(painter, option, index)
            return

        rect = option.rect
        data = index.data(_ROLE_DATA)
        is_folder = data is None
        name = index.data(Qt.ItemDataRole.DisplayRole) or ""
        badges = index.data(_ROLE_BADGES) or []
        fav = bool(index.data(_ROLE_FAV))
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        inner = rect.adjusted(2, 2, -6, -2)
        radius = 8.0
        if selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(pal.accent_muted))
            painter.drawRoundedRect(QRectF(inner), radius, radius)
            painter.setBrush(QColor(pal.accent))
            painter.drawRoundedRect(
                QRectF(inner.left(), inner.top() + 3, 3, inner.height() - 6), 1.5, 1.5
            )
        elif hover:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(pal.bg_hover))
            painter.drawRoundedRect(QRectF(inner), radius, radius)

        # Badges, laid out right-to-left along the right edge.
        right = float(inner.right() - 4)
        if not is_folder:
            for role, value in reversed(list(badges)):
                if value in (0, "0", "", None):
                    continue
                attr, label = _BADGE_SPEC.get(role, ("accent", ""))
                txt = f"{value} {label}".strip()
                color = QColor(getattr(pal, attr, pal.accent))
                self._set_badge_font(painter)
                bw = painter.fontMetrics().horizontalAdvance(txt) + 18
                bh = float(min(inner.height() - 8, 22))
                bx = right - bw
                by = inner.center().y() - bh / 2
                pill = QRectF(bx, by, bw, bh)
                fill = QColor(color)
                fill.setAlpha(48)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(fill)
                painter.drawRoundedRect(pill, bh / 2, bh / 2)
                painter.setPen(color)
                painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, txt)
                right = bx - 6

        # Favourite star + name.
        text_x = float(inner.left() + 10)
        if fav and not is_folder:
            painter.setPen(QColor(pal.warning))
            self._set_name_font(painter, is_folder)
            painter.drawText(
                QRectF(text_x, inner.top(), 16, inner.height()),
                Qt.AlignmentFlag.AlignVCenter, "★",
            )
            text_x += 18

        painter.setPen(QColor(pal.text_dim if is_folder else pal.text_primary))
        self._set_name_font(painter, is_folder)
        avail = max(0.0, right - text_x - 8)
        elided = painter.fontMetrics().elidedText(
            str(name), Qt.TextElideMode.ElideRight, int(avail)
        )
        painter.drawText(
            QRectF(text_x, inner.top(), avail, inner.height()),
            Qt.AlignmentFlag.AlignVCenter, elided,
        )
        painter.restore()

    def _set_name_font(self, painter: QPainter, is_folder: bool) -> None:
        font = painter.font()
        font.setBold(False)
        font.setPointSizeF(self._tree.name_pt(is_folder))
        painter.setFont(font)

    def _set_badge_font(self, painter: QPainter) -> None:
        font = painter.font()
        font.setBold(True)
        font.setPointSizeF(max(8.0, self._tree.name_pt(False) - 2))
        painter.setFont(font)


class FolderTreeWidget(QTreeWidget):
    """Single-column collapsible deck/folder tree with badge-rendered rows.

    Signals
    -------
    item_selected(data)
        Emitted when the user clicks any item. *data* is the value stored in the
        item's UserRole (None for virtual parent/folder nodes).
    """

    item_selected = pyqtSignal(object)

    def __init__(self, context=None, parent: QTreeWidget | None = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self._context = context
        self.setObjectName("DeckTree")

        self.setAnimated(True)
        self.setIndentation(16)
        self.setRootIsDecorated(True)
        self.setUniformRowHeights(True)
        self.setFrameShape(QTreeWidget.Shape.NoFrame)
        self.setColumnCount(1)
        self.setHeaderHidden(True)
        self.setItemDelegate(_DeckRowDelegate(self))

        self.itemClicked.connect(self._on_clicked)

        theme = getattr(context, "theme", None) if context is not None else None
        if theme is not None and hasattr(theme, "changed"):
            theme.changed.connect(self._on_theme_changed)

    # ── Theme / metrics (read by the delegate) ───────────────────────────────

    def tokens_palette(self):
        theme = getattr(self._context, "theme", None) if self._context is not None else None
        return theme.tokens.palette if theme is not None else None

    def _tokens(self):
        theme = getattr(self._context, "theme", None) if self._context is not None else None
        return theme.tokens if theme is not None else None

    def row_height(self) -> int:
        tokens = self._tokens()
        return tokens.density.min_target if tokens is not None else 40

    def name_pt(self, is_folder: bool) -> float:
        tokens = self._tokens()
        if tokens is None:
            return 11.0
        return float(tokens.typography.size("caption" if is_folder else "subtitle"))

    def _on_theme_changed(self) -> None:
        self.viewport().update()

    # ── Public API ────────────────────────────────────────────────────────────

    def populate(self, items: list[dict]) -> None:
        """Build (or rebuild) the tree.

        Each item dict accepts:
          - ``"path"``   (str, required): '::'-separated hierarchy path
          - ``"data"``   (any, optional): payload emitted on click
          - ``"label"``  (str, optional): leaf label override
          - ``"fav"``    (bool, optional): show a favourite star
          - ``"badges"`` (list[(role, count)], optional): count pills
          - ``"tip"``    (str, optional): tooltip
        """
        self.blockSignals(True)
        self.clear()

        nodes: dict[str, QTreeWidgetItem] = {}
        sorted_items = sorted(
            items, key=lambda x: (len(split_path(x["path"])), x["path"].lower())
        )

        for item in sorted_items:
            parts = split_path(item["path"])
            if not parts:
                continue

            # Ensure ancestor folder nodes exist.
            for depth_idx in range(len(parts) - 1):
                partial = SEP.join(parts[: depth_idx + 1])
                if partial not in nodes:
                    node = self._make_node(parts[depth_idx], partial, data=None)
                    par_key = SEP.join(parts[:depth_idx]) if depth_idx > 0 else None
                    par = nodes.get(par_key)
                    (par.addChild if par is not None else self.addTopLevelItem)(node)
                    nodes[partial] = node

            path = item["path"]
            if path not in nodes:
                node = self._make_node(
                    item.get("label", parts[-1]), path,
                    data=item.get("data"), fav=item.get("fav", False),
                    badges=item.get("badges"), tip=item.get("tip"),
                )
                par_key = SEP.join(parts[:-1]) if len(parts) > 1 else None
                par = nodes.get(par_key)
                (par.addChild if par is not None else self.addTopLevelItem)(node)
                nodes[path] = node
            else:
                # Promote an existing virtual folder node to a real leaf.
                node = nodes[path]
                node.setData(0, _ROLE_DATA, item.get("data"))
                node.setData(0, _ROLE_FAV, item.get("fav", False))
                node.setData(0, _ROLE_BADGES, item.get("badges") or [])

        self.expandAll()
        self.blockSignals(False)

    def set_item_badges(self, path: str, badges: list) -> None:
        item = self._find_by_path(path)
        if item is not None:
            item.setData(0, _ROLE_BADGES, badges)
            self.viewport().update()

    def get_all_data(self, root_item: QTreeWidgetItem | None = None) -> list:
        results: list = []

        def _collect(node: QTreeWidgetItem) -> None:
            data = node.data(0, _ROLE_DATA)
            if data is not None:
                results.append(data)
            for i in range(node.childCount()):
                _collect(node.child(i))

        if root_item is None:
            for i in range(self.topLevelItemCount()):
                _collect(self.topLevelItem(i))
        else:
            _collect(root_item)
        return results

    def selected_data(self) -> object:
        items = self.selectedItems()
        return items[0].data(0, _ROLE_DATA) if items else None

    def selected_all_data(self) -> list:
        items = self.selectedItems()
        return self.get_all_data(items[0]) if items else []

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _make_node(
        label: str,
        path: str,
        data: object,
        fav: bool = False,
        badges: list | None = None,
        tip: str | None = None,
    ) -> QTreeWidgetItem:
        node = QTreeWidgetItem([label])
        node.setData(0, _ROLE_DATA, data)
        node.setData(0, _ROLE_PATH, path)
        node.setData(0, _ROLE_FAV, fav)
        node.setData(0, _ROLE_BADGES, badges or [])
        if tip:
            node.setToolTip(0, tip)
        return node

    def _find_by_path(self, path: str) -> QTreeWidgetItem | None:
        def _search(node: QTreeWidgetItem) -> QTreeWidgetItem | None:
            if node.data(0, _ROLE_PATH) == path:
                return node
            for i in range(node.childCount()):
                found = _search(node.child(i))
                if found:
                    return found
            return None

        for i in range(self.topLevelItemCount()):
            found = _search(self.topLevelItem(i))
            if found:
                return found
        return None

    def _on_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        self.item_selected.emit(item.data(0, _ROLE_DATA))
