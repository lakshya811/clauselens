# ── Build stage: compile the React SPA ────────────────────────────────────────
FROM node:20-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package*.json ./
# No --prefer-offline: no npm cache exists in a fresh build layer
RUN npm ci

COPY frontend/ .
# Builds to /app/frontend/dist
RUN npm run build

# ── Runtime stage ──────────────────────────────────────────────────────────────
# python:3.11-slim is ~120 MB and matches the HF Space runtime.
FROM python:3.11-slim

# ---- System deps -------------------------------------------------------
# ghostscript + poppler: pdfplumber page images / table extraction
# tesseract: OCR fallback for scanned contracts
# libgomp1: OpenMP runtime required by faiss-cpu
RUN apt-get update && apt-get install -y --no-install-recommends \
        ghostscript \
        poppler-utils \
        tesseract-ocr \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ---- Python deps -------------------------------------------------------
WORKDIR /app
COPY pyproject.toml ./
# sentence-transformers pulls PyTorch (~2 GB) — too large for free-tier builder.
# Cross-encoder reranker falls back gracefully when it is absent.
# Install faiss-cpu directly; include ocr + pg extras for full feature parity.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -e ".[ocr,pg]" \
 && pip install --no-cache-dir faiss-cpu==1.9.0.post1

# ---- Application code --------------------------------------------------
COPY backend/ ./backend/
COPY evals/   ./evals/

# Copy the React build from the frontend stage into FastAPI's static dir
RUN mkdir -p ./backend/static
COPY --from=frontend-build /app/frontend/dist/ ./backend/static/

# ---- Runtime configuration --------------------------------------------
ENV PORT=7860 \
    VECTOR_BACKEND=faiss \
    FAISS_INDEX_DIR=/data/index \
    LOG_DIR=/data/logs \
    ENV=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN mkdir -p /data/index /data/logs

# Drop privileges — HF Space user is 1000:1000
RUN useradd -m -u 1000 appuser && chown -R appuser /app /data
USER appuser

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", \
     "--app-dir", "backend", "--workers", "1"]
