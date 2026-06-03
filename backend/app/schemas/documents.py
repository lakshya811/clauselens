"""Shared Pydantic response models for document ingestion and retrieval."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    doc_id: str = Field(
        ..., description="Stable ID for this document (all subsequent calls use this)."
    )
    filename: str
    page_count: int
    chunk_count: int
    ocr_page_count: int = Field(0, description="Pages that required OCR fallback.")
    message: str = "Document ingested successfully."


class ChunkInfo(BaseModel):
    chunk_index: int
    clause_heading: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    token_estimate: int
    citation: str
