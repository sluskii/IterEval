"""
tests/test_judge_validator.py
Unit tests for judge_validator.py — kappa computation and reliability tiers.
"""

from __future__ import annotations
import pytest
from goveval.eval.judge_validator import reliability_from_kappa, KappaResult, compute_kappa


# ── reliability_from_kappa ────────────────────────────────────────────────────

def test_high_reliability():
    assert reliability_from_kappa(0.85) == "HIGH"
    assert reliability_from_kappa(0.80) == "HIGH"


def test_moderate_reliability():
    assert reliability_from_kappa(0.70) == "MODERATE"
    assert reliability_from_kappa(0.60) == "MODERATE"


def test_low_reliability():
    assert reliability_from_kappa(0.59) == "LOW"
    assert reliability_from_kappa(0.0) == "LOW"
    assert reliability_from_kappa(-0.1) == "LOW"


# ── KappaResult dataclass ─────────────────────────────────────────────────────

def test_kappa_result_fields():
    kr = KappaResult(
        metric="hallucination",
        kappa=0.75,
        agreement_rate=0.87,
        n_samples=30,
        confusion_matrix=[[10, 2], [1, 17]],
        reliability="MODERATE",
        human_labels=[0, 1, 0, 1],
        judge_labels=[0, 1, 0, 0],
    )
    assert kr.metric == "hallucination"
    assert kr.reliability == "MODERATE"
    assert kr.n_samples == 30


# ── compute_kappa ─────────────────────────────────────────────────────────────

def test_compute_kappa_empty_raises():
    with pytest.raises(ValueError, match="No labels"):
        compute_kappa([], [], "hallucination")


def test_compute_kappa_mismatched_length_raises():
    with pytest.raises(ValueError, match="same length"):
        compute_kappa([0, 1], [0], "hallucination")


def test_compute_kappa_perfect_agreement():
    human  = [0, 0, 1, 1, 0, 1]
    judge  = [0, 0, 1, 1, 0, 1]
    result = compute_kappa(human, judge, "hallucination")
    assert result.kappa == pytest.approx(1.0)
    assert result.agreement_rate == pytest.approx(1.0)
    assert result.reliability == "HIGH"
    assert result.n_samples == 6


def test_compute_kappa_total_disagreement():
    human = [0, 0, 0, 1, 1, 1]
    judge = [1, 1, 1, 0, 0, 0]
    result = compute_kappa(human, judge)
    assert result.kappa < 0          # worse than chance
    assert result.reliability == "LOW"


def test_compute_kappa_moderate_agreement():
    # 80% raw agreement → kappa depends on base rates but should be MODERATE+
    human = [0, 0, 1, 1, 0, 1, 0, 0, 1, 1]
    judge = [0, 0, 1, 1, 0, 1, 0, 1, 1, 0]  # 2 wrong out of 10
    result = compute_kappa(human, judge)
    assert result.agreement_rate == pytest.approx(0.8)
    assert result.n_samples == 10


def test_compute_kappa_confusion_matrix_shape():
    human = [0, 1, 0, 1]
    judge = [0, 1, 1, 0]
    result = compute_kappa(human, judge)
    cm = result.confusion_matrix
    assert len(cm) == 2
    assert len(cm[0]) == 2
    assert sum(cm[0]) + sum(cm[1]) == 4  # all samples accounted for


def test_compute_kappa_stores_labels():
    human = [0, 1, 0]
    judge = [0, 0, 0]
    result = compute_kappa(human, judge)
    assert result.human_labels == human
    assert result.judge_labels == judge
