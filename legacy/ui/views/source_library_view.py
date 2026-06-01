"""SourceLibraryView — PDF library with upload, viewer, and question generation."""
from __future__ import annotations

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from services.ingestion.pdf_service import PDFService
from services.quiz.quiz_service import QuizService
from ui.views.pdf_viewer_view import PdfViewerView


class _GenerateWorker(QThread):
    finished = pyqtSignal(int)   # question count

    def __init__(self, doc_id: int, deck_id: int) -> None:
        super().__init__()
        self._doc_id = doc_id
        self._deck_id = deck_id

    def run(self) -> None:
        n = QuizService().generate_for_document(self._doc_id, self._deck_id)
        self.finished.emit(n)


class _UploadWorker(QThread):
    finished = pyqtSignal(int)   # source_document_id or -1 on failure

    def __init__(self, path: str) -> None:
        super().__init__()
        self._path = path

    def run(self) -> None:
        doc = PDFService().upload(self._path)
        self.finished.emit(doc.id if doc else -1)


class SourceLibraryView(QWidget):
    """Left: list of uploaded PDFs.  Right: embedded PDF viewer."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._doc_ids: list[int] = []
        self._doc_paths: dict[int, str] = {}
        self._gen_worker: _GenerateWorker | None = None
        self._upload_worker: _UploadWorker | None = None
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel
        left = QWidget()
        lv = QVBoxLayout(left)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.currentRowChanged.connect(self._on_selection)
        lv.addWidget(self._list)

        btn_row = QHBoxLayout()
        self._upload_btn = QPushButton("Upload PDF")
        self._upload_btn.clicked.connect(self._upload)
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.clicked.connect(self._delete)
        self._gen_btn = QPushButton("Generate Questions")
        self._gen_btn.clicked.connect(self._generate)
        btn_row.addWidget(self._upload_btn)
        btn_row.addWidget(self._delete_btn)
        btn_row.addWidget(self._gen_btn)
        lv.addLayout(btn_row)

        self._status = QLabel("")
        lv.addWidget(self._status)
        left.setMinimumWidth(220)

        # Right panel — PDF viewer
        self._viewer = PdfViewerView()

        splitter.addWidget(left)
        splitter.addWidget(self._viewer)
        splitter.setStretchFactor(1, 3)
        root.addWidget(splitter)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        self._list.clear()
        self._doc_ids = []
        self._doc_paths = {}
        db = __import__("models.base", fromlist=["get_session"]).get_session()
        try:
            from repositories.source_repository import SourceRepository
            for doc in SourceRepository(db).get_all():
                self._list.addItem(
                    QListWidgetItem(
                        f"{doc.filename}  [{doc.extraction_status}]"
                    )
                )
                self._doc_ids.append(doc.id)
                self._doc_paths[doc.id] = doc.file_path
        finally:
            db.close()
        self._status.setText(f"{len(self._doc_ids)} document(s)")

    def _selected_doc_id(self) -> int | None:
        idx = self._list.currentRow()
        return self._doc_ids[idx] if 0 <= idx < len(self._doc_ids) else None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_selection(self, idx: int) -> None:
        if 0 <= idx < len(self._doc_ids):
            path = self._doc_paths.get(self._doc_ids[idx])
            if path:
                self._viewer.load(path)

    def _upload(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", "", "PDF Files (*.pdf)"
        )
        if not path:
            return
        self._status.setText("Uploading…")
        self._upload_btn.setEnabled(False)
        self._upload_worker = _UploadWorker(path)
        self._upload_worker.finished.connect(self._on_upload_done)
        self._upload_worker.start()

    def _on_upload_done(self, doc_id: int) -> None:
        self._upload_btn.setEnabled(True)
        if doc_id < 0:
            QMessageBox.warning(self, "Upload Failed",
                                "Could not extract text from the PDF.")
        self._refresh()

    def _delete(self) -> None:
        doc_id = self._selected_doc_id()
        if doc_id is None:
            return
        ans = QMessageBox.question(self, "Delete Document",
                                   "Delete this document and all its segments?")
        if ans == QMessageBox.StandardButton.Yes:
            PDFService().delete_source(doc_id)
            self._refresh()

    def _generate(self) -> None:
        doc_id = self._selected_doc_id()
        if doc_id is None:
            QMessageBox.information(self, "Generate Questions",
                                    "Select a document first.")
            return
        # Ask which test deck to use
        from services.cards.deck_service import DeckService
        decks = DeckService().get_all("test")
        if not decks:
            QMessageBox.warning(self, "No Test Deck",
                                "No test deck found. Create one first.")
            return
        deck_id = decks[0].id  # default to first (or could prompt user)

        self._gen_btn.setEnabled(False)
        self._status.setText("Generating questions…")
        self._gen_worker = _GenerateWorker(doc_id, deck_id)
        self._gen_worker.finished.connect(self._on_gen_done)
        self._gen_worker.start()

    def _on_gen_done(self, count: int) -> None:
        self._gen_btn.setEnabled(True)
        self._status.setText(f"Generated {count} question(s).")
