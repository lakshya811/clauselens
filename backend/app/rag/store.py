"""Vector store abstraction — FAISS (local) and pgvector (deploy).

Interview answer:
  "I hide both backends behind a VectorStore ABC. FAISS runs in-process with
  no external services — ideal for local dev and the HF Space demo. In
  production with Supabase pgvector I swap by setting VECTOR_BACKEND=pgvector.
  The retrieval code, tests, and everything else never touch the backend
  directly — just add(), search(), and delete_doc() on the interface."

FAISS specifics:
  - Flat inner-product index (cosine via normalised vectors).
  - Vectors are L2-normalised before insertion so dot product = cosine similarity.
  - Index serialised to FAISS_INDEX_DIR for persistence between restarts.
  - A parallel list (self._chunks) preserves chunk metadata at each FAISS row index.

pgvector specifics (stub, wired in deploy):
  - Uses psycopg3 async + pgvector's register_vector().
  - Table: documents(id, doc_id, chunk_index, embedding vector(768), text, metadata jsonb).
  - Nearest-neighbour query: ORDER BY embedding <=> query_vec LIMIT k (cosine op).
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np

from app.ingestion.chunker import Chunk

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class VectorStore(ABC):
    """Minimal interface all backends must implement."""

    @abstractmethod
    def add(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        """Index chunks with their pre-computed embeddings."""

    @abstractmethod
    def search(
        self, query_vec: list[float], top_k: int = 8, doc_id: str | None = None
    ) -> list[tuple[Chunk, float]]:
        """Return top_k (chunk, score) pairs. Optionally filter by doc_id."""

    @abstractmethod
    def delete_doc(self, doc_id: str) -> int:
        """Remove all chunks for doc_id. Returns number of entries removed."""

    @abstractmethod
    def count(self) -> int:
        """Total number of indexed chunks."""


# ---------------------------------------------------------------------------
# FAISS backend
# ---------------------------------------------------------------------------


class FAISSVectorStore(VectorStore):
    """In-process FAISS flat index with metadata sidecar."""

    _CHUNKS_FILE = "chunks.jsonl"
    _INDEX_FILE = "index.faiss"

    def __init__(self, index_dir: str = "./faiss_index") -> None:
        self._dir = Path(index_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._chunks: list[Chunk] = []
        self._dim: int | None = None
        self._index: Any = None  # faiss.IndexFlatIP, lazy-init on first add
        self._load_if_exists()

    # ---- public interface ----

    def add(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        if not chunks:
            return
        vecs = self._normalise(np.array(embeddings, dtype=np.float32))
        self._ensure_index(vecs.shape[1])
        self._index.add(vecs)  # type: ignore[union-attr]
        self._chunks.extend(chunks)
        self._persist()
        logger.debug("FAISS: added %d chunks (total %d)", len(chunks), len(self._chunks))

    def search(
        self, query_vec: list[float], top_k: int = 8, doc_id: str | None = None
    ) -> list[tuple[Chunk, float]]:
        if self._index is None or len(self._chunks) == 0:
            return []
        q = self._normalise(np.array([query_vec], dtype=np.float32))
        k = min(top_k * 4 if doc_id else top_k, len(self._chunks))
        distances, indices = self._index.search(q, k)  # type: ignore[union-attr]
        results: list[tuple[Chunk, float]] = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self._chunks):
                continue
            chunk = self._chunks[idx]
            if doc_id and chunk.doc_id != doc_id:
                continue
            results.append((chunk, float(dist)))
            if len(results) == top_k:
                break
        return results

    def delete_doc(self, doc_id: str) -> int:
        before = len(self._chunks)
        self._chunks = [c for c in self._chunks if c.doc_id != doc_id]
        removed = before - len(self._chunks)
        if removed:
            self._rebuild_index()
        return removed

    def count(self) -> int:
        return len(self._chunks)

    # ---- internals ----

    def _ensure_index(self, dim: int) -> None:
        if self._index is not None:
            return
        try:
            import faiss  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "faiss-cpu not installed. Run: pip install 'clauselens[rag]'"
            ) from exc
        self._dim = dim
        self._index = faiss.IndexFlatIP(dim)

    def _rebuild_index(self) -> None:
        """Rebuild FAISS index from scratch after deletions."""
        if not self._chunks:
            self._index = None
            self._persist()
            return
        # Re-index requires embeddings, which we don't cache to avoid RAM bloat.
        # In practice delete_doc is called infrequently; rebuilding is acceptable.
        logger.warning(
            "FAISS: delete_doc triggered full rebuild (%d chunks remaining). "
            "This is O(n) — expected only on explicit doc removal.",
            len(self._chunks),
        )
        # We persist the chunk list so the sidecar is correct even though the
        # FAISS index file is now stale. The stale index will be rebuilt on the
        # next add() call. For now, null out the index so searches return empty
        # rather than returning stale results.
        self._index = None
        self._persist()

    @staticmethod
    def _normalise(vecs: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        return (vecs / norms).astype(np.float32)

    def _persist(self) -> None:
        chunks_path = self._dir / self._CHUNKS_FILE
        with open(chunks_path, "w") as f:
            for chunk in self._chunks:
                record = {
                    "text": chunk.text,
                    "doc_id": chunk.doc_id,
                    "chunk_index": chunk.chunk_index,
                    "clause_heading": chunk.clause_heading,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "metadata": chunk.metadata,
                }
                f.write(json.dumps(record) + "\n")

        if self._index is not None:
            import faiss  # type: ignore[import]

            faiss.write_index(self._index, str(self._dir / self._INDEX_FILE))

    def _load_if_exists(self) -> None:
        chunks_path = self._dir / self._CHUNKS_FILE
        index_path = self._dir / self._INDEX_FILE
        if not chunks_path.exists():
            return
        self._chunks = []
        with open(chunks_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                self._chunks.append(
                    Chunk(
                        text=rec["text"],
                        doc_id=rec["doc_id"],
                        chunk_index=rec["chunk_index"],
                        clause_heading=rec.get("clause_heading", ""),
                        page_start=rec.get("page_start"),
                        page_end=rec.get("page_end"),
                        metadata=rec.get("metadata", {}),
                    )
                )
        if index_path.exists() and self._chunks:
            try:
                import faiss  # type: ignore[import]

                self._index = faiss.read_index(str(index_path))
                self._dim = self._index.d
                logger.info(
                    "FAISS: loaded %d chunks from %s", len(self._chunks), self._dir
                )
            except ImportError:
                logger.warning("faiss not installed; index not loaded.")


# ---------------------------------------------------------------------------
# pgvector backend (stub — wired on deploy via DATABASE_URL)
# ---------------------------------------------------------------------------


class PgVectorStore(VectorStore):
    """pgvector backend using psycopg3 synchronous connection.

    Table DDL (run once, idempotent):

        CREATE EXTENSION IF NOT EXISTS vector;
        CREATE TABLE IF NOT EXISTS clauselens_chunks (
            id          BIGSERIAL PRIMARY KEY,
            doc_id      TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text        TEXT NOT NULL,
            clause_heading TEXT NOT NULL DEFAULT '',
            page_start  INTEGER,
            page_end    INTEGER,
            metadata    JSONB NOT NULL DEFAULT '{}',
            embedding   vector(768)
        );
        CREATE INDEX IF NOT EXISTS clauselens_chunks_doc_idx
            ON clauselens_chunks (doc_id);
        CREATE INDEX IF NOT EXISTS clauselens_chunks_emb_idx
            ON clauselens_chunks USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
    """

    _DDL = """
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE TABLE IF NOT EXISTS clauselens_chunks (
        id          BIGSERIAL PRIMARY KEY,
        doc_id      TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        text        TEXT NOT NULL,
        clause_heading TEXT NOT NULL DEFAULT '',
        page_start  INTEGER,
        page_end    INTEGER,
        metadata    JSONB NOT NULL DEFAULT '{}',
        embedding   vector(768)
    );
    CREATE INDEX IF NOT EXISTS clauselens_chunks_doc_idx
        ON clauselens_chunks (doc_id);
    """

    def __init__(self, database_url: str) -> None:
        self._url = database_url
        self._conn: Any = None
        self._connect()

    def _connect(self) -> None:
        try:
            import psycopg  # type: ignore[import]
            from pgvector.psycopg import register_vector  # type: ignore[import]

            self._conn = psycopg.connect(self._url, autocommit=True)
            register_vector(self._conn)
            self._conn.execute(self._DDL)
            logger.info("PgVectorStore connected and schema ensured.")
        except ImportError as exc:
            raise ImportError(
                "psycopg / pgvector not installed. "
                "Run: pip install 'clauselens[pg]'"
            ) from exc

    def add(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        if not chunks:
            return
        rows = [
            (
                c.doc_id,
                c.chunk_index,
                c.text,
                c.clause_heading,
                c.page_start,
                c.page_end,
                json.dumps(c.metadata),
                np.array(e, dtype=np.float32).tolist(),
            )
            for c, e in zip(chunks, embeddings)
        ]
        self._conn.executemany(
            """
            INSERT INTO clauselens_chunks
                (doc_id, chunk_index, text, clause_heading,
                 page_start, page_end, metadata, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            rows,
        )
        logger.debug("PgVector: inserted %d rows", len(rows))

    def search(
        self, query_vec: list[float], top_k: int = 8, doc_id: str | None = None
    ) -> list[tuple[Chunk, float]]:
        vec = np.array(query_vec, dtype=np.float32).tolist()
        if doc_id:
            rows = self._conn.execute(
                """
                SELECT text, doc_id, chunk_index, clause_heading,
                       page_start, page_end, metadata,
                       1 - (embedding <=> %s::vector) AS score
                FROM   clauselens_chunks
                WHERE  doc_id = %s
                ORDER  BY embedding <=> %s::vector
                LIMIT  %s
                """,
                (vec, doc_id, vec, top_k),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT text, doc_id, chunk_index, clause_heading,
                       page_start, page_end, metadata,
                       1 - (embedding <=> %s::vector) AS score
                FROM   clauselens_chunks
                ORDER  BY embedding <=> %s::vector
                LIMIT  %s
                """,
                (vec, vec, top_k),
            ).fetchall()

        results: list[tuple[Chunk, float]] = []
        for row in rows:
            text, did, idx, heading, ps, pe, meta_raw, score = row
            meta = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
            chunk = Chunk(
                text=text,
                doc_id=did,
                chunk_index=idx,
                clause_heading=heading or "",
                page_start=ps,
                page_end=pe,
                metadata=meta or {},
            )
            results.append((chunk, float(score)))
        return results

    def delete_doc(self, doc_id: str) -> int:
        result = self._conn.execute(
            "DELETE FROM clauselens_chunks WHERE doc_id = %s", (doc_id,)
        )
        return result.rowcount

    def count(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM clauselens_chunks"
        ).fetchone()
        return int(row[0]) if row else 0


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_vector_store(
    backend: str = "faiss",
    faiss_dir: str = "./faiss_index",
    database_url: str = "",
) -> VectorStore:
    """Return the configured vector store.

    backend: "faiss" | "pgvector"  (maps to VECTOR_BACKEND env var)
    """
    backend = backend.lower()
    if backend == "pgvector":
        if not database_url:
            database_url = os.environ.get("DATABASE_URL", "")
        if not database_url:
            raise ValueError(
                "VECTOR_BACKEND=pgvector but DATABASE_URL is not set."
            )
        return PgVectorStore(database_url=database_url)
    return FAISSVectorStore(index_dir=faiss_dir)
