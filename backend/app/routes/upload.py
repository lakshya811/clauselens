"""PDF upload and ingestion route.

POST /upload accepts a PDF, runs parse → chunk, stores chunks in the app-level
document store (in-memory for now; swapped for the RAG vector store in step 4).
Returns a doc_id the frontend uses for all subsequent analysis and Q&A calls.
"""

from __future__ import annotations

import hashlib
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status

from app.config import get_settings
from app.ingestion.chunker import Chunk, chunk_document
from app.ingestion.pdf_parser import ParsedDocument, parse_pdf
from app.schemas.documents import UploadResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/upload", tags=["ingestion"])


def _doc_id(filename: str, content: bytes) -> str:
    """Stable, deterministic ID from filename + first 4KB of content."""
    digest = hashlib.sha256(filename.encode() + content[:4096]).hexdigest()[:16]
    return f"doc_{digest}"


def _build_page_map(parsed: ParsedDocument) -> dict[int, int]:
    """Map character offsets (in full_text) to 1-based page numbers."""
    page_map: dict[int, int] = {}
    offset = 0
    for page in parsed.pages:
        page_map[offset] = page.page_number
        offset += len(page.text) + 2  # +2 for the '\n\n' join
    return page_map


@router.post("", response_model=UploadResponse, status_code=status.HTTP_200_OK)
async def upload_pdf(request: Request, file: UploadFile = File(...)) -> UploadResponse:  # noqa: B008
    settings = get_settings()

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.max_upload_mb:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_mb:.1f} MB). Max: {settings.max_upload_mb} MB.",
        )
    if len(content) < 100:
        raise HTTPException(status_code=400, detail="File appears empty or corrupted.")

    doc_id = _doc_id(file.filename, content)

    # Write to temp file so pdfplumber can open it; clean up immediately after.
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        parsed: ParsedDocument = parse_pdf(tmp_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("PDF parse failed for %s", file.filename)
        raise HTTPException(status_code=500, detail=f"PDF parse error: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    page_map = _build_page_map(parsed)
    chunks: list[Chunk] = chunk_document(
        text=parsed.full_text,
        doc_id=doc_id,
        target_tokens=settings.chunk_target_tokens,
        overlap_tokens=settings.chunk_overlap_tokens,
        page_map=page_map,
    )

    # Store in app state for now; the RAG layer will replace this with a vector index.
    if not hasattr(request.app.state, "documents"):
        request.app.state.documents = {}
    request.app.state.documents[doc_id] = {
        "parsed": parsed,
        "chunks": chunks,
        "filename": file.filename,
    }

    logger.info(
        "Ingested %s → %s: %d pages, %d chunks, %d OCR pages.",
        file.filename, doc_id, parsed.page_count, len(chunks), parsed.ocr_page_count,
    )

    return UploadResponse(
        doc_id=doc_id,
        filename=file.filename,
        page_count=parsed.page_count,
        chunk_count=len(chunks),
        ocr_page_count=parsed.ocr_page_count,
    )
