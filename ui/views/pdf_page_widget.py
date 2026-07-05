"""A PDF page display widget with annotation hit-testing.

Shows the rendered page pixmap (which already has annotations baked in by
PyMuPDF). Annotation overlays are no longer painted here — PyMuPDF renders
them natively. This widget only handles hit-testing so right-clicks on
annotations route to the correct xref for context menu actions.
"""
from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QWidget


class PdfPageWidget(QLabel):
    # Emitted with the annotation's PDF xref when the user right-clicks on one.
    annotation_right_clicked = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAccessibleName("PDF page")
        # Each entry: {"xref": int, "rect": {x0,y0,x1,y1} normalized 0..1}
        self._annot_rects: list[dict] = []
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

    def set_page_pixmap(self, pixmap: QPixmap) -> None:
        self.setPixmap(pixmap)
        self.resize(pixmap.size())

    def set_annot_rects(self, rects: list[dict]) -> None:
        """Update the hit-test geometry for the current page's annotations."""
        self._annot_rects = rects or []

    def _hit_test(self, pos: QPoint) -> int | None:
        """Return the xref of the annotation under *pos*, or None."""
        pixmap = self.pixmap()
        if pixmap is None or pixmap.isNull():
            return None
        pw, ph = pixmap.width(), pixmap.height()
        off_x = max(0, (self.width() - pw) // 2)
        off_y = max(0, (self.height() - ph) // 2)
        px = pos.x() - off_x
        py = pos.y() - off_y
        for entry in self._annot_rects:
            rect = entry.get("rect", {})
            x0 = float(rect.get("x0", 0)) * pw
            y0 = float(rect.get("y0", 0)) * ph
            x1 = float(rect.get("x1", 0)) * pw
            y1 = float(rect.get("y1", 0)) * ph
            if x0 <= px <= x1 and y0 <= py <= y1:
                xref = entry.get("xref")
                if xref is not None:
                    return int(xref)
        return None

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        hit = self._hit_test(event.pos())
        if hit is not None:
            self.annotation_right_clicked.emit(hit)
            event.accept()
        else:
            super().contextMenuEvent(event)
