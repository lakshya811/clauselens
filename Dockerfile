# ── Build stage: compile the React SPA ────────────────────────────────────────
FROM node:20-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ .
RUN npm run build
# Build output is at /app/frontend/dist

# ── Runtime stage ──────────────────────────────────────────────────────────────
FROM python:3.11-slim

# ---- System deps -------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        ghostscript \
        poppler-utils \
        tesseract-ocr \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ---- Python deps -------------------------------------------------------
WORKDIR /app

# Copy source BEFORE pip install — editable install (-e .) needs the package
# source tree present at install time so setuptools can locate app/*.py
COPY pyproject.toml ./
COPY backend/ ./backend/

# sentence-transformers pulls PyTorch (~2 GB) — too large for free-tier builder.
# Cross-encoder reranker falls back gracefully when it is absent.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -e ".[ocr,pg]" \
 && pip install --no-cache-dir faiss-cpu==1.9.0.post1

# ---- Rest of application code ------------------------------------------
COPY evals/ ./evals/

# Copy the React build from the frontend stage
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

RUN useradd -m -u 1000 appuser && chown -R appuser /app /data
USER appuser

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", \
     "--app-dir", "backend", "--workers", "1"]
