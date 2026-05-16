"""
goveval/analysis/hypothesis.py
Generates improvement hypotheses from failure clusters.

Each cluster maps to one or more hypotheses about:
  - What KB content is missing (→ data_generator)
  - What prompt instruction is wrong (→ prompt_optimiser)
  - Which retrieval parameter to tune
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional


@dataclass
class Hypothesis:
    hypothesis_id: str
    cluster_id: int
    cluster_label: str
    hypothesis_type: str        # MISSING_KB | WRONG_PROMPT | RETRIEVAL_PARAM
    description: str
    proposed_fix: str
    estimated_impact: str       # HIGH | MEDIUM | LOW
    fix_path: str               # "prompt_optimiser" | "data_generator" | "retrieval"


HYPOTHESIS_PROMPT = """\
A Singapore government chatbot has a cluster of evaluation failures:

CLUSTER LABEL: {cluster_label}
ROOT CAUSE: {root_cause}
EXAMPLE QUESTIONS (failed):
{example_questions}
FAILED METRICS: {failed_metrics}

Generate 1-3 hypotheses about what is causing these failures and how to fix them.
Be specific and actionable. Each hypothesis should cover exactly one root cause.

Fix path options:
  - "data_generator": missing or incorrect KB content (add/update documents)
  - "prompt_optimiser": wrong system prompt instruction (change prompt)
  - "retrieval": retrieval parameters (chunk size, top-k, embedding model)

Return ONLY valid JSON:
{{
  "hypotheses": [
    {{
      "hypothesis_type": "MISSING_KB|WRONG_PROMPT|RETRIEVAL_PARAM",
      "description": "<one sentence: what is wrong>",
      "proposed_fix": "<specific actionable fix, e.g. 'Add a KB document covering CPF LIFE payout amounts'>",
      "fix_path": "data_generator|prompt_optimiser|retrieval",
      "estimated_impact": "HIGH|MEDIUM|LOW"
    }}
  ]
}}
"""

_IMPACT_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}


def generate_hypotheses(
    failure_analysis: "FailureAnalysis",
    llm_client,
) -> list[Hypothesis]:
    """Generate improvement hypotheses for each failure cluster, sorted HIGH → LOW."""
    hypotheses: list[Hypothesis] = []
    errors: list[str] = []

    for cluster in failure_analysis.clusters:
        prompt = HYPOTHESIS_PROMPT.format(
            cluster_label=cluster.label,
            root_cause=cluster.root_cause or "Not determined",
            example_questions="\n".join(
                f"- {q}" for q in cluster.representative_questions[:5]
            ),
            failed_metrics=", ".join(cluster.common_metrics) if cluster.common_metrics else "various",
        )
        try:
            raw = llm_client.complete(prompt, max_tokens=800)
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start == -1 or end == 0:
                errors.append(f"Cluster {cluster.cluster_id}: no JSON in response")
                continue
            data = json.loads(raw[start:end])
        except json.JSONDecodeError as e:
            errors.append(f"Cluster {cluster.cluster_id}: JSON parse error — {e}")
            continue
        except Exception as e:
            errors.append(f"Cluster {cluster.cluster_id}: {type(e).__name__}: {e}")
            continue

        for i, h in enumerate(data.get("hypotheses", [])):
            if not h.get("description"):
                continue
            hypotheses.append(Hypothesis(
                hypothesis_id=f"hyp_{cluster.cluster_id}_{i}",
                cluster_id=cluster.cluster_id,
                cluster_label=cluster.label,
                hypothesis_type=h.get("hypothesis_type", "MISSING_KB"),
                description=h.get("description", ""),
                proposed_fix=h.get("proposed_fix", ""),
                estimated_impact=h.get("estimated_impact", "MEDIUM"),
                fix_path=h.get("fix_path", "data_generator"),
            ))

    return prioritise(hypotheses), errors


def prioritise(hypotheses: list[Hypothesis]) -> list[Hypothesis]:
    return sorted(hypotheses, key=lambda h: -_IMPACT_RANK.get(h.estimated_impact, 0))


def route_hypotheses(
    hypotheses: list[Hypothesis],
) -> tuple[list[Hypothesis], list[Hypothesis], list[Hypothesis]]:
    prompt = [h for h in hypotheses if h.fix_path == "prompt_optimiser"]
    data = [h for h in hypotheses if h.fix_path == "data_generator"]
    retrieval = [h for h in hypotheses if h.fix_path == "retrieval"]
    return prompt, data, retrieval
