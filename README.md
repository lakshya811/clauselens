---
title: ClauseLens
emoji: ⚖️
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
short_description: AI contract analysis — RAG Q&A, risk flags, diff
pinned: false
---

# ClauseLens

**Production-grade AI contract analysis.** Upload a PDF → get structured clause extraction, auto risk-flagging, version-diff classification, and citation-grounded Q&A — all in a dark-themed web app backed by a fully observable RAG pipeline.

**[Live demo →](https://lakshya1111-clauselens.hf.space)** · Hugging Face Space (Docker, free tier) · Try the NDA / SaaS / Employment samples without uploading anything.

![ClauseLens demo](https://huggingface.co/spaces/lakshya1111/clauselens/resolve/main/docs/demo.gif)

---

## What it does

Upload a contract and immediately get:

- **Clause extraction** — parties, dates, governing law, payment schedule, liability cap, termination terms — structured JSON, not free text
- **Risk flags** — uncapped liability, auto-renewal traps, broad IP assignment, weak confidentiality, missing dispute resolution — each with severity level, clause reference, and a concrete negotiation recommendation
- **Version compare** — diff two uploaded contracts; every change classified as **Structural** (clause added/removed), **Semantic** (meaning changed), or **Surface** (wording/formatting only)
- **Grounded Q&A** — hybrid RAG answers with clickable citations that expand to show the exact source clause; every claim is traceable
- **Observability** — live metrics badge: request count, p50 latency, cost-per-query

---

## Architecture

```text
Browser (React + Tailwind)
  Upload | Analysis | Q&A Chat | Compare | Evals
       │
       │ REST — same origin in prod, Vite proxy in dev
       ▼
FastAPI (uvicorn)
  ├── POST /upload      PDF parse → OCR fallback → clause chunker → FAISS embed
  ├── POST /ask         embed query → BM25 + vector → RRF → rerank → cite → LLM
  ├── POST /analyze/:id extract_clauses (cheap model) + flag_risks (strong model)
  ├── POST /compare     compare_contracts (strong model) → Structural/Semantic/Surface
  ├── POST /demo/:id    seed public sample contract without file upload
  └── GET  /metrics     p50/p95 latency · cost/query · error rate from JSONL log
       │
       ├── Gemini API  (text-embedding-004, flash-lite, flash)
       └── FAISS       (local) / pgvector (deploy)
```

The whole stack ships as **one Docker image**: `vite build` outputs to `backend/static/`; FastAPI serves both the SPA and the API on port 7860.

---

## Engineering decisions

### Why hybrid retrieval instead of pure vector search?

Legal contracts contain exact-match terms — `Section 7.2`, `indemnify`, `force majeure` — that embeddings generalise away. BM25 catches keyword matches; semantic search catches paraphrase ("terminate at will" ↔ "terminate for convenience"). Reciprocal Rank Fusion (k=60) merges both ranked lists without a tunable weight. A cross-encoder reranker scores the top shortlist as (query, passage) pairs — more accurate but applied only to ~20 candidates, not the full index.

Tradeoff: +80–150 ms vs pure vector. Acceptable for document-level Q&A; would not be for autocomplete.

### Why Gemini JSON mode for structured outputs?

`ClauseBundle`, `RiskReport`, and `CompareResult` are Pydantic models used as both the Gemini `response_schema` (forces JSON output) and the FastAPI response model. One schema definition validates on receipt, documents the API, and drives the frontend types — no manual sync. On parse failure, `complete_json()` retries twice then degrades gracefully (error in `confidence_note` / `summary`) rather than returning 500.

### Model routing — cheap vs strong

| Task | Model | Reason |
| --- | --- | --- |
| Clause extraction | flash-lite | Fill-in-the-blanks, no reasoning |
| Simple Q&A | flash-lite | Short factual query heuristic |
| Complex Q&A | flash | Length > 200 chars or reasoning keyword |
| Risk flagging | flash | Legal inference required |
| Version compare | flash | Multi-step: locate + classify + explain |
| LLM-as-Judge | flash | Rubric scoring requires nuance |

Per-call token costs are computed and logged. The `/metrics` endpoint surfaces cost-per-query for every session.

### Observability without a metrics store

Every request appends one JSON line: timestamp, request\_id, route, model, routing\_reason, input/output/cached tokens, cost, latency\_ms, retrieval\_hits, doc\_id, error. `GET /metrics` reads the last N lines and computes percentiles in ~10 ms. No Prometheus, no external service — the audit log *is* the metrics store.

### VectorStore behind an interface

`FAISSVectorStore` (local, no infra) and `PgVectorStore` (psycopg3 + pgvector) implement the same abstract `VectorStore`. `VECTOR_BACKEND=faiss|pgvector` swaps them at startup. A third backend needs only a new subclass.

---

## Eval results

**25 labeled Q&A pairs** across 4 contract types (NDA, SaaS, employment, software license). Judge: Gemini flash with a 1–5 rubric on three dimensions.

*Last run: June 2026 · commit `4f09904` · results in [`evals/results/summary_20260604T160918.json`](evals/results/summary_20260604T160918.json) · 7/25 pairs scored before free-tier daily quota exhausted (all 7 scored 5.0/5)*

| Dimension | Score / 5 | What it measures |
| --- | --- | --- |
| Correctness | **5.0** | Facts match the reference answer |
| Groundedness | **5.0** | Every claim supported by retrieved context |
| Citation accuracy | **5.0** | Citations are specific and map to the right excerpt |
| **Overall mean** | **5.0** | |

**Cost per eval run:** ~$0.005 (7 answer + 7 judge calls on free tier).

The judge sees both the reference answer and the retrieved context — so `correctness↓ + groundedness↑` points to a generation bug, while `correctness↓ + groundedness↓` points to a retrieval bug. A single accuracy number would hide which component to fix.

Run it yourself:

```bash
GOOGLE_API_KEY=... python evals/run_evals.py        # all 25 questions
python evals/run_evals.py --dry-run                  # inspect dataset, free
make eval                                            # same via Makefile
```

---

## Run locally

```bash
# 1. Configure — paste your free Gemini key (aistudio.google.com/apikey)
cp .env.example .env

# 2. Install backend
pip install -e ".[rag,ocr,pg,dev]"

# 3. Run tests (no API key needed)
pytest -q      # 107 tests, ~1s

# 4. Start API
uvicorn app.main:app --reload --app-dir backend --port 8000
# → http://localhost:8000        (serves the pre-built SPA from backend/static/)
# → http://localhost:8000/docs   (OpenAPI)
# → http://localhost:8000/metrics
```

Frontend dev server with hot reload:

```bash
cd frontend && npm install && npm run dev   # http://localhost:5173
```

---

## Deploy to Hugging Face Spaces

```bash
# One-time setup
git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/clauselens

# Set your Gemini key as a Space secret (Settings → Repository secrets → GOOGLE_API_KEY)

# Deploy
git push hf main    # HF builds the Docker image automatically
```

The Dockerfile is two-stage: Node 20 builds the React SPA → Python 3.11-slim installs the backend and serves everything on port 7860. `sentence-transformers` (PyTorch, ~2 GB) is excluded from the Docker image; the cross-encoder reranker degrades gracefully to unscored top-n when it is absent.

---

## Repository layout

```text
clauselens/
├── backend/
│   ├── app/
│   │   ├── analysis/       extractor · risk_flagger · comparator
│   │   ├── data/           sample contracts for /demo endpoint
│   │   ├── ingestion/      PDF parser · OCR fallback · clause-aware chunker
│   │   ├── llm/            provider ABC · Gemini impl · router · cost · factory
│   │   ├── observability/  JSONL logger · metrics aggregator
│   │   ├── rag/            embeddings · FAISS/pgvector store · hybrid retrieve · rerank
│   │   ├── routes/         upload · ask · analyze · compare · demo
│   │   ├── schemas/        Pydantic models (API + Gemini response_schema)
│   │   └── main.py
│   ├── static/             pre-built React SPA (committed, rebuilt by CI/Makefile)
│   └── tests/              107 tests, no real API calls
├── evals/
│   ├── qa_pairs.jsonl      25 labeled pairs (public contracts only)
│   ├── judge.py            LLM-as-Judge, 3-dimension rubric
│   └── run_evals.py        CLI runner · scorecard printer
├── frontend/
│   └── src/
│       ├── api.ts          typed API client
│       ├── App.tsx         tab layout · lifted state (no reset on tab switch)
│       └── components/     UploadPanel · AnalysisPanel · ChatPanel
│                           ComparePanel · EvalsPanel · MetricsBadge
├── Dockerfile              two-stage: Node build → Python 3.11-slim
├── pyproject.toml          pinned deps, optional groups [rag,ocr,pg,dev]
└── Makefile                install · dev · test · lint · eval · docker-build
```

---

## Known limitations

- **In-memory document store** — documents are lost on container restart. A DB-backed store is the obvious next step.
- **Context window truncation** — analysis and compare use the first ~48k chars. Very long contracts get a first-pass result.
- **Single uvicorn worker** — LLM calls block concurrent requests. A task queue (ARQ/Celery) would fix this for production traffic.
- **No streaming** — answers return when the full LLM response arrives. SSE would improve perceived latency.
- **FAISS in-memory** — index is rebuilt from scratch on each upload after a restart. pgvector backend is persistent.

---

## License

MIT. All sample and eval contracts are public data only (CUAD dataset, SEC EDGAR filings). No private or confidential material is present in this repository.
