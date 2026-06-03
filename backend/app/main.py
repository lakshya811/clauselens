"""FastAPI application entrypoint.

Routes are registered as the project grows (ingestion, summarize, risk,
compare, chat, metrics). For the scaffold we expose only health + version so
deployment and CI have something green to hit.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings
from app.observability.logger import init_logger
from app.observability.metrics import compute_metrics
from app.rag.store import get_vector_store
from app.routes import analyze, compare, qa, upload


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    init_logger(settings.log_dir)
    app.state.vector_store = get_vector_store(
        backend=settings.vector_backend,
        faiss_dir=settings.faiss_index_dir,
        database_url=settings.database_url,
    )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ClauseLens API",
        version=__version__,
        summary="Production AI contract analysis: RAG Q&A, clause extraction, "
        "risk flagging, version-diff classification.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(upload.router)
    app.include_router(qa.router)
    app.include_router(analyze.router)
    app.include_router(compare.router)

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        """Liveness probe used by HF Space / CI."""
        return {
            "status": "ok",
            "version": __version__,
            "env": settings.env,
            "llm_configured": settings.has_llm_credentials,
            "vector_backend": settings.vector_backend,
        }

    @app.get("/metrics", tags=["meta"])
    def metrics(window: int = 500) -> dict:
        """Aggregated request metrics over the last `window` log entries.

        Returns per-model latency percentiles (p50/p95), total cost, token
        counts, cost-per-query, and error rate. All computed from the JSONL
        observability log — no external metrics store required.
        """
        return compute_metrics(window=window)

    return app


app = create_app()
