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

# ClauseLens — AI Contract Analysis & Comparison

> Upload a contract PDF → get **clause extraction**, **risk flags**, **version diff**,
> and a **citation-grounded Q&A chat**, all in one dark-themed web UI.
> Built as a production-grade AI engineering portfolio project.

[![CI](https://github.com/USERNAME/clauselens/actions/workflows/ci.yml/badge.svg)](https://github.com/USERNAME/clauselens/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

🔗 **Live demo:** [lakshya1111-clauselens.hf.space](https://lakshya1111-clauselens.hf.space) _(Hugging Face Space)_

---

## What it does

| Feature | Description |
| --- | --- |
| **Clause extraction** | Parties, effective/expiry dates, governing law, payment, liability cap, termination terms — structured JSON via Gemini JSON mode |
| **Risk flagging** | Uncapped liability, auto-renewal traps, broad IP assignment, weak confidentiality — severity + clause reference + negotiation recommendation |
| **Version compare** | Upload two PDFs → every change classified as **Structural** (added/removed clause) / **Semantic** (meaning changed) / **Surface** (wording only) |
| **Q&A chat** | Hybrid RAG (BM25 + vector + RRF + cross-encoder rerank) → cited answers; every claim maps back to a clause/page |
| **Observability** | Live metrics badge: req count · p50 latency · cost-per-query; full JSONL audit log |

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│  Browser  (React + Tailwind dark)                               │
│  Upload │ Analysis │ Q&A Chat │ Compare │ Metrics badge         │
└────────────────────┬────────────────────────────────────────────┘
                     │ REST (same origin / Vite proxy in dev)
┌────────────────────▼────────────────────────────────────────────┐
│  FastAPI  (uvicorn, single worker)                              │
│                                                                 │
│  POST /upload   ──► PDF parse (pdfplumber + pytesseract OCR)   │
│                     clause-aware chunker                        │
│                     embed_texts() ──► FAISS index              │
│                                                                 │
│  POST /ask      ──► embed_query()                              │
│                     hybrid retrieve: BM25 + FAISS + RRF        │
│                     cross-encoder rerank                        │
│                     model router ──► Gemini (cheap | strong)   │
│                     → cited AskResponse                        │
│                                                                 │
│  POST /analyze/{doc_id}                                         │
│                     extract_clauses()  cheap model (flash-lite)│
│                     flag_risks()       strong model (flash)    │
│                     → AnalysisResponse                         │
│                                                                 │
│  POST /compare  ──► compare_contracts() strong model (flash)   │
│                     → CompareResponse (Structural/Semantic/    │
│                       Surface per changed clause)              │
│                                                                 │
│  GET  /metrics  ──► compute_metrics() reads JSONL audit log    │
│                     p50/p95 latency · cost/query · error rate  │
└─────────────────────────────────────────────────────────────────┘
         │ embed/complete                        │ vectors
┌────────▼────────┐                    ┌─────────▼──────────┐
│  Gemini API     │                    │  FAISS (local)     │
│  text-embed-004 │                    │  pgvector (deploy) │
│  flash-lite     │                    └────────────────────┘
│  flash          │
└─────────────────┘
```

---

## Engineering decisions & tradeoffs

### 1. Hybrid retrieval (BM25 + vector + RRF + cross-encoder rerank)

**Why not pure vector search?**
Legal text is full of exact-match terms that vectors generalise away: `Section 7.2`,
`indemnify`, `force majeure`. BM25 catches these; the vector arm catches semantically
similar clauses ("terminate at will" ↔ "terminate for convenience"). Reciprocal Rank
Fusion (RRF, k=60) merges both ranked lists without tuning a weight. The
cross-encoder reranker then scores the top candidates as (query, passage) pairs —
the most accurate but slowest step, applied only to a small shortlist.

**Tradeoff:** +80–150 ms vs. pure vector search. For a document-level Q&A tool
this is acceptable; for real-time autocomplete it would not be.

### 2. Structured outputs via Gemini JSON mode

`ClauseBundle`, `RiskReport`, `CompareResult` are Pydantic models used as both the
Gemini `response_schema` (forces JSON mode) and the FastAPI response model. One
source of truth: the schema validates on receipt and documents the API.

**Retry on parse failure:** `complete_json()` retries up to 2× if the model returns
malformed JSON. On all-attempts failure it returns a graceful degraded response
(error in `confidence_note` / `summary`) rather than a 500.

### 3. Cost-aware model routing

| Task | Model | Reason |
| --- | --- | --- |
| Clause extraction | `flash-lite` | Structured fill-in-the-blanks; no reasoning needed |
| Simple Q&A (short, factual) | `flash-lite` | Keyword heuristic: who/when/what < 200 chars |
| Complex Q&A (long / multi-hop) | `flash` | Length + keyword trigger: compare/analyse/liable |
| Risk flagging | `flash` | Legal inference: "is this cap unusually low?" |
| Version compare | `flash` | Multi-step: locate + classify + explain across two docs |
| LLM-as-Judge | `flash` | Evaluation requires nuanced rubric scoring |

Real token costs are computed per call (`calculate_cost(model, in_tok, out_tok)`)
and logged. The `/metrics` endpoint surfaces the cost-per-query number.

### 4. VectorStore behind an ABC

`FAISSVectorStore` (local, zero infra) and `PgVectorStore` (psycopg3 + pgvector)
implement the same `VectorStore` interface. `VECTOR_BACKEND=faiss|pgvector` swaps
them at startup. Adding a third backend (e.g. Pinecone) requires only a new
subclass — no changes to retrieval or route code.

### 5. Observability without a metrics store

Every request appends a JSON line to `requests.jsonl`: timestamp, request\_id, route,
model, routing\_reason, tokens in/out, cost, latency\_ms, retrieval\_hits, doc\_id,
error. `GET /metrics` reads the last N lines and computes p50/p95/mean latency,
per-model breakdown, error rate, and cost-per-query in ~10 ms. No Prometheus,
no InfluxDB — the audit log _is_ the metrics store. Works in a free-tier container
with no persistent network services.

### 6. Eval harness design

The judge (Gemini flash) sees both the **reference answer** and the **retrieved
context**. This gives two failure signals:

- `correctness=low, groundedness=high` → retrieval worked, model hallucinated
- `correctness=low, groundedness=low` → retrieval failed (right answer not in context)

A single accuracy metric would hide which component to fix.

---

## Eval results

Run with `make eval` (requires `GOOGLE_API_KEY`).

| Metric | Score / 5 | Notes |
| --- | --- | --- |
| Correctness | — | Populated after live run |
| Groundedness | — | Populated after live run |
| Citation accuracy | — | Populated after live run |
| **Overall mean** | — | |

**25 QA pairs** across 4 contract types (NDA, SaaS, employment, software license).
**Cost per eval run:** ~$0.02–0.04 (25 answer calls + 25 judge calls on flash).

---

## Run locally (4 commands)

```bash
# 1. Configure
cp .env.example .env           # paste your free Gemini key from aistudio.google.com

# 2. Install
pip install -e ".[rag,ocr,pg,dev]"   # or: make install

# 3. Test
pytest -q                      # 107 tests, ~1s, no API key needed

# 4. Run
uvicorn app.main:app --reload --app-dir backend --port 8000
# → API docs:   http://localhost:8000/docs
# → Frontend:   http://localhost:8000  (served from backend/static)
# → Metrics:    http://localhost:8000/metrics
```

For the **frontend dev server** (hot reload):

```bash
cd frontend && npm install && npm run dev   # http://localhost:5173
```

---

## How to deploy (Hugging Face Space)

ClauseLens ships as a single Docker image: FastAPI serves both the REST API and the
pre-built React SPA from `backend/static/`.

### 1. Create the Space

Go to [huggingface.co/new-space](https://huggingface.co/new-space):

- SDK: **Docker**
- Hardware: CPU Basic (free)
- Visibility: Public

### 2. Set secrets

In Space Settings → Repository secrets:

| Secret | Value |
| --- | --- |
| `GOOGLE_API_KEY` | Your Gemini API key |
| `VECTOR_BACKEND` | `faiss` (default) or `pgvector` |
| `DATABASE_URL` | (only if using pgvector) |

### 3. Push

```bash
git remote add hf https://huggingface.co/spaces/YOUR_HF_USERNAME/clauselens
git push hf main
```

The Space auto-builds the Docker image and exposes port 7860.

### Environment variables reference

| Variable | Default | Description |
| --- | --- | --- |
| `GOOGLE_API_KEY` | _(required)_ | Gemini API key |
| `VECTOR_BACKEND` | `faiss` | `faiss` or `pgvector` |
| `FAISS_INDEX_DIR` | `/data/index` | Persistent index path |
| `LOG_DIR` | `/data/logs` | JSONL audit log path |
| `MODEL_CHEAP` | `gemini-2.5-flash-lite` | Cheap routing tier |
| `MODEL_STRONG` | `gemini-2.5-flash` | Strong routing tier |
| `MAX_UPLOAD_MB` | `15` | Max PDF size |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |

---

## Repository layout

```text
clauselens/
├── backend/
│   ├── app/
│   │   ├── analysis/         # extractor.py, risk_flagger.py, comparator.py
│   │   ├── ingestion/        # parser.py, chunker.py
│   │   ├── llm/              # provider.py, gemini.py, router.py, cost.py, factory.py
│   │   ├── observability/    # logger.py, metrics.py
│   │   ├── rag/              # embeddings.py, store.py, retrieve.py, rerank.py
│   │   ├── routes/           # upload.py, qa.py, analyze.py, compare.py
│   │   ├── schemas/          # qa.py, analysis.py, compare.py, documents.py
│   │   └── main.py
│   ├── static/               # pre-built React SPA (git-committed, built by CI)
│   └── tests/                # 107 tests, no real API calls
├── evals/
│   ├── qa_pairs.jsonl        # 25 labeled Q&A pairs (public contracts only)
│   ├── judge.py              # LLM-as-Judge, 3-dimension rubric
│   ├── run_evals.py          # CLI runner + scorecard printer
│   └── results/              # timestamped JSONL + JSON summaries
├── frontend/
│   ├── src/
│   │   ├── api.ts            # typed API client
│   │   ├── App.tsx           # tab layout + state
│   │   └── components/       # UploadPanel, AnalysisPanel, ChatPanel,
│   │                         # ComparePanel, MetricsBadge
│   └── vite.config.ts        # builds to backend/static/; proxies /ask etc. in dev
├── Dockerfile                # two-stage: Node build → Python 3.11-slim runtime
├── pyproject.toml            # pinned deps, optional groups [rag,ocr,pg,dev]
├── Makefile                  # install / dev / test / lint / eval / docker-build
└── .env.example
```

---

## Known limitations

- **No auth / multi-tenancy** — documents are stored in process memory; a restart
  clears them. For persistent storage, add a DB-backed document store.
- **Context window truncation** — analysis and comparison use the first ~48k chars
  (~12k tokens). Very long contracts get a first-pass result; section-by-section
  chunked analysis is the natural next step.
- **Single worker** — HF Space runs one uvicorn worker. Heavy LLM calls block
  other requests. For production throughput, add a task queue (Celery/ARQ).
- **No streaming** — answers are returned when the full LLM response arrives.
  Streaming via Server-Sent Events would improve perceived latency for long answers.
- **FAISS is in-memory** — the index lives in the container's RAM; on restart the
  index rebuilds on next upload. pgvector backend is persistent.
- **Eval dataset** — 25 QA pairs covers the happy path; adversarial, ambiguous,
  and multi-document questions are not yet represented.

---

## License

MIT. All sample contracts used in tests and evals are **public data only**
(CUAD dataset / SEC EDGAR filings). No private or confidential documents are
present anywhere in this repository.
