"""
tests/test_refusal.py
Unit tests for refusal.py — classification dataclasses and metrics computation.
No real LLM calls; uses a mock client.
"""

from __future__ import annotations
import json
import pytest
from goveval.eval.refusal import (
    RefusalClassification,
    RefusalAppropriateness,
    compute_refusal_metrics,
)


# ── Mock LLM client ────────────────────────────────────────────────────────────

class MockLLMClient:
    def __init__(self, response: dict):
        self._response = json.dumps(response)

    def complete(self, *args, **kwargs) -> str:
        return self._response


# ── Dataclass construction ─────────────────────────────────────────────────────

def test_refusal_classification_types():
    for cls in ("FULL_REFUSAL", "PARTIAL_ATTEMPT", "CONFIDENT_ANSWER"):
        r = RefusalClassification(classification=cls, explanation="test", refusal_language=None)
        assert r.classification == cls


def test_refusal_appropriateness_fields():
    a = RefusalAppropriateness(
        was_refusal_necessary=True,
        explanation="Answer was not in KB.",
        refusal_quality_score=4,
        unnecessary_refusal_harm=None,
        recommendation=None,
    )
    assert a.refusal_quality_score == 4


# ── compute_refusal_metrics ────────────────────────────────────────────────────

def _cls(classification: str) -> RefusalClassification:
    return RefusalClassification(classification=classification, explanation="", refusal_language=None)


def test_empty_input_returns_zeros():
    m = compute_refusal_metrics([], [])
    assert m["precision"] == 0.0
    assert m["recall"] == 0.0
    assert m["f1"] == 0.0


def test_perfect_precision_and_recall():
    clss = [_cls("FULL_REFUSAL"), _cls("FULL_REFUSAL"),
            _cls("CONFIDENT_ANSWER"), _cls("CONFIDENT_ANSWER")]
    gt   = [True, True, False, False]
    m = compute_refusal_metrics(clss, gt)
    assert m["precision"] == pytest.approx(1.0)
    assert m["recall"]    == pytest.approx(1.0)
    assert m["f1"]        == pytest.approx(1.0)


def test_missed_refusal_lowers_recall():
    # Bot answers when it should have refused once
    clss = [_cls("CONFIDENT_ANSWER"), _cls("FULL_REFUSAL"),
            _cls("CONFIDENT_ANSWER"), _cls("CONFIDENT_ANSWER")]
    gt   = [True, True, False, False]
    m = compute_refusal_metrics(clss, gt)
    assert m["recall"] == pytest.approx(0.5)
    assert m["precision"] == pytest.approx(1.0)


def test_unnecessary_refusal_lowers_precision():
    # Bot refuses when it shouldn't once
    clss = [_cls("FULL_REFUSAL"), _cls("FULL_REFUSAL"),
            _cls("FULL_REFUSAL"), _cls("CONFIDENT_ANSWER")]
    gt   = [True, True, False, False]
    m = compute_refusal_metrics(clss, gt)
    assert m["precision"] == pytest.approx(2 / 3, abs=1e-4)
    assert m["recall"]    == pytest.approx(1.0)


def test_all_wrong_zero_metrics():
    clss = [_cls("CONFIDENT_ANSWER"), _cls("CONFIDENT_ANSWER")]
    gt   = [True, True]
    m = compute_refusal_metrics(clss, gt)
    assert m["recall"] == 0.0
    assert m["f1"]     == 0.0


# ── classify_refusal ──────────────────────────────────────────────────────────

def test_classify_refusal_full():
    from goveval.eval.refusal import classify_refusal
    client = MockLLMClient({
        "classification": "FULL_REFUSAL",
        "explanation": "Bot said it doesn't know.",
        "refusal_language": "I don't have information on that.",
    })
    result = classify_refusal("What is the CPF rate?", "I don't have information on that.", client)
    assert result.classification == "FULL_REFUSAL"


def test_classify_refusal_confident():
    from goveval.eval.refusal import classify_refusal
    client = MockLLMClient({
        "classification": "CONFIDENT_ANSWER",
        "explanation": "Bot gave a direct answer.",
        "refusal_language": None,
    })
    result = classify_refusal("What is the CPF rate?", "The CPF OA rate is 2.5%.", client)
    assert result.classification == "CONFIDENT_ANSWER"


# ── assess_appropriateness ────────────────────────────────────────────────────

def test_assess_appropriateness_necessary():
    from goveval.eval.refusal import assess_appropriateness
    client = MockLLMClient({
        "was_refusal_necessary": True,
        "explanation": "Answer not in KB.",
        "refusal_quality_score": 4,
        "unnecessary_refusal_harm": None,
        "recommendation": None,
    })
    result = assess_appropriateness("Q?", "I don't know.", [], True, client)
    assert result.was_refusal_necessary is True
    assert result.refusal_quality_score == 4


def test_assess_appropriateness_unnecessary():
    from goveval.eval.refusal import assess_appropriateness
    client = MockLLMClient({
        "was_refusal_necessary": False,
        "explanation": "Answer was in KB.",
        "refusal_quality_score": 2,
        "unnecessary_refusal_harm": "User left without answer.",
        "recommendation": "Bot should have answered directly.",
    })
    result = assess_appropriateness("Q?", "I don't know.", [], False, client)
    assert result.was_refusal_necessary is False
    assert result.refusal_quality_score == 2
    assert result.recommendation is not None
