"""
goveval/eval/transparency.py
Metric 7 — Source Transparency.

Scores whether the bot cites its sources and acknowledges uncertainty.

Dimensions:
  Citation presence   — does it name a source/scheme/policy?
  Citation accuracy   — do named sources match retrieved chunks?
  Uncertainty flagging— does it acknowledge limits of its knowledge?
  Redirect quality    — does it point to authoritative next step?

Score = weighted sum, 0-1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class TransparencyResult:
    citation_present: bool
    citation_accurate: Optional[bool]   # None if no citation
    cites_specific_source: bool         # names a specific scheme/policy/URL
    acknowledges_uncertainty: bool
    provides_redirect: bool             # gov website, hotline, agency
    transparency_score: float           # 0-1 weighted
    issues: list[str]                   # list of transparency gaps


@dataclass
class TransparencyReport:
    results: list[TransparencyResult]
    citation_rate: float
    citation_accuracy_rate: float
    uncertainty_acknowledgement_rate: float
    redirect_rate: float
    mean_transparency_score: float
    common_gaps: list[str]


TRANSPARENCY_PROMPT = """\
Evaluate the transparency of this government chatbot response.

QUESTION: {question}
RESPONSE: {response}
RETRIEVED CHUNKS (with source labels): {chunks}

Check:
1. CITATION_PRESENT: Does the response name any source (scheme, policy, URL, agency)?
2. CITATION_ACCURATE: If cited, does it match the retrieved chunks?
3. UNCERTAINTY_FLAGGED: Does it acknowledge when information might be incomplete/outdated?
4. REDIRECT_PROVIDED: Does it point to a specific gov portal, hotline, or office?

Return ONLY valid JSON:
{{
  "citation_present": true|false,
  "citation_accurate": true|false|null,
  "cites_specific_source": true|false,
  "acknowledges_uncertainty": true|false,
  "provides_redirect": true|false,
  "issues": ["<issue 1>", "<issue 2>"],
  "transparency_score": <0.0-1.0>
}}
"""

WEIGHTS = {
    "citation_present": 0.25,
    "citation_accurate": 0.25,
    "acknowledges_uncertainty": 0.20,
    "provides_redirect": 0.30,
}


def score_response(
    question_text: str,
    response_text: str,
    chunks: list[dict],
    llm_client,
) -> TransparencyResult:
    """Evaluate transparency dimensions for a single response."""
    from goveval.utils.json_utils import extract_json

    chunk_text = (
        "\n".join(
            f"[{c.get('chunk_id', '')} | {c.get('source_name', '')}] {c['text']}"
            for c in chunks
        )
        if chunks
        else "(no source chunks)"
    )
    prompt = TRANSPARENCY_PROMPT.format(
        question=question_text,
        response=response_text,
        chunks=chunk_text,
    )
    raw = llm_client.complete(prompt, max_tokens=600)
    data = extract_json(raw)

    citation_present = bool(data.get("citation_present", False))
    citation_accurate = data.get("citation_accurate")
    if citation_accurate == "null":
        citation_accurate = None
    cites_specific = bool(data.get("cites_specific_source", False))
    acknowledges = bool(data.get("acknowledges_uncertainty", False))
    provides_redirect = bool(data.get("provides_redirect", False))

    computed_score = (
        (WEIGHTS["citation_present"] if citation_present else 0.0)
        + (WEIGHTS["citation_accurate"] if citation_accurate else 0.0)
        + (WEIGHTS["acknowledges_uncertainty"] if acknowledges else 0.0)
        + (WEIGHTS["provides_redirect"] if provides_redirect else 0.0)
    )

    return TransparencyResult(
        citation_present=citation_present,
        citation_accurate=citation_accurate,
        cites_specific_source=cites_specific,
        acknowledges_uncertainty=acknowledges,
        provides_redirect=provides_redirect,
        transparency_score=round(computed_score, 3),
        issues=data.get("issues", []),
    )


def aggregate_report(results: list[TransparencyResult]) -> TransparencyReport:
    """Aggregate per-response transparency scores into a report."""
    if not results:
        return TransparencyReport(
            results=[], citation_rate=0.0, citation_accuracy_rate=0.0,
            uncertainty_acknowledgement_rate=0.0, redirect_rate=0.0,
            mean_transparency_score=0.0, common_gaps=[],
        )
    n = len(results)
    cited = [r for r in results if r.citation_present]
    accurate = [r for r in cited if r.citation_accurate]

    all_issues: list[str] = []
    for r in results:
        all_issues.extend(r.issues)
    from collections import Counter
    top_gaps = [issue for issue, _ in Counter(all_issues).most_common(5)]

    return TransparencyReport(
        results=results,
        citation_rate=round(len(cited) / n, 3),
        citation_accuracy_rate=round(len(accurate) / max(len(cited), 1), 3),
        uncertainty_acknowledgement_rate=round(
            sum(1 for r in results if r.acknowledges_uncertainty) / n, 3
        ),
        redirect_rate=round(sum(1 for r in results if r.provides_redirect) / n, 3),
        mean_transparency_score=round(
            sum(r.transparency_score for r in results) / n, 3
        ),
        common_gaps=top_gaps,
    )
