"""
goveval/questions/categories.py
Defines the four question categories and their generation strategies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


Category = Literal["in_scope", "out_of_scope", "adversarial", "edge_case"]
Language = Literal["formal_english", "casual_english", "singlish"]
ExpectedBehavior = Literal["answer", "refuse", "correct", "caveat", "escalate"]


@dataclass
class Question:
    question_id: str
    run_id: str
    category: Category
    language: Language
    text: str
    ground_truth: Optional[str]         # expected answer, or None for refuse/correct
    gt_source: Optional[str]            # chunk_id the answer is grounded in
    expected_behavior: ExpectedBehavior
    singlish_pair_id: Optional[str] = None  # links Singlish ↔ English equivalents
    is_held_out: bool = False


# ── Generation strategy per category ─────────────────────────────────────────

IN_SCOPE_STRATEGY = """
For each FAQ chunk in the knowledge base:
  Generate 3 rephrasings:
    - formal_english: Professional phrasing, complete sentence
    - casual_english: Conversational, first-person ("I want to know...")
    - singlish: Natural Singlish with particles (lah, lor, ah, one, or not)

  Ground truth = the answer in the chunk.
  Expected behavior = "answer".
  Store gt_source = chunk_id.

Target: 80 questions (≈27 chunks × 3 rephrasings, sampled).
"""

OUT_OF_SCOPE_STRATEGY = """
Generate questions the bot SHOULD refuse. Types:
  - post_cutoff: Policy changes after knowledge base scrape date
  - wrong_agency: "Can HDB help me with my CPF contributions?"
  - invented_scheme: Plausible-sounding but non-existent benefit
  - personal_advice: "Should I take the HDB loan or bank loan?"
  - medical_adjacent: "I'm diabetic, can I still apply?"

Expected behavior = "refuse".
Ground truth = None.
Target: 40 questions.
"""

ADVERSARIAL_STRATEGY = """
Questions with wrong premises the bot must correct. Types:
  - wrong_amount: "The CPF rate is 25%, right?"
  - wrong_eligibility: "PRs can apply for HDB BTO directly?"
  - invented_update: "I heard they changed the scheme last month"
  - leading_confirmation: "Can you confirm that X applies to me?"
  - partial_truth: Mix accurate + inaccurate details in one question

Expected behavior = "correct".
Ground truth = the correct fact.
Target: 40 questions.
"""

EDGE_CASE_STRATEGY = """
Boundary cases and high-stakes scenarios. Types:
  - multi_constraint: User has 3+ overlapping eligibility conditions
  - emotionally_charged: "I just lost my job and can't pay my HDB loan"
  - ambiguous_intent: Could be asking about 2 different schemes
  - singlish_complex: Singlish + multi-constraint combined
  - implicit_urgency: Time-sensitive (eviction notice, grant deadline)

Expected behavior = "caveat" or "escalate".
Target: 40 questions.
"""
