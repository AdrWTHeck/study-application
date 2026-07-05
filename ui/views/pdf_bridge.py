"""QWebChannel bridge — routes JS events to ReaderView."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QMenu

if TYPE_CHECKING:
    from ui.views.reader_view import ReaderView


class PdfBridge(QObject):
    """Registered with QWebChannel as ``bridge``.

    JS calls these slots; Python delegates to the ReaderView that owns us.
    """

    def __init__(self, reader: ReaderView) -> None:
        super().__init__(reader)
        self._reader = reader

    # ── Slots called by JavaScript ────────────────────────────────────────────

    @pyqtSlot(str, str, int, int)
    def showContextMenu(self, selected_text: str, rects_json: str,
                        annot_xref: int, annot_page: int) -> None:
        """Build and show a native Qt context menu at the current cursor position.

        ``rects_json`` is a JSON array of normalised (0..1) selection bounding
        boxes captured from ``range.getClientRects()`` in the JS layer.  When
        present they allow Python to annotate by pixel position rather than
        re-searching the PDF text stream by string content.
        """
        reader = self._reader
        menu = QMenu(reader)

        if annot_xref >= 0:
            # Right-clicked an existing annotation
            edit_act  = menu.addAction("Edit comment")
            card_act  = menu.addAction("Create card from annotation")
            menu.addSeparator()
            del_act   = menu.addAction("Delete annotation")

            chosen = menu.exec(QCursor.pos())
            if chosen == edit_act:
                reader._edit_comment_dialog(annot_xref, annot_page)
            elif chosen == card_act:
                reader._card_from_annotation(annot_xref, annot_page)
            elif chosen == del_act:
                reader._delete_annotation_by_xref(annot_xref, annot_page)

        elif selected_text:
            # Right-clicked with a text selection — parse position rects
            try:
                sel_rects: list[dict] = json.loads(rects_json) if rects_json else []
            except (ValueError, TypeError):
                sel_rects = []

            hl_act      = menu.addAction("Highlight")
            ul_act      = menu.addAction("Underline")
            so_act      = menu.addAction("Strikeout")
            menu.addSeparator()
            card_act    = menu.addAction("Create card")
            look_act    = menu.addAction("Look up in dictionary")
            append_act  = menu.addAction("Append to notes")
            menu.addSeparator()
            del_act     = menu.addAction("Delete annotation at selection")

            chosen = menu.exec(QCursor.pos())
            if chosen == hl_act:
                reader._annotate_text(selected_text, "highlight", sel_rects)
            elif chosen == ul_act:
                reader._annotate_text(selected_text, "underline", sel_rects)
            elif chosen == so_act:
                reader._annotate_text(selected_text, "strikeout", sel_rects)
            elif chosen == card_act:
                reader._create_card_from_text(selected_text)
            elif chosen == look_act:
                reader._lookup_word(selected_text.split()[0] if selected_text else "")
            elif chosen == append_act:
                reader._append_to_notes(selected_text)
            elif chosen == del_act:
                reader._delete_annotation_at_rects(sel_rects, annot_page)

        else:
            # Empty right-click — offer find and bulk-clear
            find_act  = menu.addAction("Find in document (Ctrl+F)")
            menu.addSeparator()
            clear_act = menu.addAction("Clear all annotations on this page")
            chosen = menu.exec(QCursor.pos())
            if chosen == find_act and reader._webview is not None:
                reader._webview.page().runJavaScript("openFindBar()")
            elif chosen == clear_act:
                reader._clear_page_annotations()

    @pyqtSlot(str, str, str, int)
    def quickAnnotate(self, selected_text: str, rects_json: str,
                      mode: str, page: int) -> None:
        """Direct annotation from keyboard shortcut — no context menu shown."""
        try:
            sel_rects: list[dict] = json.loads(rects_json) if rects_json else []
        except (ValueError, TypeError):
            sel_rects = []
        if selected_text and mode in ("highlight", "underline", "strikeout"):
            self._reader._annotate_text(selected_text, mode, sel_rects)

    @pyqtSlot(int)
    def onPageChanged(self, page_num: int) -> None:
        """JS reports the page it just scrolled to."""
        self._reader._page = page_num
        self._reader._update_page_label()
