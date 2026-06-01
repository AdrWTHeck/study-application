"""PdfViewerView — page-by-page PDF display using RenderService."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from config.constants import PDF_RENDER_DPI
from services.ingestion.render_service import RenderService


class _RenderWorker(QThread):
    page_ready = pyqtSignal(bytes)   # PNG bytes

    def __init__(self, path: str, page: int, dpi: int) -> None:
        super().__init__()
        self._path = path
        self._page = page
        self._dpi = dpi

    def run(self) -> None:
        svc = RenderService()
        data = svc.render_page(self._path, self._page, self._dpi)
        if data:
            self.page_ready.emit(data)


class PdfViewerView(QWidget):
    """Renders and displays one PDF page at a time.

    Call load(file_path) to open a document.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._path: str | None = None
        self._page = 0
        self._total = 0
        self._worker: _RenderWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Navigation bar
        nav = QHBoxLayout()
        self._prev_btn = QPushButton("◀ Prev")
        self._prev_btn.clicked.connect(self._prev)
        self._next_btn = QPushButton("Next ▶")
        self._next_btn.clicked.connect(self._next)
        self._page_label = QLabel("–")
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav.addWidget(self._prev_btn)
        nav.addStretch()
        nav.addWidget(self._page_label)
        nav.addStretch()
        nav.addWidget(self._next_btn)
        layout.addLayout(nav)

        # Scrollable image area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._image_label = QLabel("No document loaded")
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._scroll.setWidget(self._image_label)
        layout.addWidget(self._scroll)

        self._set_nav_enabled(False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, file_path: str) -> None:
        from services.ingestion.render_service import RenderService
        self._path = file_path
        self._total = RenderService().get_page_count(file_path)
        self._page = 0
        self._set_nav_enabled(self._total > 0)
        if self._total > 0:
            self._render()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _render(self) -> None:
        if not self._path:
            return
        self._page_label.setText(f"Page {self._page + 1} of {self._total}")
        if self._worker:
            self._worker.quit()
        self._worker = _RenderWorker(self._path, self._page, PDF_RENDER_DPI)
        self._worker.page_ready.connect(self._show_page)
        self._worker.start()
        self._image_label.setText("Rendering…")

    def _show_page(self, png_bytes: bytes) -> None:
        px = QPixmap()
        px.loadFromData(png_bytes, "PNG")
        available_w = self._scroll.viewport().width() - 10
        if px.width() > available_w:
            px = px.scaledToWidth(
                available_w, Qt.TransformationMode.SmoothTransformation
            )
        self._image_label.setPixmap(px)

    def _prev(self) -> None:
        if self._page > 0:
            self._page -= 1
            self._render()

    def _next(self) -> None:
        if self._page < self._total - 1:
            self._page += 1
            self._render()

    def _set_nav_enabled(self, enabled: bool) -> None:
        self._prev_btn.setEnabled(enabled)
        self._next_btn.setEnabled(enabled)
