"""
goveval/eval/faithfulness.py
Metric 3 — Faithfulness / Answer Quality.

Four dimensions scored 1-5 each:
  Accuracy      — factual correctness vs KB
  Completeness  — all key points from KB covered
  Clarity       — plain language, no jargon
  Actionability — tells user what to do next

Final score = mean of four dimension scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class FaithfulnessResult:
    accuracy_score: int          # 1-5
    completeness_score: int      # 1-5
    clarity_score: int           # 1-5
    actionability_score: int     # 1-5
    overall_score: float         # mean of four
    explanation: str
    improvement_hints: list[str]
    raw_judge_output: dict


JUDGE_PROMPT = """\
Score this government chatbot response on four dimensions.

QUESTION: {question}
RESPONSE: {response}
SOURCE CHUNKS:
{chunks}

Score each dimension 1-5. Use ONLY the source chunks as ground truth.

ACCURACY (1-5):
  5 — every claim matches chunks exactly
  3 — mostly correct, minor imprecision
  1 — key facts wrong or fabricated

COMPLETENESS (1-5):
  5 — all relevant information from chunks included
  3 — main points covered, minor gaps
  1 — major relevant information omitted

CLARITY (1-5):
  5 — plain language, well-structured, no unexplained jargon
  3 — understandable but could be cleaner
  1 — confusing, jargon-heavy, or poorly structured

ACTIONABILITY (1-5):
  5 — user knows exactly what to do next (links, numbers, steps)
  3 — partial next steps given
  1 — no guidance on what user should do

Return ONLY valid JSON (no fences):
{{
  "accuracy_score": <1-5>,
  "completeness_score": <1-5>,
  "clarity_score": <1-5>,
  "actionability_score": <1-5>,
  "overall_score": <float>,
  "explanation": "<two sentences>",
  "improvement_hints": ["<hint 1>", "<hint 2>"]
}}
"""


def score(
    question_text: str,
    response_text: str,
    chunks: list[dict],
    llm_client,
) -> FaithfulnessResult:
    """Score response on four faithfulness dimensions using LLM judge."""
    from goveval.utils.json_utils import extract_json

    chunk_text = (
        "\n".join(f"[{c['chunk_id']}] {c['text']}" for c in chunks)
        if chunks
        else "(no source chunks provided)"
    )
    prompt = JUDGE_PROMPT.format(
        question=question_text,
        response=response_text,
        chunks=chunk_text,
    )
    raw = llm_client.complete(prompt, max_tokens=800)
    data = extract_json(raw)

    acc = int(data.get("accuracy_score", 3))
    comp = int(data.get("completeness_score", 3))
    clar = int(data.get("clarity_score", 3))
    act = int(data.get("actionability_score", 3))
    overall = round((acc + comp + clar + act) / 4, 2)

    return FaithfulnessResult(
        accuracy_score=acc,
        completeness_score=comp,
        clarity_score=clar,
        actionability_score=act,
        overall_score=overall,
        explanation=data.get("explanation", ""),
        improvement_hints=data.get("improvement_hints", []),
        raw_judge_output=data,
    )


def aggregate(results: list[FaithfulnessResult]) -> dict:
    """
    Aggregate faithfulness scores across a batch.

    Returns:
      {accuracy_avg, completeness_avg, clarity_avg, actionability_avg,
       overall_avg, score_distribution, worst_responses}
    """
    if not results:
        return {
            "accuracy_avg": 0.0, "completeness_avg": 0.0,
            "clarity_avg": 0.0, "actionability_avg": 0.0,
            "overall_avg": 0.0, "score_distribution": {}, "worst_responses": [],
        }
    n = len(results)
    return {
        "accuracy_avg": round(sum(r.accuracy_score for r in results) / n, 2),
        "completeness_avg": round(sum(r.completeness_score for r in results) / n, 2),
        "clarity_avg": round(sum(r.clarity_score for r in results) / n, 2),
        "actionability_avg": round(sum(r.actionability_score for r in results) / n, 2),
        "overall_avg": round(sum(r.overall_score for r in results) / n, 2),
        "score_distribution": {
            str(s): sum(1 for r in results if int(r.overall_score) == s)
            for s in range(1, 6)
        },
        "worst_responses": sorted(results, key=lambda r: r.overall_score)[:3],
    }
