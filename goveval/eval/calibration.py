"""
goveval/eval/calibration.py
Metric 6 — Confidence Calibration.

Measures Expected Calibration Error (ECE): whether the bot's expressed
confidence matches its actual accuracy.

Process:
  1. Extract confidence level from response language (HIGH/MEDIUM/LOW)
  2. Map to numeric probability (0.9 / 0.6 / 0.3)
  3. Compare to binary accuracy (correct/incorrect per hallucination judge)
  4. Compute ECE = Σ |confidence - accuracy| * bucket_weight
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ConfidenceExtraction:
    response_id: str
    expressed_confidence: str    # HIGH | MEDIUM | LOW | NONE
    confidence_probability: float
    confidence_language: Optional[str]  # quoted hedging phrase


@dataclass
class CalibrationResult:
    ece: float                              # Expected Calibration Error (0-1, lower is better)
    mean_confidence: float                  # mean of all expressed confidences
    mean_accuracy: float                    # mean of actual correctness
    overconfidence_rate: float              # fraction where confidence >> accuracy
    underconfidence_rate: float             # fraction where confidence << accuracy
    calibration_curve: list[dict]           # [{bucket, confidence, accuracy, count}]
    reliability_verdict: str               # WELL_CALIBRATED | OVERCONFIDENT | UNDERCONFIDENT


CONFIDENCE_EXTRACT_PROMPT = """\
Extract the confidence level expressed in this government chatbot response.

RESPONSE: {response}

Look for hedging language:
  HIGH confidence: "The subsidy is...", "You are eligible for...", definitive statements
  MEDIUM confidence: "Generally...", "Typically...", "Based on the information..."
  LOW confidence: "I'm not certain...", "You may want to verify...", "I believe..."
  NONE: no confidence signal (e.g., refusals)

Return ONLY valid JSON:
{{
  "expressed_confidence": "HIGH|MEDIUM|LOW|NONE",
  "confidence_language": "<quoted phrase or null>"
}}
"""

_PROB_MAP = {"HIGH": 0.9, "MEDIUM": 0.6, "LOW": 0.3, "NONE": None}


def extract_confidence(
    response_text: str,
    response_id: str,
    llm_client,
) -> ConfidenceExtraction:
    """Extract expressed confidence level from a response."""
    from goveval.utils.json_utils import extract_json

    prompt = CONFIDENCE_EXTRACT_PROMPT.format(response=response_text)
    raw = llm_client.complete(prompt, max_tokens=300)
    data = extract_json(raw)

    conf = data.get("expressed_confidence", "NONE")
    prob = _PROB_MAP.get(conf, None)

    return ConfidenceExtraction(
        response_id=response_id,
        expressed_confidence=conf,
        confidence_probability=prob if prob is not None else 0.5,
        confidence_language=data.get("confidence_language"),
    )


def compute_ece(
    confidences: list[ConfidenceExtraction],
    correct_flags: list[bool],
    n_buckets: int = 5,
) -> CalibrationResult:
    """
    Compute Expected Calibration Error and full calibration curve.

    Confidence → probability mapping:
      HIGH → 0.9, MEDIUM → 0.6, LOW → 0.3, NONE → excluded
    """
    import numpy as np

    pairs = [
        (c.confidence_probability, float(cf))
        for c, cf in zip(confidences, correct_flags)
        if c.expressed_confidence != "NONE"
    ]

    if not pairs:
        return CalibrationResult(
            ece=0.0, mean_confidence=0.5, mean_accuracy=0.5,
            overconfidence_rate=0.0, underconfidence_rate=0.0,
            calibration_curve=[], reliability_verdict="WELL_CALIBRATED",
        )

    confs = np.array([p[0] for p in pairs])
    accs = np.array([p[1] for p in pairs])

    bucket_edges = np.linspace(0, 1, n_buckets + 1)
    ece = 0.0
    curve = []
    for i in range(n_buckets):
        lo, hi = bucket_edges[i], bucket_edges[i + 1]
        mask = (confs >= lo) & (confs <= hi if i == n_buckets - 1 else confs < hi)
        if mask.sum() == 0:
            continue
        b_conf = float(confs[mask].mean())
        b_acc = float(accs[mask].mean())
        weight = mask.sum() / len(pairs)
        ece += abs(b_conf - b_acc) * weight
        curve.append({
            "bucket": f"{lo:.1f}-{hi:.1f}",
            "confidence": round(b_conf, 3),
            "accuracy": round(b_acc, 3),
            "count": int(mask.sum()),
        })

    mean_conf = float(confs.mean())
    mean_acc = float(accs.mean())
    over_rate = float(((confs - accs) > 0.2).mean())
    under_rate = float(((accs - confs) > 0.2).mean())

    return CalibrationResult(
        ece=round(ece, 4),
        mean_confidence=round(mean_conf, 3),
        mean_accuracy=round(mean_acc, 3),
        overconfidence_rate=round(over_rate, 3),
        underconfidence_rate=round(under_rate, 3),
        calibration_curve=curve,
        reliability_verdict=calibration_verdict(ece),
    )


def calibration_verdict(ece: float) -> str:
    """Map ECE value to reliability verdict."""
    if ece < 0.10:
        return "WELL_CALIBRATED"
    elif ece < 0.20:
        return "OVERCONFIDENT"
    else:
        return "UNDERCONFIDENT"
