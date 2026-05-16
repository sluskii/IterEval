"""
goveval/improvement/prompt_optimiser.py
Path A — Prompt Optimisation.

Given WRONG_PROMPT failure hypotheses, generates candidate system-prompt edits
with explained diffs, expected metric improvements, and regression risk notes.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Optional


@dataclass
class PromptCandidate:
    candidate_id: str
    hypothesis_id: str
    original_prompt: str
    modified_prompt: str
    change_description: str
    expected_improvement: dict       # {metric: (low, high)} estimate
    regression_risk: str             # prose description of what might get worse
    eval_result: Optional[dict]      # MetricResult as dict once evaluated
    improvement_delta: Optional[float]


_DEFAULT_PROMPT = (
    "You are a helpful Singapore government assistant. "
    "Answer questions accurately based on the provided context."
)

EDIT_PROMPT = """\
You are improving a Singapore government chatbot's system prompt to fix specific failure patterns.

CURRENT SYSTEM PROMPT:
{current_prompt}

FAILURE HYPOTHESIS:
Type: {hypothesis_type}
Description: {description}
Proposed fix: {proposed_fix}
Failing example questions:
{example_questions}

Generate a modified system prompt that addresses this specific failure.
Rules:
  - Keep all existing instructions not related to the failure
  - Add or modify only the minimum needed to fix the issue
  - Do not introduce new hallucination risks
  - Keep the prompt concise (under 300 words total)

