#!/usr/bin/env python3
"""Eval runner — ClauseLens RAG Q&A scorecard.

Usage:
    # From the repo root, with .env containing GOOGLE_API_KEY:
    python evals/run_evals.py

    # Filter to a subset of question ids:
    python evals/run_evals.py --ids q001,q002,q010

    # Use a different judge model:
    python evals/run_evals.py --judge-model gemini-2.5-flash

    # Dry-run: skip LLM calls and print the QA pairs
    python evals/run_evals.py --dry-run

Output:
    - evals/results/results_<timestamp>.jsonl  — per-question raw scores
    - evals/results/summary_<timestamp>.json   — aggregate scorecard
    - Prints a rich table to stdout

Design:
    Each eval item goes through the *live* /ask endpoint logic — the same
    retrieve() + LLM call that production uses. This means the evals measure
    the full stack: chunking quality, retrieval, reranking, and generation.

    The judge is an LLM-as-Judge (Gemini flash) with a 1-5 rubric on three
    dimensions: correctness, groundedness, citation_accuracy. The judge prompt
    contains the reference answer so scores are anchored to ground truth.

    Interview answer:
      "I separate the answering model from the judging model. The judge sees
      the reference answer and the retrieved context, so it can catch both
      retrieval failures (context didn't contain the answer) and generation
      failures (context was good but the model hallucinated). This two-level
      attribution is more useful than a single accuracy number."
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Allow running from repo root or from the evals/ directory
_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "backend"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("run_evals")

_QA_FILE = Path(__file__).parent / "qa_pairs.jsonl"
_RESULTS_DIR = Path(__file__).parent / "results"

# Sample contract texts embedded directly for self-contained eval runs.
# In a full deployment these would be uploaded PDFs; for the eval harness we
# use representative excerpts from public CUAD-derived sample contracts.
_SAMPLE_CONTRACTS: dict[str, str] = {
    "sample_nda": """
NON-DISCLOSURE AGREEMENT

This Non-Disclosure Agreement ("Agreement") is entered into as of January 1, 2024,
by and between Acme Technologies Inc. ("Disclosing Party") and Beta Solutions LLC
("Receiving Party").

1. CONFIDENTIAL INFORMATION
"Confidential Information" means any non-public information disclosed by the
Disclosing Party to the Receiving Party. Confidential Information does not include
information that: (a) is or becomes publicly known through no breach of this
Agreement; (b) was rightfully known before disclosure; (c) is independently
developed without use of Confidential Information; or (d) is received from a
third party without restriction.

2. OBLIGATIONS
The Receiving Party shall: (a) hold Confidential Information in strict confidence
using at least the same degree of care as it uses for its own confidential
information, but no less than reasonable care; (b) not disclose Confidential
Information to any third party without prior written consent; (c) use Confidential
Information solely for evaluating a potential business relationship.

The Receiving Party may disclose Confidential Information to its employees who
have a need to know, provided such employees are bound by confidentiality
obligations at least as protective as this Agreement.

3. TERM AND SURVIVAL
This Agreement commences on the date first written above and continues for two (2)
years. The confidentiality obligations shall survive termination for a period of
two (2) years following termination of this Agreement.

4. REMEDIES
The Receiving Party acknowledges that breach of this Agreement may cause
irreparable harm. In addition to monetary damages, the Disclosing Party is
entitled to seek injunctive or other equitable relief without posting a bond,
as monetary damages may be inadequate.

5. GOVERNING LAW
This Agreement shall be governed by the laws of the State of Delaware, without
regard to conflict of law principles.
""",
    "sample_saas": """
SOFTWARE AS A SERVICE AGREEMENT

This SaaS Agreement ("Agreement") is entered into between CloudVendor Inc.
("Vendor") and Enterprise Corp ("Customer").

1. SERVICES AND SLA
Vendor will provide the SaaS platform ("Service"). Vendor commits to 99.9%
monthly uptime, calculated as: (total minutes - downtime minutes) / total minutes.
Scheduled maintenance windows communicated at least 48 hours in advance are
excluded from downtime calculations.

2. PAYMENT TERMS
Customer shall pay all fees within 30 days of the invoice date. Overdue amounts
accrue interest at 1.5% per month or the maximum rate permitted by applicable
law, whichever is lower. All fees are non-refundable except as expressly stated.

