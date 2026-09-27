"""Reading recipes out of PDFs.

PDFs saved from a browser or recipe app carry a real text layer, which we read
with its positions (so two-column layouts come out in the right order). Scanned
PDFs have no text layer; those pages are rendered and run through OCR.
"""

import pypdfium2 as pdfium

from .draft import ImportFailed
from .layout import Line, TextBox, boxes_to_lines
from .ocr import ocr_image

MAX_PAGES = 30
# Pages with less text than this are treated as scans.
_MIN_TEXT_CHARS = 25
_OCR_RENDER_SCALE = 3  # 72 dpi * 3 = 216 dpi


def open_pdf(data: bytes, name: str = "PDF") -> pdfium.PdfDocument:
    try:
        return pdfium.PdfDocument(data)
    except pdfium.PdfiumError:
        raise ImportFailed(f"{name} couldn't be opened. It may be damaged or password-protected.")


def _text_boxes(page: pdfium.PdfPage) -> list[TextBox]:
    textpage = page.get_textpage()
    try:
        _, page_height = page.get_size()
        boxes = []
        for index in range(textpage.count_rects()):
            left, bottom, right, top = textpage.get_rect(index)
            text = textpage.get_text_bounded(left, bottom, right, top)
            if text and text.strip():
                boxes.append(
                    TextBox(
                        text=" ".join(text.split()),
                        x0=left,
                        y0=page_height - top,
                        x1=right,
                        y1=page_height - bottom,
                    )
                )
        return boxes
    finally:
        textpage.close()


def pdf_to_lines(data: bytes, name: str = "PDF") -> tuple[list[Line], int]:
    """Return (lines in reading order, number of pages that needed OCR)."""
    pdf = open_pdf(data, name)
    try:
        if len(pdf) > MAX_PAGES:
            raise ImportFailed(
                f"{name} has {len(pdf)} pages. Import a PDF of a single recipe "
                f"(up to {MAX_PAGES} pages)."
            )
        lines: list[Line] = []
        ocr_pages = 0
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                boxes = _text_boxes(page)
                if sum(len(b.text) for b in boxes) < _MIN_TEXT_CHARS:
                    bitmap = page.render(scale=_OCR_RENDER_SCALE)
                    boxes = ocr_image(bitmap.to_pil())
                    ocr_pages += 1
                lines.extend(boxes_to_lines(boxes))
            finally:
                page.close()
        return lines, ocr_pages
    finally:
        pdf.close()


def page_count(data: bytes) -> int:
    pdf = open_pdf(data)
    try:
        return len(pdf)
    finally:
        pdf.close()
