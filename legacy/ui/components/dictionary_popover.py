"""DictionaryPopover — modal dialog showing a word lookup result."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QScrollArea,
    QTextBrowser, QVBoxLayout, QWidget,
)

from services.accessibility.dictionary_service import DictionaryResult, DictionaryService


class _LookupWorker(QThread):
    finished = pyqtSignal(object)   # DictionaryResult

    def __init__(self, svc: DictionaryService, word: str) -> None:
        super().__init__()
        self._svc = svc
        self._word = word

    def run(self) -> None:
        self.finished.emit(self._svc.lookup(self._word))


def _format_result(result: DictionaryResult) -> str:
    if not result.found:
        return f"<p>No definition found for <b>{result.word}</b>.</p>"

    parts: list[str] = [f"<h3>{result.word}</h3>"]

    if result.wordnet_entries:
        parts.append("<b>WordNet</b><ol>")
        for entry in result.wordnet_entries[:5]:
            syns = ", ".join(entry.synonyms[:4]) if entry.synonyms else "–"
            ants = ", ".join(entry.antonyms[:3]) if entry.antonyms else "–"
            ex   = f"<i>{entry.examples[0]}</i>" if entry.examples else ""
            parts.append(
                f"<li><i>{entry.pos}</i> — {entry.definition}"
                f"{' ' + ex if ex else ''}"
                f"<br><small>Synonyms: {syns} &nbsp;|&nbsp; Antonyms: {ants}</small></li>"
            )
        parts.append("</ol>")

    if result.webster_definition:
        brief = result.webster_definition[:300]
        if len(result.webster_definition) > 300:
            brief += "…"
        parts.append(f"<b>Webster's 1913</b><p>{brief}</p>")

    if result.ay_synonyms:
        parts.append(
            f"<b>Synonyms</b> <small>(online)</small>: "
            f"{', '.join(result.ay_synonyms[:10])}"
        )
    if result.ay_antonyms:
        parts.append(
            f"<b>Antonyms</b> <small>(online)</small>: "
            f"{', '.join(result.ay_antonyms[:10])}"
        )

    return "\n".join(parts)


class DictionaryPopover(QDialog):
    """Shows a word definition in a scrollable dialog.

    The lookup runs on a QThread so the UI stays responsive.
    Usage:
        pop = DictionaryPopover(svc, parent)
        pop.look_up("photosynthesis")
        pop.exec()
    """

    def __init__(self, svc: DictionaryService, parent=None) -> None:
        super().__init__(parent)
        self._svc = svc
        self._worker: _LookupWorker | None = None
        self.setWindowTitle("Dictionary")
        self.setMinimumSize(440, 320)
        self.resize(480, 400)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )

        layout = QVBoxLayout(self)
        self._status = QLabel("Looking up…")
        layout.addWidget(self._status)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(False)
        layout.addWidget(self._browser)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def look_up(self, word: str) -> None:
        self._status.setText(f'Looking up “{word}”…')
        self._browser.clear()
        if self._worker:
            self._worker.quit()
        self._worker = _LookupWorker(self._svc, word)
        self._worker.finished.connect(self._on_result)
        self._worker.start()

    def _on_result(self, result: DictionaryResult) -> None:
        self._status.setText("")
        self._browser.setHtml(_format_result(result))
