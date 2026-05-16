"""
goveval/eval/hallucination.py
Metric 1 — Hallucination Rate.

Judge decomposes the response into atomic claims, checks each against
source chunks, and labels: SUPPORTED | UNSUPPORTED | CANNOT_DETERMINE.

Score = UNSUPPORTED / (SUPPORTED + UNSUPPORTED)
Cannot-determine cases excluded from denominator, reported separately.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Claim:
    text: str
    verdict: str            # SUPPORTED | UNSUPPORTED | CANNOT_DETERMINE
    explanation: str
    source_chunk_id: Optional[str]


@dataclass
class HallucinationResult:
    claims: List[Claim]
    hallucination_rate: float       # UNSUPPORTED / (SUP + UNSUP)
    cannot_determine_rate: float    # CANNOT_DETERMINE / total_claims
    overall_assessment: str
    raw_judge_output: dict


JUDGE_PROMPT = """\
You are evaluating whether a Singapore government chatbot hallucinated.

QUESTION: {question}
RESPONSE: {response}
SOURCE CHUNKS:
{chunks}

IMPORTANT — REFUSAL HANDLING:
If the response is a refusal, deflection, or acknowledgement of uncertainty
(e.g. "I don't have information", "I cannot answer", "Please visit the website",
"I'm not sure", "I don't know"), it makes NO verifiable factual claims.
Return an empty claims list with hallucination_rate=0.0 and overall_assessment="Refusal — no factual claims made."

Otherwise:

STEP 1 — Extract every distinct factual claim from the response.
A claim is any verifiable statement (amounts, dates, eligibility rules, programme names).
Do NOT extract meta-statements like "I don't know" or "please check" as claims.
List them numbered.

STEP 2 — For each claim, check ONLY the source chunks provided.
Do NOT use outside knowledge. Label each:
  SUPPORTED          — directly stated or clearly implied by a chunk
  UNSUPPORTED        — contradicts chunks or has no basis in chunks
  CANNOT_DETERMINE   — insufficient information in chunks to judge

STEP 3 — For each UNSUPPORTED claim, explain in one sentence why.

STEP 4 — Return ONLY valid JSON (no fences):
{{
  "claims": [
    {{
      "claim": "<claim text>",
      "verdict": "SUPPORTED|UNSUPPORTED|CANNOT_DETERMINE",
      "explanation": "<one sentence>",
      "source_chunk_id": "<chunk_id or null>"
    }}
  ],
  "hallucination_rate": <float 0-1>,
  "cannot_determine_rate": <float 0-1>,
  "overall_assessment": "<one sentence>"
}}
"""

_REFUSAL_CHECK_PROMPT = """\
Does the following chatbot response make any verifiable factual claims, or is it \
purely a refusal, deflection, or acknowledgement of uncertainty with no factual content?

RESPONSE: {response}

Answer with a single word — REFUSAL or FACTUAL — and nothing else."""


def _is_refusal(response_text: str, llm_client) -> bool:
    """Return True if the LLM judges the response as a refusal with no factual claims."""
    raw = llm_client.complete(
        _REFUSAL_CHECK_PROMPT.format(response=response_text),
        max_tokens=5,
    )
    return raw.strip().upper().startswith("REFUSAL")


def judge(
    question_text: str,
    response_text: str,
    chunks: list[dict],
    llm_client,
) -> HallucinationResult:
    """
    Call LLM judge and parse result into HallucinationResult.
    chunks: list of {chunk_id, text} dicts from KB retrieval.
    """
    from goveval.utils.json_utils import extract_json

    # Short-circuit: refusals/deflections make no factual claims → 0% hallucination
    if _is_refusal(response_text, llm_client):
        return HallucinationResult(
            claims=[],
            hallucination_rate=0.0,
            cannot_determine_rate=0.0,
            overall_assessment="Refusal — no factual claims made.",
            raw_judge_output={"refusal_detected": True},
        )

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
    raw = llm_client.complete(prompt, max_tokens=2000)
    data = extract_json(raw)

    claims = [
        Claim(
            text=c["claim"],
            verdict=c["verdict"],
            explanation=c.get("explanation", ""),
            source_chunk_id=c.get("source_chunk_id"),
        )
        for c in data.get("claims", [])
    ]

    # Recompute rates from parsed claims (don't trust LLM's own arithmetic)
    n_unsup = sum(1 for c in claims if c.verdict == "UNSUPPORTED")
    n_sup = sum(1 for c in claims if c.verdict == "SUPPORTED")
    n_cannot = sum(1 for c in claims if c.verdict == "CANNOT_DETERMINE")
    denom = n_sup + n_unsup
    hall_rate = n_unsup / denom if denom > 0 else 0.0
    cannot_rate = n_cannot / len(claims) if claims else 0.0

    return HallucinationResult(
        claims=claims,
        hallucination_rate=round(hall_rate, 4),
        cannot_determine_rate=round(cannot_rate, 4),
        overall_assessment=data.get("overall_assessment", ""),
        raw_judge_output=data,
    )
