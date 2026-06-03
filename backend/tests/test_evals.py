"""Tests for the eval harness — judge scoring and QA dataset.

Strategy:
  - Judge: mock LLM response to verify score parsing, fallback on JSON error,
    strip markdown fences, mean calculation.
  - Dataset: verify qa_pairs.jsonl has ≥25 pairs, required fields, no duplicate IDs.
  - run_evals helpers: load_qa_pairs filter, sample contract texts present.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Make evals/ importable from the backend test runner
_REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from app.llm.provider import LLMResponse  # noqa: E402

_QA_FILE = _REPO_ROOT / "evals" / "qa_pairs.jsonl"


# ---------------------------------------------------------------------------
# Dataset integrity
# ---------------------------------------------------------------------------


def _load_all_pairs() -> list[dict]:
    pairs = []
    with open(_QA_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                pairs.append(json.loads(line))
    return pairs


def test_qa_dataset_has_minimum_pairs() -> None:
    pairs = _load_all_pairs()
    assert len(pairs) >= 25, f"Expected ≥25 QA pairs, got {len(pairs)}"


def test_qa_dataset_no_duplicate_ids() -> None:
    pairs = _load_all_pairs()
    ids = [p["id"] for p in pairs]
    assert len(ids) == len(set(ids)), "Duplicate IDs found in qa_pairs.jsonl"


def test_qa_dataset_required_fields() -> None:
    pairs = _load_all_pairs()
    required = {"id", "doc_id", "question", "reference_answer"}
    for p in pairs:
        missing = required - p.keys()
        assert not missing, f"QA pair {p.get('id')} is missing fields: {missing}"


def test_qa_dataset_covers_multiple_docs() -> None:
    pairs = _load_all_pairs()
    doc_ids = {p["doc_id"] for p in pairs}
    assert len(doc_ids) >= 3, f"Expected ≥3 distinct doc_ids, got {doc_ids}"


# ---------------------------------------------------------------------------
# Judge: score parsing
# ---------------------------------------------------------------------------


def _mock_llm_for_judge(json_response: str) -> MagicMock:
    llm = MagicMock()
    llm.timed_complete.return_value = LLMResponse(
        content=json_response,
        model="gemini-2.5-flash",
        input_tokens=500,
        output_tokens=80,
        cost_usd=0.00005,
        latency_ms=300.0,
    )
    return llm


def test_judge_parses_scores() -> None:
    from evals.judge import judge_answer

    payload = json.dumps({
        "correctness": 4,
        "groundedness": 5,
        "citation_accuracy": 3,
        "reasoning": "Correct facts; fully grounded; citations present but vague.",
    })
    llm = _mock_llm_for_judge(payload)
    score = judge_answer(
        question_id="q001",
        question="Who are the parties?",
        reference="Party A and Party B.",
        context="[Section 1]\nThis agreement is between Party A and Party B.",
        answer="The parties are Party A and Party B [Section 1].",
        llm=llm,
        model="gemini-2.5-flash",
    )
    assert score.correctness == 4.0
    assert score.groundedness == 5.0
    assert score.citation_accuracy == 3.0
    assert score.error == ""


def test_judge_mean_calculation() -> None:
    from evals.judge import JudgeScore

    s = JudgeScore(question_id="q001", correctness=3, groundedness=4, citation_accuracy=5)
    assert abs(s.mean - 4.0) < 1e-9


def test_judge_strips_markdown_fence() -> None:
    from evals.judge import judge_answer

    payload = (
        "```json\n"
        + json.dumps({
            "correctness": 5,
            "groundedness": 5,
            "citation_accuracy": 5,
            "reasoning": "Perfect.",
        })
        + "\n```"
    )
    llm = _mock_llm_for_judge(payload)
    score = judge_answer(
        question_id="q002",
        question="Q?",
        reference="R.",
        context="C.",
        answer="A.",
        llm=llm,
        model="gemini-2.5-flash",
    )
    assert score.correctness == 5.0
    assert score.error == ""


def test_judge_fallback_on_invalid_json() -> None:
    from evals.judge import judge_answer

    llm = _mock_llm_for_judge("not valid json at all")
    score = judge_answer(
        question_id="q003",
        question="Q?",
        reference="R.",
        context="C.",
        answer="A.",
        llm=llm,
        model="gemini-2.5-flash",
    )
    assert score.error != ""
    assert score.correctness == 0.0
    assert score.mean == 0.0


def test_judge_fallback_on_llm_exception() -> None:
    from evals.judge import judge_answer

    llm = MagicMock()
    llm.timed_complete.side_effect = RuntimeError("API error")
    score = judge_answer(
        question_id="q004",
        question="Q?",
        reference="R.",
        context="C.",
        answer="A.",
        llm=llm,
        model="gemini-2.5-flash",
    )
    assert score.error != ""
    assert score.correctness == 0.0


# ---------------------------------------------------------------------------
# run_evals helpers
# ---------------------------------------------------------------------------


def test_load_qa_pairs_no_filter() -> None:
    from evals.run_evals import load_qa_pairs

    pairs = load_qa_pairs()
    assert len(pairs) >= 25


def test_load_qa_pairs_with_filter() -> None:
    from evals.run_evals import load_qa_pairs

    pairs = load_qa_pairs(ids=["q001", "q005"])
    assert len(pairs) == 2
    assert {p["id"] for p in pairs} == {"q001", "q005"}


def test_load_qa_pairs_empty_filter() -> None:
    from evals.run_evals import load_qa_pairs

    pairs = load_qa_pairs(ids=["qXXX"])
    assert pairs == []


def test_sample_contracts_cover_all_doc_ids() -> None:
    from evals.run_evals import _SAMPLE_CONTRACTS, load_qa_pairs

    pairs = load_qa_pairs()
    doc_ids_in_pairs = {p["doc_id"] for p in pairs}
    missing = doc_ids_in_pairs - set(_SAMPLE_CONTRACTS.keys())
    assert not missing, f"Sample contracts missing for doc_ids: {missing}"


def test_sample_contracts_are_non_empty() -> None:
    from evals.run_evals import _SAMPLE_CONTRACTS

    for doc_id, text in _SAMPLE_CONTRACTS.items():
        assert len(text.strip()) > 200, f"Contract text for {doc_id} is too short"
