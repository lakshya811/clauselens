"""Tests for the RAG layer — no API calls, no real embeddings.

Strategy:
  - VectorStore: tested with FAISSVectorStore using random numpy vectors
    (faiss-cpu is an optional dep; tests skip gracefully if absent).
  - RRF: pure-logic, no deps beyond stdlib.
  - BM25 retrieval: requires rank-bm25 (core dep, always present).
  - Reranker fallback: no sentence-transformers installed in CI → tests the
    graceful-degradation path only.
"""

from __future__ import annotations

import math

import pytest
from app.ingestion.chunker import Chunk
from app.rag.retrieve import _bm25_ranked, _build_bm25, reciprocal_rank_fusion

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(
    text: str,
    doc_id: str = "doc_test",
    chunk_index: int = 0,
    clause_heading: str = "",
) -> Chunk:
    return Chunk(
        text=text,
        doc_id=doc_id,
        chunk_index=chunk_index,
        clause_heading=clause_heading,
    )


def _ranked(chunks: list[Chunk]) -> list[tuple[Chunk, float]]:
    """Fake ranked list with descending scores."""
    return [(c, float(len(chunks) - i)) for i, c in enumerate(chunks)]


# ---------------------------------------------------------------------------
# RRF tests (pure logic)
# ---------------------------------------------------------------------------


def test_rrf_single_list_preserves_order() -> None:
    chunks = [_make_chunk(f"text {i}", chunk_index=i) for i in range(5)]
    result = reciprocal_rank_fusion(_ranked(chunks), top_n=5)
    assert [c.chunk_index for c, _ in result] == [0, 1, 2, 3, 4]


def test_rrf_scores_are_positive() -> None:
    chunks = [_make_chunk(f"c{i}", chunk_index=i) for i in range(3)]
    result = reciprocal_rank_fusion(_ranked(chunks))
    assert all(score > 0 for _, score in result)


def test_rrf_merges_two_disjoint_lists() -> None:
    a_chunks = [_make_chunk("a", doc_id="d", chunk_index=0)]
    b_chunks = [_make_chunk("b", doc_id="d", chunk_index=1)]
    result = reciprocal_rank_fusion(_ranked(a_chunks), _ranked(b_chunks))
    assert len(result) == 2


def test_rrf_boosts_overlap() -> None:
    """A chunk ranked 1st in both lists should beat one ranked 1st in only one."""
    shared = _make_chunk("shared", chunk_index=0)
    unique_a = _make_chunk("only_a", chunk_index=1)
    unique_b = _make_chunk("only_b", chunk_index=2)

    list_a: list[tuple[Chunk, float]] = [(shared, 2.0), (unique_a, 1.0)]
    list_b: list[tuple[Chunk, float]] = [(shared, 2.0), (unique_b, 1.0)]

    result = reciprocal_rank_fusion(list_a, list_b, top_n=3)
    top_chunk = result[0][0]
    assert top_chunk.chunk_index == 0  # shared should be on top


def test_rrf_top_n_respected() -> None:
    chunks = [_make_chunk(f"c{i}", chunk_index=i) for i in range(10)]
    result = reciprocal_rank_fusion(_ranked(chunks), top_n=3)
    assert len(result) == 3


def test_rrf_empty_inputs_return_empty() -> None:
    result = reciprocal_rank_fusion([], [])
    assert result == []


