"""
goveval/analysis/failure_analyser.py
Clusters failing questions to find structural failure patterns.

Uses KMeans on sentence embeddings of failed question texts.
Each cluster gets an LLM-generated label: "Missing scheme X",
"Singlish retrieval failure", "Wrong eligibility threshold", etc.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FailureCluster:
    cluster_id: int
    label: str
    root_cause: str
    question_ids: list[str]
    representative_questions: list[str]
    representative_question: str
    common_metrics: list[str]
    failure_count: int
    severity: str


@dataclass
class FailureAnalysis:
    run_id: str
    iteration: int
    total_failures: int
    clusters: list[FailureCluster]
    dominant_pattern: str
    improvement_priority: list[str]


CLUSTER_LABEL_PROMPT = """\
    These Singapore government chatbot questions all failed evaluation. Find the common failure pattern.

    QUESTIONS:
    {questions}

    FAILED METRICS: {metrics}

    Give this cluster a short label (5-10 words) that describes the root cause.
    Examples: "Missing CPF contribution scheme info", "Singlish housing query misunderstood",
    "Wrong income threshold stated", "Out-of-scope question incorrectly answered"

    Return ONLY valid JSON:
    {{
    "label": "<cluster label>",
    "root_cause": "<one sentence explaining why these fail>",
    "severity": "HIGH|MEDIUM|LOW"
    }}
"""

# Module-level model cache — avoids reloading on every call
_ST_MODEL = None


def analyse_failures(
    verdicts: list[dict],
    run_id: str,
    iteration: int,
    llm_client,
    n_clusters: int = 3,
    min_cluster_size: int = 2,
) -> FailureAnalysis:
    """
    Filter failing verdicts, embed question texts, cluster with KMeans,
    then ask LLM to label each cluster.
    """
    failures = _extract_failures(verdicts)

    if not failures:
        return FailureAnalysis(
            run_id=run_id, iteration=iteration, total_failures=0,
            clusters=[], dominant_pattern="none", improvement_priority=[],
        )

    texts = [f.get("question_text", "") for f in failures]

    # Embed + cluster only when there are enough failures
    if len(failures) >= 3:
        try:
            embeddings = _embed_questions(texts)
            k = min(n_clusters, max(1, len(failures) // max(1, min_cluster_size)))
            k = min(k, len(failures))
            labels = _cluster(embeddings, k)
        except Exception:
            labels = [0] * len(failures)
    else:
        labels = [0] * len(failures)

    # Group by cluster
    cluster_map: dict[int, list[dict]] = {}
    for failure, label in zip(failures, labels):
        cluster_map.setdefault(label, []).append(failure)

    clusters: list[FailureCluster] = []
    for cid, members in sorted(cluster_map.items()):
        qtexts = [m.get("question_text", "") for m in members]
        all_metrics: list[str] = []
        for m in members:
            all_metrics.extend(m.get("failed_metrics", []))
        unique_metrics = list(dict.fromkeys(all_metrics))

        try:
            label_data = _label_cluster(qtexts, unique_metrics, llm_client)
        except Exception:
            label_data = {
                "label": f"Failure group {cid + 1}",
                "root_cause": "Could not determine automatically.",
                "severity": "MEDIUM",
            }

        member_severities = [m.get("severity", "LOW") for m in members]
        if "HIGH" in member_severities:
            sev = "HIGH"
        elif "MEDIUM" in member_severities:
            sev = "MEDIUM"
        else:
            sev = "LOW"
        # Use LLM's severity if it rated higher
        llm_sev = label_data.get("severity", sev)
        if {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(llm_sev, 0) > {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(sev, 0):
            sev = llm_sev

        clusters.append(FailureCluster(
            cluster_id=cid,
            label=label_data.get("label", f"Failure group {cid + 1}"),
            root_cause=label_data.get("root_cause", ""),
            question_ids=[m.get("question_id", "") for m in members],
            representative_questions=qtexts[:3],
            representative_question=qtexts[0] if qtexts else "",
            common_metrics=unique_metrics,
            failure_count=len(members),
            severity=sev,
        ))

    clusters.sort(
        key=lambda c: (-{"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(c.severity, 0), -c.failure_count)
    )
    dominant = clusters[0].label if clusters else "none"

    return FailureAnalysis(
        run_id=run_id,
        iteration=iteration,
        total_failures=len(failures),
        clusters=clusters,
        dominant_pattern=dominant,
        improvement_priority=[c.label for c in clusters],
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _extract_failures(verdicts: list[dict]) -> list[dict]:
    failures = []
    for v in verdicts:
        detail = v.get("detail", {})
        if isinstance(detail, str):
            try:
                detail = json.loads(detail)
            except Exception:
                detail = {}

        hall = detail.get("hallucination_rate") or 0
        faith = detail.get("faithfulness")
        refusal_cls = detail.get("refusal") or ""
        trans_raw = detail.get("transparency")
        trans = trans_raw if trans_raw is not None else 1.0

        failed_metrics: list[str] = []
        if hall > 0:
            failed_metrics.append("hallucination")
        if faith is not None and faith < 3.0:
            failed_metrics.append("faithfulness")
        if refusal_cls == "FALSE_REFUSAL":
            failed_metrics.append("false_refusal")
        if trans < 0.60:
            failed_metrics.append("transparency")

        if not failed_metrics:
            continue

        if hall > 0.20 or (faith is not None and faith < 2.5):
            severity = "HIGH"
        elif hall > 0 or (faith is not None and faith < 3.5):
            severity = "MEDIUM"
        else:
            severity = "LOW"

        failures.append({**v, "failed_metrics": failed_metrics, "severity": severity})
    return failures


def _embed_questions(texts: list[str]):
    global _ST_MODEL
    if _ST_MODEL is None:
        from sentence_transformers import SentenceTransformer
        _ST_MODEL = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    return _ST_MODEL.encode(texts)


def _cluster(embeddings, n_clusters: int) -> list[int]:
    from sklearn.cluster import KMeans
    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    return km.fit_predict(embeddings).tolist()


def _label_cluster(
    question_texts: list[str],
    failed_metrics: list[str],
    llm_client,
) -> dict:
    prompt = CLUSTER_LABEL_PROMPT.format(
        questions="\n".join(f"- {q}" for q in question_texts[:10]),
        metrics=", ".join(failed_metrics) if failed_metrics else "various",
    )
    raw = llm_client.complete(prompt, max_tokens=300)
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(raw[start:end])
        except Exception:
            pass
    return {
        "label": f"Failure pattern ({len(question_texts)} questions)",
        "root_cause": "LLM response could not be parsed.",
        "severity": "MEDIUM",
    }
