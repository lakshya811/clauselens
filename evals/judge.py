"""LLM-as-Judge for RAG Q&A evaluation.

Three dimensions scored 1-5 each:
  correctness   — does the answer convey the same facts as the reference?
  groundedness  — is every claim supported by the provided context?
  citation_acc  — are the citations specific, accurate, and useful?

Interview answer:
  "I use the same model that powers the app (Gemini flash) as the judge,
  but with a structured rubric so scores are reproducible. Each dimension
  is scored 1–5 with explicit anchors in the prompt (e.g. 5 = all facts
  correct, 1 = major factual errors). I ask for a brief reasoning string
  alongside each score so I can spot systematic failure modes — e.g. the
  model answers correctly but cites the wrong section. The judge runs as
  a separate Python script so it can be wired into CI via `make eval`."
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_JUDGE_SYSTEM = """You are an impartial evaluator for an AI contract analysis system.
You will be given:
  - QUESTION: the user's question
  - REFERENCE: the ground-truth answer written by a human expert
  - CONTEXT: the contract excerpts the system retrieved
  - ANSWER: the system's generated answer

Score the answer on three dimensions, each from 1 to 5:

correctness (1-5):
  5 = All facts match the reference; no omissions or additions that change meaning.
  4 = Mostly correct; minor omissions or imprecise wording that doesn't mislead.
  3 = Partially correct; some facts right, some wrong or missing.
  2 = Mostly incorrect or incomplete in ways that would mislead the reader.
  1 = Factually wrong or completely off-topic.

groundedness (1-5):
  5 = Every claim is explicitly supported by the provided context.
  4 = Nearly all claims are grounded; one minor unsupported statement.
  3 = Some claims are grounded; others go beyond the context.
  2 = Most claims are not supported by the provided context.
  1 = Answer ignores the context entirely or contradicts it.

citation_accuracy (1-5):
  5 = All citations are specific (clause/section reference), accurate,
      and map to the correct excerpt.
  4 = Citations are mostly accurate; one is vague or slightly off.
  3 = Some citations present and correct; others missing or inaccurate.
  2 = Citations are present but largely wrong, missing, or not specific.
  1 = No citations at all, or citations are fabricated.

Return ONLY valid JSON in this exact format (no markdown, no extra keys):
{
  "correctness": <1-5>,
  "groundedness": <1-5>,
  "citation_accuracy": <1-5>,
  "reasoning": "<one sentence per dimension, semicolon-separated>"
}"""

_JUDGE_USER = """QUESTION: {question}

REFERENCE: {reference}

CONTEXT:
{context}

ANSWER: {answer}"""


@dataclass
class JudgeScore:
    question_id: str
    correctness: float = 0.0
    groundedness: float = 0.0
    citation_accuracy: float = 0.0
    reasoning: str = ""
    error: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    @property
    def mean(self) -> float:
        return (self.correctness + self.groundedness + self.citation_accuracy) / 3


def judge_answer(
    *,
    question_id: str,
    question: str,
    reference: str,
    context: str,
    answer: str,
    llm,  # LLMProvider
    model: str,
) -> JudgeScore:
    """Score a single (question, answer, context) triple.

    Returns a JudgeScore with 1-5 scores on three dimensions.
    On any failure, returns a JudgeScore with error field populated and scores = 0.
    """
    from app.llm.provider import Message

    user_msg = _JUDGE_USER.format(
        question=question,
        reference=reference,
        context=context,
        answer=answer,
    )

    try:
        resp = llm.timed_complete(
            messages=[Message(role="user", content=user_msg)],
            model=model,
            system_prompt=_JUDGE_SYSTEM,
            temperature=0.0,
        )
        raw = resp.content.strip()
        # Strip potential markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)

        return JudgeScore(
            question_id=question_id,
            correctness=float(data["correctness"]),
            groundedness=float(data["groundedness"]),
            citation_accuracy=float(data["citation_accuracy"]),
            reasoning=data.get("reasoning", ""),
            model=model,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            cost_usd=resp.cost_usd,
        )
    except Exception as exc:
        logger.exception("Judge failed for question %s", question_id)
        return JudgeScore(question_id=question_id, error=str(exc), model=model)
