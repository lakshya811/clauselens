"""Demo endpoint — one-click sample contracts.

POST /demo/{sample_id} seeds a pre-built sample contract into app state and
returns an UploadResponse so the frontend can treat it exactly like an uploaded
document. No file upload required.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.data.samples import SAMPLES
from app.ingestion.chunker import chunk_document
from app.observability.logger import log_request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("", tags=["demo"])
def list_samples() -> list[dict]:
    """List available sample contracts for the demo buttons."""
    return [
        {"id": k, "label": v["label"], "description": v["description"]}
        for k, v in SAMPLES.items()
    ]


@router.post("/{sample_id}", status_code=status.HTTP_200_OK)
async def load_sample(sample_id: str, request: Request) -> dict:
    """Seed a sample contract into app state. Returns an UploadResponse-compatible dict."""
    if sample_id not in SAMPLES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sample '{sample_id}' not found. Available: {list(SAMPLES.keys())}",
        )

    sample = SAMPLES[sample_id]
    text = sample["text"]
    filename = sample["filename"]
    doc_id = f"demo_{sample_id}"

    # Build a minimal ParsedDocument-like object
    class _Parsed:
        full_text = text
        page_count = text.count("\n\n") // 3 + 1
        ocr_page_count = 0

    parsed = _Parsed()

    # Chunk the text
    chunks = chunk_document(
        full_text=text,
        doc_id=doc_id,
        filename=filename,
        page_count=parsed.page_count,
    )

    # Store in app state (same structure as /upload)
    if not hasattr(request.app.state, "documents"):
        request.app.state.documents = {}

    request.app.state.documents[doc_id] = {
        "chunks": chunks,
        "filename": filename,
        "parsed": parsed,
    }

    # Try to embed (non-fatal if no API key / no vector store)
    embedded = False
    try:
        settings = request.app.state.settings
        if settings.has_llm_credentials:
            from app.rag.embeddings import embed_texts

            texts = [c.text for c in chunks]
            embeddings = embed_texts(texts, api_key=settings.google_api_key)
            vs = request.app.state.vector_store
            vs.add(chunks, embeddings)
            embedded = True
    except Exception:
        logger.info("Sample embedding skipped (no key or store error); BM25-only mode.")

    log_request(route="/demo", model="none", doc_id=doc_id)

    return {
        "doc_id": doc_id,
        "filename": filename,
        "page_count": parsed.page_count,
        "chunk_count": len(chunks),
        "ocr_page_count": 0,
        "embedded": embedded,
    }
