"""App-wide search view: query notes, questions, and sources; jump to the
relevant section. The FTS index is rebuilt lazily when the view is (re)opened.
"""
from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from app.navigation import Destination
from ui.components.containers import themed_scroll_area
from ui.utils.layouts import apply_page_margins, clear_layout
from domain.search.search_service import SearchResult, SearchService

_TYPE_DEST = {
    "note": Destination.CARDS,
    "question": Destination.TESTS,
    "source": Destination.LIBRARY,
    "deadline": Destination.DEADLINES,
}
_TYPE_LABEL = {
    "note": "Card",
    "question": "Question",
    "source": "Source",
    "deadline": "Deadline",
    "dictionary": "Dictionary",
}


class SearchView(QWidget):
    def __init__(self, context: AppContext,
                 navigate: Callable[[Destination], None] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self._navigate = navigate
        self.setObjectName("Page")
        self.setAccessibleName("Search")
        self._service = SearchService(context.db, context.dictionary) if context.db is not None else None
        self._needs_rebuild = True

        layout = QVBoxLayout(self)
        apply_page_margins(layout, self._context)
        layout.setSpacing(12)

        title = QLabel("Search")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Search cards, questions, sources, deadlines, and dictionary…")
        self._input.setAccessibleName("Search query")
        self._input.textChanged.connect(lambda: self._debounce.start())
        self._input.returnPressed.connect(self._run)
        layout.addWidget(self._input)

        self._status = QLabel("")
        self._status.setObjectName("SettingsHint")
        layout.addWidget(self._status)

        scroll, self._results, self._results_layout = themed_scroll_area(spacing=8)
        layout.addWidget(scroll, 1)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._run)

    def focus_search(self) -> None:
        self._input.setFocus()
        self._input.selectAll()

    def _run(self) -> None:
        clear_layout(self._results_layout)

        query = self._input.text().strip()
        if self._service is None or not query:
            self._status.setText("")
            return
        if self._needs_rebuild:
            # Build once; incremental updates keep it fresh thereafter.
            self._service.ensure_built()
            self._needs_rebuild = False
        results = self._service.search(query)
        self._status.setText(f"{len(results)} result{'s' if len(results) != 1 else ''}")
        for result in results:
            self._results_layout.addWidget(self._result_row(result))

    def _result_row(self, result: SearchResult) -> QWidget:
        row = QWidget()
        row.setObjectName("DeckRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        kind = QLabel(_TYPE_LABEL.get(result.type, result.type))
        kind.setObjectName("SettingsHint")
        kind.setFixedWidth(80)
        layout.addWidget(kind)

        text = QLabel(f"{result.title} — {result.snippet}")
        text.setObjectName("DeckName")
        text.setWordWrap(True)
        layout.addWidget(text, 1)

        dest = _TYPE_DEST.get(result.type)
        if dest is not None and self._navigate is not None:
            open_btn = QPushButton("Open")
            open_btn.setAccessibleName(f"Open in {dest.title}")
            open_btn.clicked.connect(lambda _=False, d=dest: self._navigate(d))
            layout.addWidget(open_btn)
        return row

    def showEvent(self, event: QShowEvent) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._needs_rebuild = True  # refresh the index next time a search runs
