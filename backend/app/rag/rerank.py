"""Cross-encoder reranker (optional dep from [rag] extras).

Interview answer:
  "After BM25+vector hybrid retrieval I have a fused top-k list. A bi-encoder
  (the embedding model) computes query and document independently, so it can't
  model their interaction. A cross-encoder reads (query, document) jointly and
  produces a much better relevance score — at the cost of O(k) forward passes
  instead of one. Since I only rerank top_k=8→4, this is ≈8 passes on a 256M
  parameter MiniLM: <100ms on CPU, negligible at this scale. It's the classic
  retrieve-then-rerank pattern from the MS MARCO paper."

Model: cross-encoder/ms-marco-MiniLM-L-6-v2 (~66M params, fast on CPU)
Fallback: if sentence-transformers not installed, return input unchanged
          (scores become float(rank) so callers still work).
"""

from __future__ import annotations

import logging

from app.ingestion.chunker import Chunk

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_reranker_cache: object | None = None


def _get_reranker(model: str = _DEFAULT_MODEL) -> object:
    global _reranker_cache
    if _reranker_cache is not None:
        return _reranker_cache
    try:
        from sentence_transformers import CrossEncoder  # type: ignore[import]

        logger.info("Loading cross-encoder: %s", model)
        _reranker_cache = CrossEncoder(model, max_length=512)
        return _reranker_cache
    except ImportError as exc:
        raise ImportError(
            "sentence-transformers not installed. "
            "Run: pip install 'clauselens[rag]'"
        ) from exc


def rerank(
    query: str,
    candidates: list[tuple[Chunk, float]],
    top_n: int = 4,
    model: str = _DEFAULT_MODEL,
) -> list[tuple[Chunk, float]]:
    """Rerank candidate (chunk, score) pairs using a cross-encoder.

    Args:
        query: The user question.
        candidates: Output from retrieval — (chunk, score) sorted best-first.
        top_n: Return at most this many results.
        model: Cross-encoder model name.

    Returns:
        Reranked [(chunk, score), ...] sorted best-first.

    If sentence-transformers is not installed the function falls back to
    returning candidates[:top_n] with their original scores.
    """
    if not candidates:
        return []

    try:
        reranker = _get_reranker(model)
    except ImportError:
        logger.debug("Cross-encoder unavailable; returning first %d candidates.", top_n)
        return candidates[:top_n]

    pairs = [(query, c.text) for c, _ in candidates]
    scores = reranker.predict(pairs)  # type: ignore[attr-defined]

    ranked = sorted(
        zip(candidates, scores),
        key=lambda x: float(x[1]),
        reverse=True,
    )
    return [(chunk, float(score)) for (chunk, _orig), score in ranked[:top_n]]
