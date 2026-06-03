"""Unit tests for the clause-aware chunker.

These run without any LLM key or PDF — pure text in, Chunk list out.
They verify the three properties that matter for RAG quality:
  1. No content is lost (all text covered).
  2. Target token size is respected (modulo single paragraphs > target).
  3. Clause headings are attached to the right chunks.
"""

from __future__ import annotations

from app.ingestion.chunker import Chunk, _approx_tokens, chunk_document

_MINI_CONTRACT = """\
ARTICLE I DEFINITIONS

1.1 "Agreement" means this Software License Agreement.
1.2 "Licensor" means Acme Corp, a Delaware corporation.
1.3 "Licensee" means the entity identified in the Order Form.

ARTICLE II LICENSE GRANT

2.1 Subject to the terms hereof, Licensor grants Licensee a non-exclusive,
non-transferable license to use the Software solely for Licensee's internal
business purposes.

2.2 Licensee shall not sublicense, sell, resell, transfer, assign, or otherwise
dispose of, nor allow access to the Software to any third party.

ARTICLE III PAYMENT

3.1 Licensee shall pay the fees set forth in the Order Form within thirty (30)
days of the invoice date.

3.2 All fees are non-refundable except as expressly set forth herein.
"""


def test_chunk_document_returns_chunks() -> None:
    chunks = chunk_document(_MINI_CONTRACT, doc_id="test_doc", target_tokens=200)
    assert len(chunks) >= 1
    assert all(isinstance(c, Chunk) for c in chunks)


def test_no_content_lost() -> None:
    chunks = chunk_document(_MINI_CONTRACT, doc_id="test_doc", target_tokens=200)
    recovered = " ".join(c.text for c in chunks)
    # Every meaningful word in the original should appear in the chunks.
    for keyword in ["non-exclusive", "non-refundable", "Order Form", "Delaware"]:
        assert keyword in recovered, f"keyword {keyword!r} not found in chunks"


def test_heading_attached_to_chunk() -> None:
    chunks = chunk_document(_MINI_CONTRACT, doc_id="test_doc", target_tokens=200)
    headings = [c.clause_heading for c in chunks]
    # At least one chunk should carry a heading with recognisable text.
    assert any("ARTICLE" in h or "." in h for h in headings)


def test_chunk_indices_are_sequential() -> None:
    chunks = chunk_document(_MINI_CONTRACT, doc_id="test_doc", target_tokens=200)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_target_token_size_respected() -> None:
    target = 150
    chunks = chunk_document(_MINI_CONTRACT, doc_id="test_doc", target_tokens=target)
    oversized = [c for c in chunks if _approx_tokens(c.text) > target * 2]
    sizes = [_approx_tokens(c.text) for c in oversized]
    assert oversized == [], f"Chunks grossly over target: {sizes}"


def test_approx_tokens_never_zero() -> None:
    assert _approx_tokens("x") == 1
    assert _approx_tokens("") == 1
    assert _approx_tokens("hello world") > 1


def test_chunk_citation_format() -> None:
    chunks = chunk_document(_MINI_CONTRACT, doc_id="test_doc", target_tokens=200)
    for c in chunks:
        # citation must be a non-empty string.
        assert isinstance(c.citation, str)
        assert len(c.citation) > 0


def test_short_document_yields_at_least_one_chunk() -> None:
    chunks = chunk_document("This is a short contract.", doc_id="tiny")
    assert len(chunks) >= 1


def test_empty_document_yields_no_chunks() -> None:
    chunks = chunk_document("", doc_id="empty")
    assert len(chunks) == 0
