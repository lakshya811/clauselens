# ── Build stage: compile the React SPA ────────────────────────────────────────
FROM node:20-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --prefer-offline

COPY frontend/ .
# VITE_API_URL left empty → app talks to the same origin (FastAPI serves both)
RUN npm run build          # outputs to ../backend/static/

# ── Runtime stage ──────────────────────────────────────────────────────────────
# python:3.11-slim is ~120 MB and matches the HF Space runtime.
# We avoid alpine: pdfplumber needs libgomp (from faiss-cpu) which musl won't find.
FROM python:3.11-slim

# ---- System deps -------------------------------------------------------
# ghostscript + poppler: pdfplumber needs them for page images / table extraction
# tesseract: OCR fallback for scanned contracts
# libgomp1: OpenMP runtime for faiss-cpu
RUN apt-get update && apt-get install -y --no-install-recommends \
        ghostscript \
        poppler-utils \
        tesseract-ocr \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ---- Python deps -------------------------------------------------------
WORKDIR /app
COPY pyproject.toml ./
# Install all extras (rag includes faiss-cpu + sentence-transformers)
# --no-build-isolation keeps the layer cacheable; setuptools is already present.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -e ".[rag,ocr,pg]"

# ---- Application code --------------------------------------------------
COPY backend/ ./backend/
COPY evals/   ./evals/

# Copy the pre-built React bundle from the build stage
COPY --from=frontend-build /app/backend/static ./backend/static

# ---- Runtime configuration --------------------------------------------
# HF Spaces runs as a non-root user on port 7860.
# The app reads these from env at startup; they can be overridden via Secrets.
ENV PORT=7860 \
    VECTOR_BACKEND=faiss \
    FAISS_INDEX_DIR=/data/index \
    LOG_DIR=/data/logs \
    ENV=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# /data is the HF Spaces persistent volume (survives restarts inside a session)
RUN mkdir -p /data/index /data/logs

# Drop privileges: HF Space user is 1000:1000
RUN useradd -m -u 1000 appuser && chown -R appuser /app /data
USER appuser

EXPOSE 7860

# uvicorn with a single worker; HF Spaces is single-replica anyway.
# --app-dir keeps the PYTHONPATH sane without an editable install path hack.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", \
     "--app-dir", "backend", "--workers", "1"]
