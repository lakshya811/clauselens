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
from app.routes import upload


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: validate config early so misconfiguration fails before serving traffic.
    settings = get_settings()
    app.state.settings = settings
    yield
    # Shutdown: nothing to tear down yet (vector store / clients added later).


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

    return app


app = create_app()
