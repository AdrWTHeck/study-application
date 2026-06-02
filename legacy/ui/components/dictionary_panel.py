"""DictionaryPanel — dockable side panel with search and lookup."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDockWidget, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QTextBrowser, QVBoxLayout, QWidget,
)

from services.accessibility.dictionary_service import DictionaryResult, DictionaryService
from ui.components.dictionary_popover import _format_result


class _SearchWorker(QThread):
    results_ready = pyqtSignal(list)   # list[str] suggestions

    def __init__(self, svc: DictionaryService, query: str) -> None:
        super().__init__()
        self._svc = svc
        self._query = query

    def run(self) -> None:
        self.results_ready.emit(self._svc.search(self._query))


class _LookupWorker(QThread):
    finished = pyqtSignal(object)

    def __init__(self, svc: DictionaryService, word: str) -> None:
        super().__init__()
        self._svc = svc
        self._word = word

    def run(self) -> None:
        self.finished.emit(self._svc.lookup(self._word))


class _PanelBody(QWidget):
    """Inner widget so DictionaryPanel can be embedded or docked."""

    def __init__(self, svc: DictionaryService, parent=None) -> None:
        super().__init__(parent)
        self._svc = svc
        self._search_worker: _SearchWorker | None = None
        self._lookup_worker: _LookupWorker | None = None

        layout = QVBoxLayout(self)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search word…")
        self._search_box.textChanged.connect(self._on_text_changed)
        self._search_box.returnPressed.connect(self._on_enter)
        layout.addWidget(self._search_box)

        self._suggest_list = QListWidget()
        self._suggest_list.setMaximumHeight(100)
        self._suggest_list.itemClicked.connect(self._on_suggestion_clicked)
        layout.addWidget(self._suggest_list)

        self._result = QTextBrowser()
        self._result.setOpenExternalLinks(False)
        layout.addWidget(self._result)

    def look_up(self, word: str) -> None:
        self._search_box.setText(word)
        self._start_lookup(word)

    def _on_text_changed(self, text: str) -> None:
        if len(text) < 2:
            self._suggest_list.clear()
            return
        if self._search_worker:
            self._search_worker.quit()
        self._search_worker = _SearchWorker(self._svc, text)
        self._search_worker.results_ready.connect(self._show_suggestions)
        self._search_worker.start()

    def _on_enter(self) -> None:
        self._start_lookup(self._search_box.text().strip())

    def _on_suggestion_clicked(self, item: QListWidgetItem) -> None:
        word = item.text()
        self._search_box.setText(word)
        self._start_lookup(word)

    def _show_suggestions(self, words: list[str]) -> None:
        self._suggest_list.clear()
        for w in words[:10]:
            self._suggest_list.addItem(w)

    def _start_lookup(self, word: str) -> None:
        if not word:
            return
        self._result.setHtml("<p>Looking up…</p>")
        if self._lookup_worker:
            self._lookup_worker.quit()
        self._lookup_worker = _LookupWorker(self._svc, word)
        self._lookup_worker.finished.connect(self._on_result)
        self._lookup_worker.start()

    def _on_result(self, result: DictionaryResult) -> None:
        self._result.setHtml(_format_result(result))


class DictionaryPanel(QDockWidget):
    """QDockWidget wrapping the dictionary panel body.

    Attach to QMainWindow via addDockWidget().
    Call look_up(word) to pre-populate the search box.
    """

    def __init__(self, svc: DictionaryService, parent=None) -> None:
        super().__init__("Dictionary", parent)
        self._body = _PanelBody(svc, self)
        self.setWidget(self._body)
        self.setMinimumWidth(280)
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )

    def look_up(self, word: str) -> None:
        self._body.look_up(word)
        if not self.isVisible():
            self.show()