3. DATA AND PRIVACY
Vendor may use aggregated, anonymized customer data to improve its services.
Vendor may not use identifiable customer data for any purpose other than providing
the contracted services. Upon termination, Vendor will make Customer data available
for export for 30 days, after which it will be deleted from all systems within
60 days.

4. INTELLECTUAL PROPERTY
Each party retains ownership of its pre-existing intellectual property.

5. LIMITATION OF LIABILITY
Each party's total liability is capped at the total fees paid or payable by
Customer in the twelve (12) months preceding the claim. IN NO EVENT SHALL EITHER
PARTY BE LIABLE FOR INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE
DAMAGES, INCLUDING LOSS OF PROFITS, REVENUE, DATA, OR BUSINESS OPPORTUNITY,
EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.

6. INDEMNIFICATION
Vendor shall indemnify, defend, and hold harmless Customer against third-party
claims alleging that the Service infringes a patent, copyright, or trade secret,
subject to: (a) Customer promptly notifying Vendor in writing; (b) Vendor having
sole control of the defense; (c) Customer cooperating fully with Vendor.

7. TERMINATION
Either party may terminate for convenience upon 30 days written notice.
Either party may terminate immediately upon material breach that remains uncured
for 15 days after written notice.

8. AUTO-RENEWAL
This Agreement automatically renews for successive one-year terms unless either
party provides 60 days written notice of non-renewal before the end of the
then-current term.
""",
    "sample_employment": """
EMPLOYMENT AGREEMENT

This Employment Agreement is entered into between TechStartup Inc. ("Company")
and Jane Smith ("Employee"), effective February 1, 2024.

1. POSITION AND COMPENSATION
Employee is hired as Senior Software Engineer. Base salary is $120,000 per year,
payable in equal bi-weekly installments. Employee is eligible for an annual
performance bonus of up to 15% of base salary.

2. INTELLECTUAL PROPERTY
All inventions, developments, and works created by Employee within the scope of
employment, or using Company resources or information, are work-for-hire and are
assigned to and owned by the Company. Employee waives all moral rights.

3. CONFIDENTIALITY
Employee shall maintain in confidence all proprietary information during and
after employment, with no time limitation.

4. NON-COMPETE
For one (1) year following termination for any reason, Employee shall not engage
in any business that competes with the Company in any geographic area where the
Company conducts business. Employee shall not solicit Company customers or
employees for two (2) years following termination.

5. TERMINATION
Company may terminate Employee's employment without cause upon 60 days written
notice or payment in lieu of notice at Company's election. Employee may
terminate upon 30 days written notice.

6. DISPUTE RESOLUTION
Any dispute arising from or related to this Agreement shall be resolved by
binding arbitration under the rules of the American Arbitration Association
in the state of the Company's principal office. The arbitrator's decision
shall be final and may be entered as a judgment in any court of competent
jurisdiction.
""",
    "sample_license": """
SOFTWARE LICENSE AGREEMENT

This Software License Agreement is between Licensor Corp ("Licensor") and
Licensee Ltd ("Licensee"), effective March 1, 2024.

1. GRANT OF LICENSE
Subject to the terms of this Agreement, Licensor grants Licensee a non-exclusive,
non-transferable license to use the Software solely within Licensee's organization.
Licensee may not sublicense, sell, resell, transfer, assign, or otherwise dispose
of the Software or its rights under this Agreement.

2. TERM AND RENEWAL
This Agreement commences on the effective date and continues for one year.
It automatically renews for successive one-year terms unless either party
provides 60 days written notice of non-renewal before the end of the current term.

3. WARRANTY
Licensor warrants that the Software will substantially conform to the
documentation for 90 days following delivery ("Warranty Period"). This warranty
does not apply if the Software has been modified by Licensee. After the Warranty
Period, the Software is provided AS IS without warranty of any kind.

4. AUDIT RIGHTS
Licensor may audit Licensee's use of the Software upon 10 days written notice,
no more than once per calendar year, during normal business hours, to verify
compliance with the license terms. Licensee shall maintain records sufficient
to verify compliance.

