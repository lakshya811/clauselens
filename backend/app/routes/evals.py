"""Evals endpoints.

GET  /evals/summary  — latest results (live run > baseline.json fallback)
GET  /evals/status   — current run state: idle | running | done | error
POST /evals/run      — kick off a background eval run (requires GOOGLE_API_KEY)
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import threading
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evals", tags=["evals"])

_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_RESULTS_DIR = _REPO_ROOT / "evals" / "results"
_BASELINE_FILE = _REPO_ROOT / "evals" / "baseline.json"

# In-memory run state — single worker, reset on each POST /evals/run
_run_state: dict = {"status": "idle", "started_at": None, "log": [], "error": None}
_run_lock = threading.Lock()


# ---------------------------------------------------------------------------
# GET /evals/summary
# ---------------------------------------------------------------------------

@router.get("/summary")
def evals_summary() -> dict:
    """Return the latest eval run summary, or the committed baseline."""
    if _RESULTS_DIR.is_dir():
        summaries = sorted(_RESULTS_DIR.glob("summary_*.json"), reverse=True)
        if summaries:
            try:
                with open(summaries[0]) as f:
                    data = json.load(f)
                data["status"] = "ok"
                data["is_baseline"] = False
                return data
            except Exception:
                logger.exception("Failed to read eval summary %s", summaries[0])

    if _BASELINE_FILE.exists():
        try:
            with open(_BASELINE_FILE) as f:
                data = json.load(f)
            data["status"] = "ok"
            data["is_baseline"] = True
            return data
        except Exception as exc:
            logger.exception("Failed to read baseline")
            return {"status": "error", "detail": str(exc)}

    return {"status": "not_run"}


# ---------------------------------------------------------------------------
# GET /evals/status
# ---------------------------------------------------------------------------

@router.get("/status")
def evals_status() -> dict:
    """Return the current background run state."""
    with _run_lock:
        return {**_run_state}


# ---------------------------------------------------------------------------
# POST /evals/run
# ---------------------------------------------------------------------------

def _do_run(api_key: str) -> None:
    """Run the eval harness in a background thread, updating _run_state."""
    global _run_state

    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    def log(msg: str) -> None:
        logger.info("[eval-run] %s", msg)
        with _run_lock:
            _run_state["log"].append(msg)

    try:
        log("Starting eval harness (25 questions, ~8 min on free tier)…")

        cmd = [
            sys.executable, "-m", "evals.run_evals",
            "--sleep", "12",
            "--judge-model", "gemini-2.5-flash",
        ]
        env_extra = {"GOOGLE_API_KEY": api_key, "MODEL_CHEAP": "gemini-2.5-flash", "MODEL_STRONG": "gemini-2.5-flash"}

        import os
        env = {**os.environ, **env_extra}

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(_REPO_ROOT),
            env=env,
        )

        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                log(line)

        proc.wait()

        if proc.returncode == 0:
            with _run_lock:
                _run_state["status"] = "done"
            log("✓ Eval run complete — refresh to see scores.")
        else:
            with _run_lock:
                _run_state["status"] = "error"
                _run_state["error"] = f"Process exited with code {proc.returncode}"
            log(f"✗ Run failed (exit {proc.returncode})")

    except Exception as exc:
        logger.exception("Eval background thread failed")
        with _run_lock:
            _run_state["status"] = "error"
            _run_state["error"] = str(exc)


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
def evals_run() -> dict:
    """Kick off a background eval run. Returns 202 immediately."""
    global _run_state

    settings = get_settings()
    if not settings.has_llm_credentials:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GOOGLE_API_KEY not configured on this server.",
        )

    with _run_lock:
        if _run_state["status"] == "running":
            return {"message": "Already running", "status": "running"}
        _run_state = {
            "status": "running",
            "started_at": time.time(),
            "log": [],
            "error": None,
        }

    t = threading.Thread(target=_do_run, args=(settings.google_api_key,), daemon=True)
    t.start()
    return {"message": "Eval run started", "status": "running"}