Return ONLY valid JSON:
{{
  "modified_prompt": "<full modified system prompt>",
  "change_description": "<one sentence: what changed and why>",
  "expected_improvement": {{
    "hallucination_rate": "<e.g. '-5 to -8%' or 'no change expected'>",
    "faithfulness": "<e.g. '+0.08 to +0.12'>",
    "calibration_ece": "<e.g. '-0.04'>"
  }},
  "regression_risk": "<one to two sentences on what might get worse>"
}}
"""


def generate_candidates(
    hypotheses: list,
    current_prompt: str,
    example_questions: list[dict],
    llm_client,
) -> list[PromptCandidate]:
    """Generate one candidate prompt edit per WRONG_PROMPT hypothesis."""
    base_prompt = current_prompt.strip() or _DEFAULT_PROMPT
    candidates: list[PromptCandidate] = []

    for h in hypotheses:
        if getattr(h, "fix_path", "") != "prompt_optimiser":
            continue

        examples_text = "\n".join(
            f"  - {q.get('question_text', q) if isinstance(q, dict) else str(q)}"
            for q in example_questions[:5]
        ) or "  (no examples available)"

        prompt = EDIT_PROMPT.format(
            current_prompt=base_prompt,
            hypothesis_type=h.hypothesis_type,
            description=h.description,
            proposed_fix=h.proposed_fix,
            example_questions=examples_text,
        )

        try:
            raw = llm_client.complete(prompt, max_tokens=1000)
        except Exception as e:
            candidates.append(PromptCandidate(
                candidate_id=f"cand_{h.hypothesis_id}",
                hypothesis_id=h.hypothesis_id,
                original_prompt=base_prompt,
                modified_prompt=base_prompt,
                change_description=f"LLM call failed: {e}",
                expected_improvement={},
                regression_risk="",
                eval_result=None,
                improvement_delta=None,
            ))
            continue

        data = _parse_json(raw)
        candidates.append(PromptCandidate(
            candidate_id=f"cand_{uuid.uuid4().hex[:6]}",
            hypothesis_id=h.hypothesis_id,
            original_prompt=base_prompt,
            modified_prompt=data.get("modified_prompt", base_prompt),
            change_description=data.get("change_description", "No description returned."),
            expected_improvement=data.get("expected_improvement", {}),
            regression_risk=data.get("regression_risk", "Unknown."),
            eval_result=None,
            improvement_delta=None,
        ))

    return candidates


def evaluate_candidate(
    candidate: PromptCandidate,
    held_out_questions: list,
    kb,
    llm_client,
    db,
    run_id: str,
) -> PromptCandidate:
    """
    Run a lightweight eval (hallucination + faithfulness only) on held-out questions
    using the candidate's modified prompt injected into a mock local bot.
    Updates candidate.eval_result and candidate.improvement_delta.

    Only meaningful when the target bot is a local Python callable that accepts
    a system_prompt override. For HTTP API bots this is a no-op.
    """
    if not held_out_questions:
        return candidate

    try:
        from goveval.eval.hallucination import judge as hall_judge
        from goveval.eval.faithfulness import score as faith_score

        hall_rates: list[float] = []
        faith_scores: list[float] = []

        for q in held_out_questions[:10]:
            q_text = getattr(q, "text", str(q))
            chunks_raw = kb.retrieve(q_text, n_results=5)
            chunks = [
                {"chunk_id": c.chunk_id, "text": c.text, "source_name": getattr(c, "source_name", "")}
                for c in chunks_raw
            ]
            # Simulate a response using the modified prompt + KB context
            context_block = "\n\n".join(c["text"] for c in chunks[:3])
            sim_prompt = (
                f"{candidate.modified_prompt}\n\nContext:\n{context_block}\n\n"
                f"Question: {q_text}\nAnswer:"
            )
            try:
                simulated_response = llm_client.complete(sim_prompt, max_tokens=300)
            except Exception:
                continue

            try:
                h = hall_judge(q_text, simulated_response, chunks, llm_client)
                hall_rates.append(h.hallucination_rate)
            except Exception:
                pass

            try:
                f = faith_score(q_text, simulated_response, chunks, llm_client)
                faith_scores.append(f.overall_score)
            except Exception:
                pass

        if not hall_rates:
            return candidate

        avg_hall = sum(hall_rates) / len(hall_rates)
        avg_faith = sum(faith_scores) / len(faith_scores) if faith_scores else 0.0

        candidate.eval_result = {
            "hallucination_rate": round(avg_hall, 4),
            "faithfulness_avg": round(avg_faith, 3),
            "n_questions": len(hall_rates),
        }
        # Improvement delta: reduction in hallucination rate (higher is better)
        candidate.improvement_delta = round(-avg_hall, 4)

    except Exception:
        pass

    return candidate


def select_best(
    candidates: list[PromptCandidate],
    baseline_metrics: dict,
) -> Optional[PromptCandidate]:
    """
    Select the candidate with the highest improvement_delta > 0.
    Falls back to the first candidate with a non-identical prompt if none were evaluated.
    """
    evaluated = [c for c in candidates if c.improvement_delta is not None and c.improvement_delta > 0]
    if evaluated:
        return max(evaluated, key=lambda c: c.improvement_delta)

    # Fall back: return first candidate whose prompt actually changed
    changed = [c for c in candidates if c.modified_prompt != c.original_prompt]
    return changed[0] if changed else (candidates[0] if candidates else None)


def apply_prompt(candidate: PromptCandidate, config_path: str) -> None:
    """Write winning prompt to config.yaml system_prompt field."""
    import yaml
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        config = {}
    config["system_prompt"] = candidate.modified_prompt
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


def diff_lines(original: str, modified: str) -> list[tuple[str, str]]:
    """
    Return a line-by-line diff as list of (type, line) where type is
    'same', 'added', or 'removed'. Used by the dashboard to render the diff.
    """
    orig_lines = original.splitlines()
    mod_lines = modified.splitlines()

    import difflib
    matcher = difflib.SequenceMatcher(None, orig_lines, mod_lines)
    result: list[tuple[str, str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for line in orig_lines[i1:i2]:
                result.append(("same", line))
        elif tag == "replace":
            for line in orig_lines[i1:i2]:
                result.append(("removed", line))
            for line in mod_lines[j1:j2]:
                result.append(("added", line))
        elif tag == "delete":
            for line in orig_lines[i1:i2]:
                result.append(("removed", line))
        elif tag == "insert":
            for line in mod_lines[j1:j2]:
                result.append(("added", line))
    return result


# ── Internal helpers ──────────────────────────────────────────────────────────

def _parse_json(raw: str) -> dict:
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(raw[start:end])
        except Exception:
            pass
    return {}
