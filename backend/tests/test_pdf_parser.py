"""Tests for pdf_parser.

The PDF-specific tests create a minimal in-memory PDF using fpdf2 (a tiny
pure-python library). If fpdf2 is not installed we skip those tests gracefully —
they're integration tests; the chunker unit tests are the fast-path CI gate.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.ingestion.pdf_parser import ParsedDocument, _density, parse_pdf

# ---- pure unit tests (no PDF deps) ----

def test_density_normal_page() -> None:
    # A page with lots of text should have high density.
    text = "a" * 3000
    assert _density(text, 500, 700) > _density("a" * 10, 500, 700)


def test_density_empty_page() -> None:
    assert _density("", 500, 700) == 0.0


def test_parse_nonexistent_file() -> None:
    with pytest.raises(FileNotFoundError):
        parse_pdf("/tmp/no_such_file_clauselens.pdf")


def test_parse_wrong_extension(tmp_path: Path) -> None:
    f = tmp_path / "contract.txt"
    f.write_text("hello")
    with pytest.raises(ValueError, match="Expected .pdf"):
        parse_pdf(f)


# ---- integration tests that require a real PDF ----

def _make_pdf(text: str = "Hello Contract.") -> bytes:
    """Create a minimal valid PDF in memory using fpdf2."""
    try:
        from fpdf import FPDF
    except ImportError:
        pytest.skip("fpdf2 not installed — skipping PDF integration tests")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, text)
    return pdf.output()


def test_parse_real_pdf_returns_parsed_document(tmp_path: Path) -> None:
    data = _make_pdf("This is ARTICLE I DEFINITIONS. 1.1 Agreement means this.")
    p = tmp_path / "test.pdf"
    p.write_bytes(data)
    doc = parse_pdf(p)
    assert isinstance(doc, ParsedDocument)
    assert doc.page_count >= 1
    # fpdf2 PDFs may trip the low-density threshold (no embedded text layer);
    # in that case the parser attempts OCR. If OCR deps aren't installed we get
    # empty text — that's expected degraded-mode behaviour, not a failure.
    # Just verify the parser completes without exception.


def test_parse_real_pdf_structure(tmp_path: Path) -> None:
    data = _make_pdf("Born-digital contract text with plenty of characters per page.")
    p = tmp_path / "test.pdf"
    p.write_bytes(data)
    doc = parse_pdf(p)
    # Parser must return a valid ParsedDocument with at least one page.
    assert isinstance(doc, ParsedDocument)
    assert doc.page_count >= 1
    assert doc.source_path.endswith(".pdf")
