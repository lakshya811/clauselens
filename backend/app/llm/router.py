"""Model router — cheap vs strong model selection.

Routing logic (interview answer):
  "I route on two axes: task type and query complexity. Task type is the
  primary signal — extraction and simple QA are deterministic/low-reasoning
  tasks where the cheap model (flash-lite) is sufficient. Risk reasoning and
  version comparison involve multi-step legal inference, so they always go to
  the strong model (flash). For QA, I add a complexity heuristic: question
  length and presence of multi-hop keywords (compare, explain why, what if)
  push it to the strong model. The routing rules are explicit and documented,
  not a black box, so I can justify every routing decision in a postmortem."

Task taxonomy:
  CHEAP  → extract, simple_qa, summarize
  STRONG → risk, compare, complex_qa, judge (LLM-as-Judge eval)
"""

from __future__ import annotations

import re
from enum import Enum


class TaskType(str, Enum):
    EXTRACT = "extract"        # structured clause extraction
    SUMMARIZE = "summarize"    # document summary
    SIMPLE_QA = "simple_qa"   # short factual Q&A (who, when, what amount)
    COMPLEX_QA = "complex_qa"  # multi-hop / reasoning Q&A
    RISK = "risk"              # risk flag identification
    COMPARE = "compare"        # version diff classification
    JUDGE = "judge"            # LLM-as-Judge scoring


# Tasks routed to the cheap model by default.
_CHEAP_TASKS = {TaskType.EXTRACT, TaskType.SUMMARIZE, TaskType.SIMPLE_QA}

# Keywords in the user question that signal complex reasoning → strong model.
_COMPLEX_KEYWORDS_RE = re.compile(
    r"\b(compare|contrast|explain why|why does|what if|how does|analyse|analyze"
    r"|implication|consequence|difference between|risk of|liable|indemnif)\b",
    re.IGNORECASE,
)

# Questions longer than this (chars) are sent to the strong model regardless.
_COMPLEXITY_CHAR_THRESHOLD = 200


def route(
    task: TaskType,
    model_cheap: str,
    model_strong: str,
    query: str = "",
) -> tuple[str, str]:
    """Select a model for the given task + query.

    Returns:
        (model_name, reason) — reason is logged to the observability JSONL.
    """
    if task in _CHEAP_TASKS:
        if task == TaskType.SIMPLE_QA:
            # Upgrade simple_qa if the question looks complex.
            if len(query) > _COMPLEXITY_CHAR_THRESHOLD:
                return model_strong, "qa_length_threshold"
            if _COMPLEX_KEYWORDS_RE.search(query):
                return model_strong, "qa_complexity_keyword"
        return model_cheap, f"task_{task.value}_cheap"

    return model_strong, f"task_{task.value}_strong"


def classify_query_task(query: str) -> TaskType:
    """Heuristically classify a free-text Q&A query into a TaskType.

    Used when the caller doesn't supply an explicit task — e.g. the chat route
    receives a user message and needs to route it without knowing intent upfront.
    """
    q = query.lower()

    if _COMPLEX_KEYWORDS_RE.search(q):
        return TaskType.COMPLEX_QA

    # Short factual patterns → simple_qa
    if re.search(r"\b(who|when|what (is|are|was|were)|how much|how many)\b", q):
        if len(query) < _COMPLEXITY_CHAR_THRESHOLD:
            return TaskType.SIMPLE_QA

    if len(query) > _COMPLEXITY_CHAR_THRESHOLD:
        return TaskType.COMPLEX_QA

    return TaskType.SIMPLE_QA
