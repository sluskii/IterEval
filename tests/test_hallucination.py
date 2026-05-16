"""
tests/test_hallucination.py
Tests for hallucination.py — LLM-based refusal detection and judge logic.
No real LLM calls; uses a mock client.
"""

from __future__ import annotations
import json
import pytest
from goveval.eval.hallucination import _is_refusal, judge, HallucinationResult


# ── Mock LLM clients ───────────────────────────────────────────────────────────

class MockLLMClient:
    """Returns a fixed JSON string for any .complete() call."""
    def __init__(self, response: dict):
        self._response = json.dumps(response)

    def complete(self, prompt: str, max_tokens: int = 1500) -> str:
        return self._response


class MockRefusalClient:
    """Always responds REFUSAL to the refusal-check prompt, then returns judge_response for subsequent calls."""
    def __init__(self, judge_response: dict | None = None):
        self._judge_response = json.dumps(judge_response) if judge_response else ""
        self._call_count = 0

    def complete(self, prompt: str, max_tokens: int = 1500) -> str:
        self._call_count += 1
        if max_tokens == 5:   # refusal check call
            return "REFUSAL"
        return self._judge_response


class MockFactualClient:
    """Always responds FACTUAL to the refusal-check prompt, then returns judge_response."""
    def __init__(self, judge_response: dict):
        self._judge_response = json.dumps(judge_response)

    def complete(self, prompt: str, max_tokens: int = 1500) -> str:
        if max_tokens == 5:   # refusal check call
            return "FACTUAL"
        return self._judge_response


# ── _is_refusal ────────────────────────────────────────────────────────────────

class TestIsRefusal:
    def test_llm_says_refusal(self):
        client = MockRefusalClient()
        assert _is_refusal("I don't have specific information on that topic.", client)

    def test_llm_says_factual(self):
        client = MockFactualClient({"claims": [], "hallucination_rate": 0.0,
                                    "cannot_determine_rate": 0.0, "overall_assessment": ""})
        assert not _is_refusal("The CPF OA rate is 2.5% per annum.", client)

    def test_refusal_response_starts_with_refusal(self):
        client = MockRefusalClient()
        assert _is_refusal("Please visit the relevant agency website.", client)


# ── judge() refusal fast-path ──────────────────────────────────────────────────

class TestJudgeRefusalFastPath:
    """When LLM flags a response as a refusal, judge short-circuits to 0% hallucination."""

    REFUSAL_RESPONSES = [
        "I don't have specific information on that topic.",
        "I cannot provide information about IRAS tax refunds.",
        "I'm unable to answer that question.",
        "I don't know. Please check with the relevant authority.",
        "I am not sure about this topic.",
    ]

    @pytest.mark.parametrize("response", REFUSAL_RESPONSES)
    def test_refusal_scores_zero_hallucination(self, response):
        client = MockRefusalClient()
        result = judge("Any question?", response, [], client)
        assert result.hallucination_rate == 0.0
        assert result.claims == []
        assert "Refusal" in result.overall_assessment

    def test_refusal_no_chunks_needed(self):
        client = MockRefusalClient()
        result = judge("Q", "I don't have specific information on that topic.", [], client)
        assert isinstance(result, HallucinationResult)
        assert result.hallucination_rate == 0.0


# ── judge() normal path ────────────────────────────────────────────────────────

class TestJudgeNormalPath:
    """Non-refusal responses go through LLM judge; rates recomputed from parsed claims."""

    CLEAN_OUTPUT = {
        "claims": [
            {"claim": "CPF OA rate is 2.5%.", "verdict": "SUPPORTED",
             "explanation": "Stated in chunk.", "source_chunk_id": "c1"},
            {"claim": "Applies to all Singapore citizens.", "verdict": "SUPPORTED",
             "explanation": "Stated in chunk.", "source_chunk_id": "c1"},
        ],
        "hallucination_rate": 0.0,
        "cannot_determine_rate": 0.0,
        "overall_assessment": "No hallucinations detected.",
    }

    HALLUCINATION_OUTPUT = {
        "claims": [
            {"claim": "CPF OA rate is 2.5%.", "verdict": "SUPPORTED",
             "explanation": "Stated in chunk.", "source_chunk_id": "c1"},
            {"claim": "The scheme started in 1950.", "verdict": "UNSUPPORTED",
             "explanation": "No source mentions 1950.", "source_chunk_id": None},
        ],
        "hallucination_rate": 0.5,
        "cannot_determine_rate": 0.0,
        "overall_assessment": "One fabricated date.",
    }

    ALL_UNSUPPORTED_OUTPUT = {
        "claims": [
            {"claim": "Claim A.", "verdict": "UNSUPPORTED",
             "explanation": "Not in chunks.", "source_chunk_id": None},
            {"claim": "Claim B.", "verdict": "UNSUPPORTED",
             "explanation": "Not in chunks.", "source_chunk_id": None},
        ],
        "hallucination_rate": 1.0,
        "cannot_determine_rate": 0.0,
        "overall_assessment": "Fully hallucinated.",
    }

    CANNOT_DETERMINE_OUTPUT = {
        "claims": [
            {"claim": "Claim A.", "verdict": "CANNOT_DETERMINE",
             "explanation": "Insufficient info.", "source_chunk_id": None},
        ],
        "hallucination_rate": 0.0,
        "cannot_determine_rate": 1.0,
        "overall_assessment": "Cannot determine.",
    }

    def test_clean_response_zero_hallucination(self):
        client = MockFactualClient(self.CLEAN_OUTPUT)
        result = judge(
            "What is the CPF OA rate?",
            "The CPF OA rate is 2.5% and applies to all Singapore citizens.",
            [{"chunk_id": "c1", "text": "CPF OA interest rate is 2.5% per annum."}],
            client,
        )
        assert result.hallucination_rate == 0.0
        assert len(result.claims) == 2

    def test_hallucination_rate_recomputed_from_claims(self):
        # LLM reports 0.5 but we recompute — should still be 0.5 (1 unsup / 2 total)
        client = MockFactualClient(self.HALLUCINATION_OUTPUT)
        result = judge(
            "What is the CPF OA rate?",
            "The CPF OA rate is 2.5%. The scheme started in 1950.",
            [{"chunk_id": "c1", "text": "CPF OA interest rate is 2.5% per annum."}],
            client,
        )
        assert result.hallucination_rate == pytest.approx(0.5)

    def test_all_unsupported_is_100_percent(self):
        client = MockFactualClient(self.ALL_UNSUPPORTED_OUTPUT)
        result = judge("Q", "Claim A. Claim B.", [], client)
        assert result.hallucination_rate == pytest.approx(1.0)

    def test_cannot_determine_excluded_from_denominator(self):
        # Only CANNOT_DETERMINE claims → denom=0 → rate=0.0
        client = MockFactualClient(self.CANNOT_DETERMINE_OUTPUT)
        result = judge("Q", "Claim A.", [], client)
        assert result.hallucination_rate == 0.0
        assert result.cannot_determine_rate == pytest.approx(1.0)

    def test_empty_claims_list_is_zero(self):
        client = MockFactualClient({
            "claims": [], "hallucination_rate": 0.0,
            "cannot_determine_rate": 0.0, "overall_assessment": "Nothing."
        })
        result = judge("Q", "Some factual answer.", [], client)
        assert result.hallucination_rate == 0.0