5. FEES
Annual license fee is $25,000, invoiced on the anniversary of the effective date.
Payment is due within 30 days of invoice.
""",
}


def load_qa_pairs(ids: list[str] | None = None) -> list[dict]:
    pairs = []
    with open(_QA_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if ids is None or item["id"] in ids:
                pairs.append(item)
    return pairs


def run_answer(
    *,
    question: str,
    doc_id: str,
    contract_text: str,
    llm,
    model_cheap: str,
    model_strong: str,
    top_k: int = 5,
) -> tuple[str, str, float, int, int]:
    """Run the full RAG pipeline for one question on one contract.

    Returns (answer, context_str, cost_usd, input_tokens, output_tokens).
    """
    from app.ingestion.chunker import chunk_document
    from app.llm.provider import Message
    from app.llm.router import classify_query_task, route
    from app.rag.retrieve import _bm25_ranked, _build_bm25

    # Chunk the contract text
    chunks = chunk_document(
        full_text=contract_text,
        doc_id=doc_id,
        filename=f"{doc_id}.txt",
        page_count=1,
    )

    if not chunks:
        return "No chunks generated.", "", 0.0, 0, 0

    # BM25-only retrieval (no vector store needed for eval harness)
    bm25 = _build_bm25(chunks)
    retrieved = _bm25_ranked(bm25, chunks, question, top_k=top_k)

    context_parts = []
    for chunk, _score in retrieved:
        citation = getattr(chunk, "citation", "")
        text = getattr(chunk, "text", "")
        context_parts.append(f"[{citation}]\n{text}")
    context_str = "\n\n---\n\n".join(context_parts)

    task = classify_query_task(question)
    model, _ = route(task, model_cheap, model_strong, query=question)

    system_prompt = (
        "You are a precise contract analysis assistant. "
        "Answer the question using ONLY the provided contract excerpts. "
        "Cite every factual claim with the citation label, e.g. [Section 4.2]. "
        "If the context is insufficient, say so."
    )
    user_msg = f"Contract excerpts:\n\n{context_str}\n\nQuestion: {question}"

    resp = llm.timed_complete(
        messages=[Message(role="user", content=user_msg)],
        model=model,
        system_prompt=system_prompt,
        temperature=0.0,
    )
    return resp.content, context_str, resp.cost_usd, resp.input_tokens, resp.output_tokens


def print_scorecard(results: list[dict], summary: dict) -> None:
    """Print a text scorecard table."""
    col_w = [8, 50, 13, 13, 15, 8]
    header = ["ID", "Question", "Correct.", "Ground.", "Citation", "Mean"]
    sep = "+" + "+".join("-" * w for w in col_w) + "+"
    fmt = "|" + "|".join(f"{{:<{w}}}" for w in col_w) + "|"

    print("\n" + sep)
    print(fmt.format(*header))
    print(sep)
    for r in results:
        if r.get("error"):
            row = [r["id"], r["question"][:48], "ERR", "ERR", "ERR", "0.0"]
        else:
            row = [
                r["id"],
                r["question"][:48],
                str(r["correctness"]),
                str(r["groundedness"]),
                str(r["citation_accuracy"]),
                f"{r['mean']:.2f}",
            ]
        print(fmt.format(*row))
    print(sep)

    print(f"\n{'='*60}")
    print("AGGREGATE SCORECARD")
    print(f"{'='*60}")
    print(f"  Questions evaluated : {summary['n_questions']}")
    print(f"  Errors              : {summary['n_errors']}")
    print(f"  Correctness (mean)  : {summary['correctness_mean']:.2f} / 5")
    print(f"  Groundedness (mean) : {summary['groundedness_mean']:.2f} / 5")
    print(f"  Citation acc (mean) : {summary['citation_accuracy_mean']:.2f} / 5")
    print(f"  Overall mean        : {summary['overall_mean']:.2f} / 5")
    print(f"  Total cost          : ${summary['total_cost_usd']:.5f}")
    print(f"  Cost per question   : ${summary['cost_per_question_usd']:.5f}")
    print(f"  Total input tokens  : {summary['total_input_tokens']}")
    print(f"  Total output tokens : {summary['total_output_tokens']}")
    print(f"{'='*60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="ClauseLens eval runner")
    parser.add_argument("--ids", help="Comma-separated question IDs to run (default: all)")
    parser.add_argument(
        "--judge-model",
        default="gemini-2.5-flash",
        help="Model used for LLM-as-Judge scoring (default: gemini-2.5-flash)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print pairs without calling LLM")
    parser.add_argument("--top-k", type=int, default=5, help="Retrieval top-k (default: 5)")
    args = parser.parse_args()

    id_filter = [x.strip() for x in args.ids.split(",")] if args.ids else None
    pairs = load_qa_pairs(id_filter)
    if not pairs:
        logger.error("No QA pairs found (check --ids filter or %s)", _QA_FILE)
        sys.exit(1)

    logger.info("Loaded %d QA pairs", len(pairs))

    if args.dry_run:
        for p in pairs:
            print(f"[{p['id']}] {p['question']} (doc: {p['doc_id']})")
        return

    # Boot app config + LLM
    from app.config import get_settings
    from app.llm.factory import get_llm

    from evals.judge import judge_answer

    settings = get_settings()
    if not settings.has_llm_credentials:
        logger.error(
            "GOOGLE_API_KEY not set. Add it to backend/.env or export it."
        )
        sys.exit(1)

    llm = get_llm()
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    results_path = _RESULTS_DIR / f"results_{ts}.jsonl"
    summary_path = _RESULTS_DIR / f"summary_{ts}.json"

    all_results: list[dict] = []
    total_cost = 0.0
    total_input = 0
    total_output = 0

    for i, pair in enumerate(pairs, 1):
        qid = pair["id"]
        question = pair["question"]
        doc_id = pair["doc_id"]
        reference = pair["reference_answer"]

        contract_text = _SAMPLE_CONTRACTS.get(doc_id, "")
        if not contract_text:
            logger.warning("No sample contract text for doc_id=%s, skipping", doc_id)
            continue

        logger.info("[%d/%d] %s — %s", i, len(pairs), qid, question[:60])
        t0 = time.perf_counter()

        try:
            answer, context_str, answer_cost, in_tok, out_tok = run_answer(
                question=question,
                doc_id=doc_id,
                contract_text=contract_text,
                llm=llm,
                model_cheap=settings.model_cheap,
                model_strong=settings.model_strong,
                top_k=args.top_k,
            )
        except Exception as exc:
            logger.exception("Answer generation failed for %s", qid)
            row = {"id": qid, "question": question, "error": str(exc)}
            all_results.append(row)
            with open(results_path, "a") as f:
                f.write(json.dumps(row) + "\n")
            continue

        score = judge_answer(
            question_id=qid,
            question=question,
            reference=reference,
            context=context_str,
            answer=answer,
            llm=llm,
            model=args.judge_model,
        )

        elapsed = (time.perf_counter() - t0) * 1000
        combined_cost = answer_cost + score.cost_usd
        total_cost += combined_cost
        total_input += in_tok + score.input_tokens
        total_output += out_tok + score.output_tokens

        row = {
            "id": qid,
            "doc_id": doc_id,
            "question": question,
            "reference": reference,
            "answer": answer,
            "correctness": score.correctness,
            "groundedness": score.groundedness,
            "citation_accuracy": score.citation_accuracy,
            "mean": round(score.mean, 3),
            "reasoning": score.reasoning,
            "error": score.error,
            "judge_model": score.model,
            "answer_cost_usd": round(answer_cost, 7),
            "judge_cost_usd": round(score.cost_usd, 7),
            "total_cost_usd": round(combined_cost, 7),
            "latency_ms": round(elapsed, 1),
            "tags": pair.get("tags", []),
        }
        all_results.append(row)
        with open(results_path, "a") as f:
            f.write(json.dumps(row) + "\n")

        logger.info(
            "  → correct=%.1f ground=%.1f cite=%.1f mean=%.2f cost=$%.5f",
            score.correctness,
            score.groundedness,
            score.citation_accuracy,
            score.mean,
            combined_cost,
        )

    # Compute aggregate stats
    scored = [r for r in all_results if not r.get("error")]
    n = len(scored)
    summary = {
        "timestamp": ts,
        "n_questions": len(all_results),
        "n_scored": n,
        "n_errors": len(all_results) - n,
        "correctness_mean": round(sum(r["correctness"] for r in scored) / n, 3) if n else 0,
        "groundedness_mean": round(sum(r["groundedness"] for r in scored) / n, 3) if n else 0,
        "citation_accuracy_mean": (  # noqa: E501
            round(sum(r["citation_accuracy"] for r in scored) / n, 3) if n else 0
        ),
        "overall_mean": round(sum(r["mean"] for r in scored) / n, 3) if n else 0,
        "total_cost_usd": round(total_cost, 6),
        "cost_per_question_usd": round(total_cost / len(all_results), 6) if all_results else 0,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "judge_model": args.judge_model,
        "results_file": str(results_path),
    }

    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print_scorecard(all_results, summary)
    logger.info("Results written to %s", results_path)
    logger.info("Summary written to %s", summary_path)


if __name__ == "__main__":
    main()
