"""Evals results endpoint — serves the latest eval run summary to the frontend.

GET /evals/summary
  Reads the most recent evals/results/summary_<ts>.json and returns it verbatim.
  Returns {"status": "not_run"} if no results file exists yet.

This lets the Evals tab in the UI show real measured scores rather than hardcoded
constants, while degrading gracefully on a fresh deployment.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evals", tags=["evals"])

# Walk up from this file to the repo root, then into evals/results/
_RESULTS_DIR = Path(__file__).parent.parent.parent.parent / "evals" / "results"


@router.get("/summary")
def evals_summary() -> dict:
    """Return the latest eval run summary, or {status: not_run} if none exist."""
    if not _RESULTS_DIR.is_dir():
        return {"status": "not_run"}

    summaries = sorted(_RESULTS_DIR.glob("summary_*.json"), reverse=True)
    if not summaries:
        return {"status": "not_run"}

    try:
        with open(summaries[0]) as f:
            data = json.load(f)
        data["status"] = "ok"
        return data
    except Exception as exc:
        logger.exception("Failed to read eval summary %s", summaries[0])
        return {"status": "error", "detail": str(exc)}
