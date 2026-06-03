"""PDF text extraction with automatic scanned-PDF detection.

Strategy (interview answer):
- pdfplumber gives us layout-aware extraction: it preserves column order and can
  pull text from tables, which vanilla PyPDF2 mangles.
- After extracting each page we measure "text density" (chars per page-area unit).
  If the whole document is below the threshold it's almost certainly a scanned PDF
  with no embedded text layer, and we hand off to the OCR fallback.
- This two-stage approach handles the full spectrum: born-digital PDFs, hybrid docs
  (e.g. signature pages are scanned, body is text), and fully scanned contracts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Characters-per-page-area below which we treat the page as "no embedded text."
# Empirically: a typical contract page ~400 chars; scanned pages return <5.
_OCR_DENSITY_THRESHOLD = 20.0


@dataclass
class PageText:
    page_number: int  # 1-based
    text: str
    via_ocr: bool = False
    width: float = 0.0
    height: float = 0.0


@dataclass
class ParsedDocument:
    source_path: str
    pages: list[PageText] = field(default_factory=list)
    ocr_page_count: int = 0

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text.strip())

    @property
    def page_count(self) -> int:
        return len(self.pages)


def _density(text: str, width: float, height: float) -> float:
    area = max(width * height, 1.0)
    return len(text) / area * 1000  # chars per 1000 pt²


def parse_pdf(path: str | Path) -> ParsedDocument:
    """Extract text from a PDF, falling back to OCR for scanned pages.

    Raises FileNotFoundError if the file does not exist, ValueError for
    non-PDF files or password-protected documents.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected .pdf, got {path.suffix}")

    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError("pdfplumber not installed. Run: pip install pdfplumber") from exc

    doc = ParsedDocument(source_path=str(path))

    with pdfplumber.open(path) as pdf:
        if pdf.metadata.get("Encrypted"):
            raise ValueError("Password-protected PDFs are not supported.")

        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            w, h = page.width, page.height
            d = _density(text, w, h)

            if d < _OCR_DENSITY_THRESHOLD:
                logger.info("Page %d low density (%.1f) — attempting OCR.", i, d)
                ocr_text = _ocr_page(page, i)
                doc.pages.append(PageText(i, ocr_text, via_ocr=True, width=w, height=h))
                if ocr_text.strip():
                    doc.ocr_page_count += 1
            else:
                doc.pages.append(PageText(i, text, width=w, height=h))

    logger.info(
        "Parsed %s: %d pages, %d via OCR.",
        path.name,
        doc.page_count,
        doc.ocr_page_count,
    )
    return doc


def _ocr_page(page, page_number: int) -> str:
    """Rasterise a pdfplumber page and run tesseract OCR on it.

    Gracefully degrades: if pytesseract or Pillow isn't installed, or if the
    system `tesseract` binary is absent, we log a warning and return empty string
    so the rest of the document still processes.
    """
    try:
        import pytesseract  # optional dep — [ocr] extra
        from PIL import Image  # noqa: F401
    except ImportError:
        logger.warning(
            "Page %d: OCR deps not installed (pip install clauselens[ocr]). Skipping.",
            page_number,
        )
        return ""

    try:
        # pdfplumber can render a page to a PIL Image via its .to_image() helper.
        # Resolution 200 dpi is a good balance of accuracy vs. speed for A4 text.
        img = page.to_image(resolution=200).original
        text: str = pytesseract.image_to_string(img, lang="eng")
        return text
    except Exception as exc:
        logger.warning("Page %d OCR failed: %s", page_number, exc)
        return ""
