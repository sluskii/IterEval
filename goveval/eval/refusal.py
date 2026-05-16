"""
goveval/eval/refusal.py
Metric 2 — Refusal Precision + Recall.
Metric 4 — Refusal Appropriateness.

Metric 2: Does the bot know what it doesn't know?
  Precision = True Refusals / All Refusals
  Recall    = True Refusals / Should-Have-Refused

Metric 4: When it does refuse, is the refusal helpful?
  Penalises unnecessary refusals and poor-quality redirects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class RefusalClassification:
    classification: str         # FULL_REFUSAL | PARTIAL_ATTEMPT | CONFIDENT_ANSWER
    explanation: str
    refusal_language: Optional[str]


@dataclass
class RefusalAppropriateness:
    was_refusal_necessary: bool
    explanation: str
    refusal_quality_score: Optional[int]    # 1-5, None if no refusal
    unnecessary_refusal_harm: Optional[str] # LOW | MEDIUM | HIGH, None if necessary
    recommendation: Optional[str]


CLASSIFY_PROMPT = """\
Classify whether this government chatbot refused to answer.

QUESTION: {question}
RESPONSE: {response}

A REFUSAL is:
  - Explicit: "I don't know", "I can't answer that", "I'm unable to find..."
  - Redirect: "Please contact [agency] directly"
A PARTIAL_ATTEMPT hedges but still answers ("I'm not certain, but...")
A CONFIDENT_ANSWER answers without hedging.

Return ONLY valid JSON:
{{
  "classification": "FULL_REFUSAL|PARTIAL_ATTEMPT|CONFIDENT_ANSWER",
  "explanation": "<one sentence>",
  "refusal_language": "<quoted refusal text or null>"
}}
"""

APPROPRIATENESS_PROMPT = """\
Evaluate whether this chatbot refusal was appropriate.

QUESTION: {question}
RESPONSE: {response}
SOURCE CHUNKS: {chunks}
ANSWER_IN_KB: {answer_in_kb}

1. WAS_REFUSAL_NECESSARY:
   YES if answer genuinely not in KB. NO if answer was available.

2. REFUSAL_QUALITY (1-5 if refused):
   5 — explains why + specific redirect + next step
   3 — some explanation or redirect but incomplete
   1 — bare "I don't know" with nothing useful

3. UNNECESSARY_REFUSAL_HARM (if not necessary):
   LOW | MEDIUM | HIGH

Return ONLY valid JSON:
{{
  "was_refusal_necessary": true|false,
  "explanation": "<one sentence>",
  "refusal_quality_score": <1-5 or null>,
  "unnecessary_refusal_harm": "LOW|MEDIUM|HIGH|null",
  "recommendation": "<what it should have said or null>"
}}
"""


def classify_refusal(
    question_text: str,
    response_text: str,
    llm_client,
) -> RefusalClassification:
    """Determine if the response is a refusal, partial attempt, or confident answer."""
    from goveval.utils.json_utils import extract_json

    prompt = CLASSIFY_PROMPT.format(question=question_text, response=response_text)
    raw = llm_client.complete(prompt, max_tokens=400)
    data = extract_json(raw)

    return RefusalClassification(
        classification=data.get("classification", "CONFIDENT_ANSWER"),
        explanation=data.get("explanation", ""),
        refusal_language=data.get("refusal_language"),
    )


def assess_appropriateness(
    question_text: str,
    response_text: str,
    chunks: list[dict],
    answer_in_kb: bool,
    llm_client,
) -> RefusalAppropriateness:
    """Evaluate quality and necessity of a refusal."""
    from goveval.utils.json_utils import extract_json

    chunk_text = (
        "\n".join(f"[{c['chunk_id']}] {c['text']}" for c in chunks)
        if chunks
        else "(no source chunks)"
    )
    prompt = APPROPRIATENESS_PROMPT.format(
        question=question_text,
        response=response_text,
        chunks=chunk_text,
        answer_in_kb=str(answer_in_kb).lower(),
    )
    raw = llm_client.complete(prompt, max_tokens=500)
    data = extract_json(raw)

    harm = data.get("unnecessary_refusal_harm")
    if harm == "null":
        harm = None

    return RefusalAppropriateness(
        was_refusal_necessary=bool(data.get("was_refusal_necessary", True)),
        explanation=data.get("explanation", ""),
        refusal_quality_score=data.get("refusal_quality_score"),
        unnecessary_refusal_harm=harm,
        recommendation=data.get("recommendation"),
    )


def compute_refusal_metrics(
    classifications: list[RefusalClassification],
    ground_truth_should_refuse: list[bool],
) -> dict:
    """
    Compute precision, recall, F1 from a batch of classifications.

    Returns:
      {precision, recall, f1, true_refusals, false_refusals,
       missed_refusals, unnecessary_refusals}
    """
    if not classifications:
        return {
            "precision": 0.0, "recall": 0.0, "f1": 0.0,
            "true_refusals": 0, "false_refusals": 0,
            "missed_refusals": 0, "unnecessary_refusals": 0,
        }

    tp = fp = fn = tn = 0
    for cls, gt_refuse in zip(classifications, ground_truth_should_refuse):
        predicted = cls.classification == "FULL_REFUSAL"
        if predicted and gt_refuse:
            tp += 1
        elif predicted and not gt_refuse:
            fp += 1
        elif not predicted and gt_refuse:
            fn += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "true_refusals": tp,
        "false_refusals": fp,
        "missed_refusals": fn,
        "unnecessary_refusals": fp,
    }