def test_rrf_score_formula() -> None:
    """Verify the 1/(k+rank+1) formula by hand for a single item at rank 0."""
    c = _make_chunk("x", chunk_index=0)
    result = reciprocal_rank_fusion([(c, 99.0)], k=60, top_n=1)
    expected = 1.0 / (60 + 0 + 1)
    assert math.isclose(result[0][1], expected, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# BM25 tests
# ---------------------------------------------------------------------------


def test_bm25_returns_matching_chunk_first() -> None:
    chunks = [
        _make_chunk("payment due on the first of each month", chunk_index=0),
        _make_chunk("termination requires thirty days notice", chunk_index=1),
        _make_chunk("liability shall not exceed contract value", chunk_index=2),
    ]
    bm25 = _build_bm25(chunks)
    results = _bm25_ranked(bm25, chunks, query="payment", top_k=3)
    top_chunk, top_score = results[0]
    assert top_chunk.chunk_index == 0
    assert top_score > 0


def test_bm25_top_k_limits_results() -> None:
    chunks = [_make_chunk(f"text {i}", chunk_index=i) for i in range(10)]
    bm25 = _build_bm25(chunks)
    results = _bm25_ranked(bm25, chunks, query="text", top_k=3)
    assert len(results) == 3


def test_bm25_absent_term_scores_zero() -> None:
    chunks = [
        _make_chunk("payment terms section", chunk_index=0),
        _make_chunk("governing law clause", chunk_index=1),
    ]
    bm25 = _build_bm25(chunks)
    results = _bm25_ranked(bm25, chunks, query="xxxxnotaword", top_k=2)
    assert all(score == 0.0 for _, score in results)


# ---------------------------------------------------------------------------
# FAISS store tests (skipped if faiss not installed)
# ---------------------------------------------------------------------------

def _faiss_importable() -> bool:
    try:
        import faiss  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(
    not _faiss_importable(),
    reason="faiss-cpu not installed",
)
class TestFAISSStore:
    def setup_method(self) -> None:
        import tempfile
        self._tmpdir = tempfile.mkdtemp()

    def _store(self) -> object:
        from app.rag.store import FAISSVectorStore
        return FAISSVectorStore(index_dir=self._tmpdir)

    def test_add_and_count(self) -> None:
        import numpy as np
        store = self._store()
        chunks = [_make_chunk(f"c{i}", chunk_index=i) for i in range(5)]
        vecs = np.random.rand(5, 768).tolist()
        store.add(chunks, vecs)
        assert store.count() == 5

    def test_search_returns_results(self) -> None:
        import numpy as np
        store = self._store()
        chunks = [_make_chunk(f"chunk {i}", chunk_index=i) for i in range(10)]
        vecs = np.random.rand(10, 768).tolist()
        store.add(chunks, vecs)
        q = np.random.rand(768).tolist()
        results = store.search(q, top_k=3)
        assert len(results) == 3
        assert all(isinstance(c, Chunk) for c, _ in results)

    def test_search_filters_by_doc_id(self) -> None:
        import numpy as np
        store = self._store()
        chunks_a = [_make_chunk("a", doc_id="doc_a", chunk_index=0)]
        chunks_b = [_make_chunk("b", doc_id="doc_b", chunk_index=0)]
        vecs_a = np.random.rand(1, 768).tolist()
        vecs_b = np.random.rand(1, 768).tolist()
        store.add(chunks_a, vecs_a)
        store.add(chunks_b, vecs_b)
        results = store.search(np.random.rand(768).tolist(), top_k=5, doc_id="doc_a")
        assert all(c.doc_id == "doc_a" for c, _ in results)

    def test_delete_doc_removes_chunks(self) -> None:
        import numpy as np
        store = self._store()
        chunks = [_make_chunk(f"c{i}", doc_id="doc_del", chunk_index=i) for i in range(3)]
        vecs = np.random.rand(3, 768).tolist()
        store.add(chunks, vecs)
        removed = store.delete_doc("doc_del")
        assert removed == 3
        assert store.count() == 0


# ---------------------------------------------------------------------------
# Reranker fallback test (no sentence-transformers needed)
# ---------------------------------------------------------------------------


def test_rerank_fallback_without_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    """When sentence-transformers is absent, rerank() returns first top_n unchanged."""
    import sys

    # Temporarily hide sentence_transformers
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)  # type: ignore[arg-type]


    import app.rag.rerank as rerank_mod

    # Reset cache so the import path is re-exercised.
    rerank_mod._reranker_cache = None

    chunks = [_make_chunk(f"c{i}", chunk_index=i) for i in range(5)]
    candidates: list[tuple[Chunk, float]] = _ranked(chunks)
    result = rerank_mod.rerank("test query", candidates, top_n=3)
    assert len(result) == 3
    # Fallback should return the first 3 in original order
    assert result[0][0].chunk_index == 0
