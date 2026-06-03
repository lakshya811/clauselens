"""Hybrid retrieval: semantic (FAISS/pgvector) + BM25, fused with RRF.

Interview answer:
  "Semantic search alone misses exact legal terms — 'Section 12.3(b)' has no
  semantic neighbour. BM25 handles exact-match recall. I fuse the two ranked
  lists with Reciprocal Rank Fusion (RRF), score = Σ 1/(k+rank), where k=60
  is the standard constant that dampens high-rank outliers. RRF requires no
  score normalisation — the two rankers live in different score spaces — and
  empirically outperforms linear interpolation on BEIR benchmarks."

Pipeline:
  1. Embed query (Gemini text-embedding-004, RETRIEVAL_QUERY task type)
  2. Semantic top-(top_k*4) from VectorStore, filtered by doc_id
  3. BM25 top-(top_k*4) from in-memory index built from the doc's chunks
  4. RRF fusion → top top_k candidates
  5. Optional cross-encoder rerank → final top rerank_n results
"""

from __future__ import annotations

import logging

from app.ingestion.chunker import Chunk
from app.rag.store import VectorStore

logger = logging.getLogger(__name__)

_RRF_K = 60  # standard RRF dampening constant


# ---------------------------------------------------------------------------
# BM25 helpers (rank-bm25 is a core dep, always available)
# ---------------------------------------------------------------------------


def _build_bm25(chunks: list[Chunk]) -> object:
    from rank_bm25 import BM25Okapi  # type: ignore[import]

    tokenised = [c.text.lower().split() for c in chunks]
    return BM25Okapi(tokenised)


def _bm25_ranked(
    bm25: object, chunks: list[Chunk], query: str, top_k: int
) -> list[tuple[Chunk, float]]:
    tokens = query.lower().split()
    scores = bm25.get_scores(tokens)  # type: ignore[attr-defined]
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    results: list[tuple[Chunk, float]] = []
    for idx, score in ranked[:top_k]:
        results.append((chunks[idx], float(score)))
    return results


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------


def reciprocal_rank_fusion(
    *ranked_lists: list[tuple[Chunk, float]],
    k: int = _RRF_K,
    top_n: int = 10,
) -> list[tuple[Chunk, float]]:
    """Fuse multiple ranked lists into a single ranking using RRF.

    Args:
        *ranked_lists: Each list is [(chunk, score), ...] ordered best-first.
        k: RRF constant (60 is the literature default).
        top_n: Return at most this many results.

    Returns:
        Merged list [(chunk, rrf_score), ...], sorted best-first.
    """
    scores: dict[str, float] = {}
    chunks_by_key: dict[str, Chunk] = {}

    for ranked in ranked_lists:
        for rank, (chunk, _) in enumerate(ranked):
            key = f"{chunk.doc_id}:{chunk.chunk_index}"
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            chunks_by_key[key] = chunk

    merged = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [(chunks_by_key[key], score) for key, score in merged[:top_n]]


# ---------------------------------------------------------------------------
# Main retrieval function
# ---------------------------------------------------------------------------


def retrieve(
    query: str,
    doc_id: str,
    chunks: list[Chunk],
    vector_store: VectorStore,
    query_embedding: list[float],
    top_k: int = 8,
    rerank_n: int | None = None,
) -> list[tuple[Chunk, float]]:
    """Hybrid retrieve for a query against a single document.

    Args:
        query: User question.
        doc_id: Document to restrict retrieval to.
        chunks: All chunks for doc_id (needed for BM25 index).
        vector_store: Initialised VectorStore (FAISS or pgvector).
        query_embedding: Pre-computed query vector from embed_query().
        top_k: Number of results to return before optional reranking.
        rerank_n: If set, rerank the top_k results to this many. Requires
                  the [rag] optional dep (sentence-transformers).

    Returns:
        List of (chunk, score) sorted by relevance, length ≤ top_k.
    """
    fetch_n = top_k * 4  # over-fetch so fusion has more candidates

    # 1. Semantic search
    semantic_results = vector_store.search(
        query_vec=query_embedding, top_k=fetch_n, doc_id=doc_id
    )
    logger.debug("Semantic retrieval: %d candidates", len(semantic_results))

    # 2. BM25 keyword search
    if chunks:
        bm25 = _build_bm25(chunks)
        bm25_results = _bm25_ranked(bm25, chunks, query, top_k=fetch_n)
        logger.debug("BM25 retrieval: %d candidates", len(bm25_results))
    else:
        bm25_results = []

    # 3. RRF fusion
    fused = reciprocal_rank_fusion(semantic_results, bm25_results, top_n=top_k)
    logger.debug("After RRF fusion: %d candidates", len(fused))

    # 4. Optional cross-encoder rerank
    if rerank_n and rerank_n < len(fused):
        try:
            from app.rag.rerank import rerank as _rerank

            fused = _rerank(query, fused, top_n=rerank_n)
            logger.debug("After rerank: %d results", len(fused))
        except ImportError:
            logger.debug("Cross-encoder not available; skipping rerank.")
            fused = fused[:rerank_n]

    return fused
