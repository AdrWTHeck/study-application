"""PDF-native annotation CRUD via PyMuPDF.

All highlights, underlines, strikethroughs, and sticky notes are written
directly into the working copy PDF as standard PDF annotation objects.
No SQLAlchemy — pure file operations. The working copy is saved incrementally
so writes are fast and prior history is preserved in the PDF structure.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import fitz  # PyMuPDF


# Annotation type codes mirrored from fitz constants for clarity.
ANNOT_HIGHLIGHT  = 8   # fitz.PDF_ANNOT_HIGHLIGHT
ANNOT_TEXT       = 0   # fitz.PDF_ANNOT_TEXT  (sticky note)
ANNOT_UNDERLINE  = 9   # fitz.PDF_ANNOT_UNDERLINE
ANNOT_STRIKEOUT  = 11  # fitz.PDF_ANNOT_STRIKEOUT

TYPE_NAMES = {
    ANNOT_HIGHLIGHT: "Highlight",
    ANNOT_TEXT:      "Note",
    ANNOT_UNDERLINE: "Underline",
    ANNOT_STRIKEOUT: "Strikeout",
}


@dataclass
class AnnotationInfo:
    xref:      int
    page:      int        # 0-based page index
    type_code: int        # one of ANNOT_* constants above
    type_name: str        # human-readable label
    color_hex: str        # "#rrggbb"
    subject:   str        # highlighted / underlined source text
    content:   str        # user comment / note body
    rect:      dict = field(default_factory=dict)  # normalized {x0,y0,x1,y1} 0..1


class AnnotationService:
    """Static methods for reading and writing PDF annotations."""

    # ------------------------------------------------------------------ read

    @staticmethod
    def get_all_annotations(pdf_path: str) -> list[AnnotationInfo]:
        """Return every annotation across all pages, ordered by (page, y)."""
        result: list[AnnotationInfo] = []
        try:
            with fitz.open(pdf_path) as doc:
                for page_idx in range(doc.page_count):
                    page = doc[page_idx]
                    result.extend(
                        AnnotationService._read_page_annots(page, page_idx)
                    )
        except Exception:  # noqa: BLE001
            pass
        return result

    @staticmethod
    def get_page_annotations(pdf_path: str, page_index: int) -> list[AnnotationInfo]:
        """Return annotations for a single page (0-based index)."""
        try:
            with fitz.open(pdf_path) as doc:
                if page_index < 0 or page_index >= doc.page_count:
                    return []
                return AnnotationService._read_page_annots(doc[page_index], page_index)
        except Exception:  # noqa: BLE001
            return []

    # ----------------------------------------------------------------- write

    @staticmethod
    def add_highlight(pdf_path: str, page_index: int, quads: list,
                      color_hex: str, subject: str = "") -> int:
        """Add a highlight annotation. Returns the annotation xref."""
        return AnnotationService._add_markup(
            pdf_path, page_index, quads, color_hex, subject, ANNOT_HIGHLIGHT
        )

    @staticmethod
    def add_underline(pdf_path: str, page_index: int, quads: list,
                      color_hex: str, subject: str = "") -> int:
        return AnnotationService._add_markup(
            pdf_path, page_index, quads, color_hex, subject, ANNOT_UNDERLINE
        )

    @staticmethod
    def add_strikeout(pdf_path: str, page_index: int, quads: list,
                      color_hex: str, subject: str = "") -> int:
        return AnnotationService._add_markup(
            pdf_path, page_index, quads, color_hex, subject, ANNOT_STRIKEOUT
        )

    @staticmethod
    def add_text_note(pdf_path: str, page_index: int, norm_x: float,
                      norm_y: float, content: str, color_hex: str) -> int:
        """Add a sticky-note annotation at a normalized page position. Returns xref."""
        try:
            doc = fitz.open(pdf_path)
            page = doc[page_index]
            pw, ph = page.rect.width, page.rect.height
            point = fitz.Point(norm_x * pw, norm_y * ph)
            annot = page.add_text_annot(point, content)
            annot.set_colors(stroke=AnnotationService._hex_to_rgb(color_hex))
            annot.update()
            xref = annot.xref
            AnnotationService._save(doc, pdf_path)
            doc.close()
            return xref
        except Exception:  # noqa: BLE001
            try:
                doc.close()
            except Exception:  # noqa: BLE001
                pass
            return -1

    @staticmethod
    def update_comment(pdf_path: str, page_index: int, xref: int, content: str) -> None:
        """Replace the user comment on an existing annotation."""
        try:
            doc = fitz.open(pdf_path)
            page = doc[page_index]
            for annot in page.annots():
                if annot.xref == xref:
                    info = annot.info
                    info["content"] = content
                    annot.set_info(info)
                    annot.update()
                    break
            AnnotationService._save(doc, pdf_path)
            doc.close()
        except Exception:  # noqa: BLE001
            try:
                doc.close()
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def delete_annotation(pdf_path: str, page_index: int, xref: int) -> None:
        """Delete an annotation by xref."""
        try:
            doc = fitz.open(pdf_path)
            page = doc[page_index]
            for annot in page.annots():
                if annot.xref == xref:
                    page.delete_annot(annot)
                    break
            AnnotationService._save(doc, pdf_path)
            doc.close()
        except Exception:  # noqa: BLE001
            try:
                doc.close()
            except Exception:  # noqa: BLE001
                pass

    # --------------------------------------------------------------- helpers

    @staticmethod
    def _add_markup(pdf_path: str, page_index: int, quads: list,
                    color_hex: str, subject: str, annot_type: int) -> int:
        try:
            doc = fitz.open(pdf_path)
            page = doc[page_index]
            rgb = AnnotationService._hex_to_rgb(color_hex)
            if annot_type == ANNOT_HIGHLIGHT:
                annot = page.add_highlight_annot(quads)
            elif annot_type == ANNOT_UNDERLINE:
                annot = page.add_underline_annot(quads)
            else:
                annot = page.add_strikeout_annot(quads)
            annot.set_colors(stroke=rgb)
            annot.set_info(subject=subject, content="")
            annot.update()
            xref = annot.xref
            AnnotationService._save(doc, pdf_path)
            doc.close()
            return xref
        except Exception:  # noqa: BLE001
            try:
                doc.close()
            except Exception:  # noqa: BLE001
                pass
            return -1

    @staticmethod
    def _read_page_annots(page: fitz.Page, page_idx: int) -> list[AnnotationInfo]:
        items: list[AnnotationInfo] = []
        pw, ph = page.rect.width, page.rect.height
        if pw <= 0 or ph <= 0:
            return items
        for annot in page.annots():
            type_code = annot.type[0]
            if type_code not in TYPE_NAMES:
                continue
            info = annot.info
            colors = annot.colors
            stroke = colors.get("stroke") or (1.0, 0.83, 0.29)
            color_hex = AnnotationService._rgb_to_hex(stroke)
            rect = annot.rect
            norm = {
                "x0": rect.x0 / pw, "y0": rect.y0 / ph,
                "x1": rect.x1 / pw, "y1": rect.y1 / ph,
            }
            items.append(AnnotationInfo(
                xref=annot.xref,
                page=page_idx,
                type_code=type_code,
                type_name=TYPE_NAMES[type_code],
                color_hex=color_hex,
                subject=info.get("subject", ""),
                content=info.get("content", ""),
                rect=norm,
            ))
        return items

    @staticmethod
    def _save(doc: fitz.Document, pdf_path: str) -> None:
        doc.save(pdf_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple:
        h = hex_color.lstrip("#")
        if len(h) != 6:
            return (1.0, 0.83, 0.29)
        return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]

    @staticmethod
    def _rgb_to_hex(rgb: tuple) -> str:
        r, g, b = rgb if len(rgb) >= 3 else (1.0, 0.83, 0.29)
        return "#{:02x}{:02x}{:02x}".format(
            int((r or 0) * 255), int((g or 0) * 255), int((b or 0) * 255)
        )
