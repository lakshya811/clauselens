"""Evals results endpoint — serves the latest eval run summary to the frontend.

GET /evals/summary
  1. Looks for evals/results/summary_<ts>.json (written by run_evals.py).
     If found, returns the newest one — these are real measured scores.
  2. Falls back to evals/baseline.json — a committed representative baseline
     used until a live run is available.
  3. Returns {"status": "not_run"} if neither exists.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evals", tags=["evals"])

_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_RESULTS_DIR = _REPO_ROOT / "evals" / "results"
_BASELINE_FILE = _REPO_ROOT / "evals" / "baseline.json"


@router.get("/summary")
def evals_summary() -> dict:
    """Return the latest eval run summary, or the committed baseline."""
    # Prefer a real timestamped run result
    if _RESULTS_DIR.is_dir():
        summaries = sorted(_RESULTS_DIR.glob("summary_*.json"), reverse=True)
        if summaries:
            try:
                with open(summaries[0]) as f:
                    data = json.load(f)
                data["status"] = "ok"
                data["is_baseline"] = False
                return data
            except Exception as exc:
                logger.exception("Failed to read eval summary %s", summaries[0])

    # Fall back to committed baseline
    if _BASELINE_FILE.exists():
        try:
            with open(_BASELINE_FILE) as f:
                data = json.load(f)
            data["status"] = "ok"
            data["is_baseline"] = True
            return data
        except Exception as exc:
            logger.exception("Failed to read baseline %s", _BASELINE_FILE)
            return {"status": "error", "detail": str(exc)}

    return {"status": "not_run"}
