"""Tests for model router — task routing and complexity heuristics.

No API calls; pure logic.
"""

from __future__ import annotations

import pytest
from app.llm.router import TaskType, classify_query_task, route

CHEAP = "gemini-2.5-flash-lite"
STRONG = "gemini-2.5-flash"


# ---- task-type routing ----

@pytest.mark.parametrize("task", [TaskType.EXTRACT, TaskType.SUMMARIZE])
def test_cheap_tasks_go_to_cheap_model(task: TaskType) -> None:
    model, reason = route(task, CHEAP, STRONG)
    assert model == CHEAP
    assert "cheap" in reason


@pytest.mark.parametrize("task", [TaskType.RISK, TaskType.COMPARE, TaskType.JUDGE])
def test_strong_tasks_go_to_strong_model(task: TaskType) -> None:
    model, reason = route(task, CHEAP, STRONG)
    assert model == STRONG
    assert "strong" in reason


def test_simple_qa_short_plain_is_cheap() -> None:
    model, _ = route(TaskType.SIMPLE_QA, CHEAP, STRONG, query="What is the payment amount?")
    assert model == CHEAP


def test_simple_qa_long_query_upgrades_to_strong() -> None:
    long_q = "What is the payment amount? " * 12  # > 200 chars
    model, reason = route(TaskType.SIMPLE_QA, CHEAP, STRONG, query=long_q)
    assert model == STRONG
    assert reason == "qa_length_threshold"


def test_simple_qa_complex_keyword_upgrades_to_strong() -> None:
    model, reason = route(
        TaskType.SIMPLE_QA, CHEAP, STRONG,
        query="Compare the liability caps in section 7 and section 9"
    )
    assert model == STRONG
    assert reason == "qa_complexity_keyword"


def test_complex_qa_always_strong() -> None:
    model, _ = route(TaskType.COMPLEX_QA, CHEAP, STRONG, query="anything")
    assert model == STRONG


# ---- classify_query_task ----

def test_classify_factual_who() -> None:
    assert classify_query_task("Who are the parties to this agreement?") == TaskType.SIMPLE_QA


def test_classify_factual_when() -> None:
    assert classify_query_task("When does the agreement expire?") == TaskType.SIMPLE_QA


def test_classify_complex_keyword() -> None:
    result = classify_query_task("Explain why the indemnification clause is unusual")
    assert result == TaskType.COMPLEX_QA


def test_classify_long_question_is_complex() -> None:
    long_q = "What does this contract say about payment " * 6
    assert classify_query_task(long_q) == TaskType.COMPLEX_QA


def test_classify_compare_keyword() -> None:
    result = classify_query_task("Compare the termination rights of each party")
    assert result == TaskType.COMPLEX_QA
