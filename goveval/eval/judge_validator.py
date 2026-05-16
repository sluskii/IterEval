"""
goveval/eval/judge_validator.py
Inter-rater reliability: Cohen's Kappa between LLM judge and human labels.

Human-in-the-loop workflow:
  1. Dashboard shows a sample of bot responses for a human reviewer to label.
  2. A policy officer labels each as "hallucination" (1) or "clean" (0).
  3. run_judge_on_sample() runs the LLM hallucination judge on the same responses.
  4. compute_kappa() computes Cohen's Kappa + confusion matrix.
  5. validate_judge() wraps steps 3+4 and returns a ValidationReport.

Thresholds (matching HELM and RAGAs convention):
  k >= 0.8 -> HIGH reliability
  k >= 0.6 -> MODERATE reliability
  k <  0.6 -> LOW  reliability -- loop should be paused until judge prompt is revised

See LIMITATIONS.md for known scope constraints.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class KappaResult:
    metric: str
    kappa: float
    agreement_rate: float
    n_samples: int
    confusion_matrix: list[list[int]]   # [[TN, FP], [FN, TP]]
    reliability: str                     # HIGH | MODERATE | LOW
    human_labels: list[int]
    judge_labels: list[int]


@dataclass
class ValidationReport:
    per_metric: list[KappaResult]
    overall_reliability: str
    weak_metrics: list[str]
    recommendation: str
    passed: bool                         # True if all metrics k >= 0.6


RELIABILITY_THRESHOLDS = {
    "HIGH":     0.8,
    "MODERATE": 0.6,
}

DEFAULT_METRICS = ["hallucination"]


def reliability_from_kappa(kappa: float) -> str:
    if kappa >= RELIABILITY_THRESHOLDS["HIGH"]:
        return "HIGH"
    if kappa >= RELIABILITY_THRESHOLDS["MODERATE"]:
        return "MODERATE"
    return "LOW"


def compute_kappa(
    human_labels: list[int],
    judge_labels: list[int],
    metric: str = "hallucination",
) -> KappaResult:
    """
    Compute Cohen's Kappa between human and LLM judge binary labels.

    Labels: 0 = clean/correct, 1 = hallucination/failure.
    Uses sklearn.metrics.cohen_kappa_score (chance-corrected agreement).
    Returns a 2x2 confusion matrix [[TN, FP], [FN, TP]].
    """
    from sklearn.metrics import cohen_kappa_score, confusion_matrix as sk_cm
    import numpy as np

    if len(human_labels) != len(judge_labels):
        raise ValueError(
            f"Label lists must be same length: human={len(human_labels)}, judge={len(judge_labels)}"
        )
    if len(human_labels) == 0:
        raise ValueError("No labels provided.")

    h = np.array(human_labels)
    j = np.array(judge_labels)

    kappa = float(cohen_kappa_score(h, j))
    agreement_rate = float(np.mean(h == j))
    cm = sk_cm(h, j, labels=[0, 1]).tolist()
    reliability = reliability_from_kappa(kappa)

    return KappaResult(
        metric=metric,
        kappa=round(kappa, 4),
        agreement_rate=round(agreement_rate, 4),
        n_samples=len(human_labels),
        confusion_matrix=cm,
        reliability=reliability,
        human_labels=list(h),
        judge_labels=list(j),
    )


def run_judge_on_sample(
    sample: list[dict],
    llm_client,
) -> list[int]:
    """
    Run the LLM hallucination judge on a list of sample dicts.

    Each dict must have "question_text" and "response_text".
    Optionally "chunks": list[dict] for KB grounding.

    Returns binary list: 0=clean, 1=hallucination (rate > 0).
    """
    from goveval.eval.hallucination import judge as hall_judge

    labels: list[int] = []
    for item in sample:
        q_text = item.get("question_text", "")
        r_text = item.get("response_text", "")
        chunks = item.get("chunks") or []
        try:
            result = hall_judge(q_text, r_text, chunks, llm_client)
            labels.append(1 if result.hallucination_rate > 0 else 0)
        except Exception:
            labels.append(0)
    return labels


def validate_judge(
    sample: list[dict],
    human_labels: list[int],
    llm_client,
    metrics: list[str] | None = None,
) -> ValidationReport:
    """
    Full validation pipeline: run LLM judge on sample, compute kappa vs. human labels.

    sample: list of {"question_text", "response_text", optionally "chunks"}
    human_labels: binary list aligned to sample (0=clean, 1=hallucination)
    """
    metrics = metrics or DEFAULT_METRICS
    judge_labels = run_judge_on_sample(sample, llm_client)

    per_metric: list[KappaResult] = []
    for metric in metrics:
        kr = compute_kappa(human_labels, judge_labels, metric=metric)
        per_metric.append(kr)

    return _build_report(per_metric)


def validate_all_metrics(
    human_labels: list[dict],
    judge_labels: list[dict],
    metrics: list[str] | None = None,
) -> ValidationReport:
    """
    Compute kappa per metric from pre-computed label dicts.

    human_labels / judge_labels: list of dicts keyed by metric name -> binary int.
    Example: [{"hallucination": 1}, {"hallucination": 0}, ...]
    """
    metrics = metrics or DEFAULT_METRICS
    per_metric: list[KappaResult] = []
    for metric in metrics:
        h = [d.get(metric, 0) for d in human_labels]
        j = [d.get(metric, 0) for d in judge_labels]
        per_metric.append(compute_kappa(h, j, metric=metric))
    return _build_report(per_metric)


def _build_report(per_metric: list[KappaResult]) -> ValidationReport:
    weak = [kr.metric for kr in per_metric if kr.reliability == "LOW"]
    all_pass = all(kr.kappa >= RELIABILITY_THRESHOLDS["MODERATE"] for kr in per_metric)

    if all_pass:
        tier_rank = {"HIGH": 2, "MODERATE": 1, "LOW": 0}
        overall_reliability = min(
            (kr.reliability for kr in per_metric), key=lambda r: tier_rank[r]
        )
        recommendation = (
            "Judge reliability is sufficient (k >= 0.60). "
            "The automated eval loop may proceed."
        )
    else:
        overall_reliability = "LOW"
        recommendation = (
            f"Judge reliability is LOW for: {', '.join(weak)}. "
            "Revise the judge prompt or increase the human label sample size "
            "before running the automated loop. "
            "k >= 0.60 required; k >= 0.80 recommended."
        )

    return ValidationReport(
        per_metric=per_metric,
        overall_reliability=overall_reliability,
        weak_metrics=weak,
        recommendation=recommendation,
        passed=all_pass,
    )


def save_validation_report(report: ValidationReport, path: str) -> None:
    """Persist ValidationReport as JSON for audit trail."""
    data = {
        "overall_reliability": report.overall_reliability,
        "passed": report.passed,
        "recommendation": report.recommendation,
        "weak_metrics": report.weak_metrics,
        "per_metric": [
            {
                "metric": kr.metric,
                "kappa": kr.kappa,
                "agreement_rate": kr.agreement_rate,
                "n_samples": kr.n_samples,
                "confusion_matrix": kr.confusion_matrix,
                "reliability": kr.reliability,
            }
            for kr in report.per_metric
        ],
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
