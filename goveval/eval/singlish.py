"""
goveval/eval/singlish.py
Metric 5 — Singlish / Dialect Gap.

Compares bot performance on Singlish questions vs their standard-English
equivalents. Flags where dialect causes degraded retrieval or response quality.

Gap = mean(standard_scores) - mean(singlish_scores)
Threshold: gap > 0.15 → alert.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SinglishPairResult:
    standard_question_id: str
    singlish_question_id: str
    standard_score: float       # 0-1, faithfulness or correctness
    singlish_score: float       # 0-1
    gap: float                  # standard - singlish (positive = singlish worse)
    degradation_reason: Optional[str]


@dataclass
class SinglishGapReport:
    pairs: list[SinglishPairResult]
    mean_standard_score: float
    mean_singlish_score: float
    gap: float
    gap_alert: bool             # True if gap > threshold
    worst_pairs: list[SinglishPairResult]


DIALECT_JUDGE_PROMPT = """\
A Singapore government chatbot received two versions of the same question:
one in standard English, one in Singlish/colloquial phrasing.

STANDARD QUESTION: {standard_question}
STANDARD RESPONSE: {standard_response}

SINGLISH QUESTION: {singlish_question}
SINGLISH RESPONSE: {singlish_response}

SOURCE CHUNKS:
{chunks}

Evaluate:
1. Did the bot understand the Singlish question correctly?
2. Is the Singlish response as complete and accurate as the standard response?
3. If quality differs, what caused the gap? (retrieval failure, misunderstanding, etc.)

Score each response 0.0–1.0 on overall quality relative to the source chunks.

Return ONLY valid JSON:
{{
  "standard_score": <0.0-1.0>,
  "singlish_score": <0.0-1.0>,
  "understood_singlish": true|false,
  "quality_gap_reason": "<one sentence or null>",
  "recommendation": "<how to improve Singlish handling or null>"
}}
"""


def compute_pair_gap(
    standard_question: str,
    standard_response: str,
    singlish_question: str,
    singlish_response: str,
    chunks: list[dict],
    standard_question_id: str,
    singlish_question_id: str,
    llm_client,
) -> SinglishPairResult:
    """Evaluate one Singlish/standard pair and compute gap."""
    from goveval.utils.json_utils import extract_json

    chunk_text = (
        "\n".join(f"[{c['chunk_id']}] {c['text']}" for c in chunks)
        if chunks
        else "(no source chunks)"
    )
    prompt = DIALECT_JUDGE_PROMPT.format(
        standard_question=standard_question,
        standard_response=standard_response,
        singlish_question=singlish_question,
        singlish_response=singlish_response,
        chunks=chunk_text,
    )
    raw = llm_client.complete(prompt, max_tokens=600)
    data = extract_json(raw)

    std_score = float(data.get("standard_score", 0.5))
    sin_score = float(data.get("singlish_score", 0.5))

    return SinglishPairResult(
        standard_question_id=standard_question_id,
        singlish_question_id=singlish_question_id,
        standard_score=round(std_score, 3),
        singlish_score=round(sin_score, 3),
        gap=round(std_score - sin_score, 3),
        degradation_reason=data.get("quality_gap_reason"),
    )


def compute_gap_report(
    pair_results: list[SinglishPairResult],
    gap_threshold: float = 0.15,
) -> SinglishGapReport:
    """
    Aggregate pair results into a gap report.
    Flags alert if mean gap exceeds threshold.
    """
    if not pair_results:
        return SinglishGapReport(
            pairs=[], mean_standard_score=0.0, mean_singlish_score=0.0,
            gap=0.0, gap_alert=False, worst_pairs=[],
        )

    mean_std = sum(p.standard_score for p in pair_results) / len(pair_results)
    mean_sin = sum(p.singlish_score for p in pair_results) / len(pair_results)
    gap = mean_std - mean_sin
    worst = sorted(pair_results, key=lambda p: p.gap, reverse=True)[:3]

    return SinglishGapReport(
        pairs=pair_results,
        mean_standard_score=round(mean_std, 4),
        mean_singlish_score=round(mean_sin, 4),
        gap=round(gap, 4),
        gap_alert=gap > gap_threshold,
        worst_pairs=worst,
    )


def match_singlish_pairs(
    questions: list,
    responses: list,
) -> list[tuple]:
    """
    Match Singlish questions to their standard equivalents using
    Question.singlish_pair_id field.

    Returns list of (standard_q, singlish_q, standard_r, singlish_r) tuples.
    """
    q_map = {q.question_id: q for q in questions}
    r_map = {r.question_id: r for r in responses}

    pairs = []
    for q in questions:
        if q.language == "singlish" and q.singlish_pair_id:
            std_q = q_map.get(q.singlish_pair_id)
            sin_r = r_map.get(q.question_id)
            std_r = r_map.get(q.singlish_pair_id)
            if std_q and sin_r and std_r:
                pairs.append((std_q, q, std_r, sin_r))
    return pairs
