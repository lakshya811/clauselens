"""Embedding layer using Gemini text-embedding-004.

Interview answer:
  "I use Gemini's text-embedding-004 model (768-dim). For ingestion I batch
  chunks into groups of 100 to stay under the API's per-request limit. At query
  time I embed the single user question with task_type=RETRIEVAL_QUERY while
  chunks are embedded with RETRIEVAL_DOCUMENT — the asymmetric task types are
  documented in the Gemini embedding guide and give measurably better recall
  for RAG retrieval."
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_EMBED_MODEL = "models/text-embedding-004"
_BATCH_SIZE = 100  # Gemini's batch limit per embedContent request


def _get_client(api_key: str) -> object:
    try:
        from google import genai  # type: ignore[import]

        return genai.Client(api_key=api_key)
    except ImportError as exc:
        raise ImportError(
            "google-genai not installed. Run: pip install google-genai"
        ) from exc


def embed_texts(
    texts: list[str],
    api_key: str,
    task_type: str = "RETRIEVAL_DOCUMENT",
    model: str = _EMBED_MODEL,
) -> list[list[float]]:
    """Embed a list of texts, batching to respect API limits.

    Args:
        texts: Strings to embed.
        api_key: Gemini API key.
        task_type: One of RETRIEVAL_DOCUMENT | RETRIEVAL_QUERY | SEMANTIC_SIMILARITY.
        model: Embedding model name.

    Returns:
        List of float vectors, same length as texts.
    """
    if not texts:
        return []

    client = _get_client(api_key)
    results: list[list[float]] = []

    for batch_start in range(0, len(texts), _BATCH_SIZE):
        batch = texts[batch_start : batch_start + _BATCH_SIZE]
        try:
            from google.genai import types as genai_types  # type: ignore[import]

            response = client.models.embed_content(  # type: ignore[attr-defined]
                model=model,
                contents=batch,
                config=genai_types.EmbedContentConfig(task_type=task_type),
            )
            for emb in response.embeddings:
                results.append(list(emb.values))
        except Exception:
            logger.exception(
                "Embedding batch %d-%d failed",
                batch_start,
                batch_start + len(batch),
            )
            raise

    return results


def embed_query(query: str, api_key: str, model: str = _EMBED_MODEL) -> list[float]:
    """Embed a single retrieval query (uses RETRIEVAL_QUERY task type)."""
    vecs = embed_texts([query], api_key, task_type="RETRIEVAL_QUERY", model=model)
    return vecs[0]
