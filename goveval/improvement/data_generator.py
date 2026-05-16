"""
goveval/improvement/data_generator.py
Path B — KB Data Augmentation.

When failure analysis indicates MISSING_KB hypotheses:
  1. Identify what information is missing
  2. Generate synthetic KB documents grounded in real gov policy
  3. Generate additional evaluation questions targeting the gap

All synthetic documents are flagged is_synthetic=True for audit trail.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class SyntheticDocument:
    doc_id: str
    hypothesis_id: str
    cluster_label: str
    title: str
    content: str
    source_label: str
    is_synthetic: bool = True
    created_at: str = ""


@dataclass
class SyntheticQuestion:
    text: str
    category: str       # in_scope | adversarial
    expected_behavior: str   # answer | correct


@dataclass
class TrainingSample:
    doc: SyntheticDocument
    questions: list[SyntheticQuestion]
    hypothesis_id: str


@dataclass
class QAPair:
    question: str
    ideal_response: str
    phrasing_style: str   # formal | singlish_mild | singlish_heavy | adversarial
    hypothesis_id: str


@dataclass
class QATrainingSet:
    hypothesis_id: str
    cluster_label: str
    failure_pattern: str
    pairs: list[QAPair]
    usage_notes: str


SYNTHETIC_DOC_PROMPT = """\
A Singapore government chatbot is failing to answer questions about: {gap_description}

These questions failed during evaluation:
{failure_examples}

Generate a factual supplementary knowledge base document that fills this gap.

Requirements:
  - Grounded in Singapore government policy — do NOT fabricate specific amounts, dates, or rules
  - If you don't know the exact current policy, write the document in general terms and note it requires verification
  - Plain language suitable for a RAG knowledge base chunk (not a full article)
  - 150-250 words
  - Covers the specific eligibility rules, amounts, or procedures that seem to be missing

Return ONLY valid JSON:
{{
  "title": "<concise document title>",
  "content": "<document text — 150-250 words>",
  "source_label": "synthetic — <topic area>"
}}
"""

FOLLOWUP_QUESTIONS_PROMPT = """\
Generate evaluation questions that test whether a chatbot correctly uses this knowledge base document.

DOCUMENT TITLE: {title}
DOCUMENT CONTENT: {content}

Generate exactly 5 questions:
  1. A direct factual question (formal English)
  2. An eligibility boundary question
  3. A Singlish-phrased version of question 1 (use: lah, lor, ah, can or not, one)
  4. An adversarial question with a WRONG premise the bot must correct
  5. An out-of-scope question related to the topic but outside this bot's remit

Return ONLY valid JSON:
{{
  "questions": [
    {{
      "text": "<question text>",
      "category": "in_scope|adversarial|out_of_scope|singlish",
      "expected_behavior": "answer|correct|refuse"
    }}
  ]
}}
"""


def generate_synthetic_doc(
    hypothesis: "Hypothesis",
    failure_examples: list[dict],
    llm_client,
) -> SyntheticDocument:
    """Generate one synthetic KB document for a MISSING_KB hypothesis."""
    failure_text = "\n".join(
        f"- Q: {fe.get('question_text', '?')}  "
        f"(failed: {', '.join(fe.get('failed_metrics', []))})"
        for fe in failure_examples[:5]
    )
    prompt = SYNTHETIC_DOC_PROMPT.format(
        gap_description=hypothesis.description,
        failure_examples=failure_text or "(no examples available)",
    )
    raw = llm_client.complete(prompt, max_tokens=700)
    start = raw.find("{")
    end = raw.rfind("}") + 1
    data: dict = {}
    if start != -1 and end > start:
        try:
            data = json.loads(raw[start:end])
        except Exception:
            pass

    return SyntheticDocument(
        doc_id=f"syndoc_{uuid.uuid4().hex[:8]}",
        hypothesis_id=hypothesis.hypothesis_id,
        cluster_label=hypothesis.cluster_label,
        title=data.get("title", f"Supplementary document — {hypothesis.cluster_label}"),
        content=data.get("content", raw),  # fallback: use raw text if JSON parse failed
        source_label=data.get("source_label", f"synthetic — {hypothesis.cluster_label}"),
        is_synthetic=True,
        created_at=datetime.utcnow().isoformat(),
    )


def generate_followup_questions(
    doc: SyntheticDocument,
    llm_client,
) -> list[SyntheticQuestion]:
    """Generate evaluation questions that probe the synthetic document's content."""
    prompt = FOLLOWUP_QUESTIONS_PROMPT.format(
        title=doc.title,
        content=doc.content[:1200],
    )
    raw = llm_client.complete(prompt, max_tokens=800)
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return []
    try:
        data = json.loads(raw[start:end])
    except Exception:
        return []

    questions = []
    for q in data.get("questions", []):
        if not q.get("text"):
            continue
        questions.append(SyntheticQuestion(
            text=q["text"],
            category=q.get("category", "in_scope"),
            expected_behavior=q.get("expected_behavior", "answer"),
        ))
    return questions


QA_PAIRS_PROMPT = """\
A Singapore government chatbot is failing on questions with this pattern: {failure_pattern}

These specific examples failed:
{failure_examples}

Knowledge base content available to the bot:
{kb_content}

Generate {n_pairs} synthetic training pairs — each is a (question, ideal_response) example \
that targets this specific failure pattern.

Requirements:
  - Questions should be realistic variants covering different phrasings and topics
  - If this is a Singlish/language failure: vary dialect intensity across examples \
(lah, lor, ah, sia, can or not, one, how come, got meh)
  - Ideal responses MUST be grounded in the knowledge base content — do NOT fabricate \
specific amounts, dates, rates, or eligibility rules
  - If the exact value is not in the KB content provided, write the response in general \
terms and note "please verify with the relevant agency"
  - Each ideal response should be complete, helpful, and include a source reference \
like [Source: agency.gov.sg/page]
  - Cover the full range: basic factual, eligibility boundary, procedure, edge case

Return ONLY valid JSON:
{{
  "pairs": [
    {{
      "question": "<question text>",
      "ideal_response": "<what the bot should say>",
      "phrasing_style": "formal|singlish_mild|singlish_heavy|adversarial"
    }}
  ],
  "usage_notes": "<one sentence on the best way to use these pairs>"
}}
"""


def generate_qa_pairs(
    hypothesis: "Hypothesis",
    failure_examples: list[dict],
    kb_chunks: list[dict] | None,
    llm_client,
    n_pairs: int = 20,
) -> QATrainingSet:
    """
    Generate (question, ideal_response) training pairs targeted at a specific failure pattern.

    These are ready to use as:
      - Few-shot examples injected into the system prompt
      - Fine-tuning data (download as JSONL)
      - Expanded test cases for regression testing
    """
    failure_text = "\n".join(
        f"  - Q: {fe.get('question_text', '?')}  "
        f"(failed: {', '.join(fe.get('failed_metrics', []))})"
        for fe in failure_examples[:8]
    ) or "  (no examples available)"

    kb_content = ""
    if kb_chunks:
        kb_content = "\n\n".join(
            f"[{c.get('source_name', 'Source')}]\n{c.get('text', '')[:400]}"
            for c in kb_chunks[:4]
        )
    if not kb_content:
        kb_content = "(No knowledge base content provided — ground responses in general Singapore government policy)"

    prompt = QA_PAIRS_PROMPT.format(
        failure_pattern=hypothesis.description,
        failure_examples=failure_text,
        kb_content=kb_content,
        n_pairs=n_pairs,
    )

    try:
        raw = llm_client.complete(prompt, max_tokens=3000)
    except Exception as e:
        return QATrainingSet(
            hypothesis_id=hypothesis.hypothesis_id,
            cluster_label=hypothesis.cluster_label,
            failure_pattern=hypothesis.description,
            pairs=[],
            usage_notes=f"Generation failed: {e}",
        )

    start = raw.find("{")
    end = raw.rfind("}") + 1
    data: dict = {}
    if start != -1 and end > start:
        try:
            data = json.loads(raw[start:end])
        except Exception:
            pass

    pairs = []
    for p in data.get("pairs", []):
        if not p.get("question") or not p.get("ideal_response"):
            continue
        pairs.append(QAPair(
            question=p["question"],
            ideal_response=p["ideal_response"],
            phrasing_style=p.get("phrasing_style", "formal"),
            hypothesis_id=hypothesis.hypothesis_id,
        ))

    return QATrainingSet(
        hypothesis_id=hypothesis.hypothesis_id,
        cluster_label=hypothesis.cluster_label,
        failure_pattern=hypothesis.description,
        pairs=pairs,
        usage_notes=data.get("usage_notes", "Use as few-shot examples or fine-tuning data."),
    )


def qa_set_to_jsonl(qa_set: QATrainingSet) -> str:
    """Serialise a QATrainingSet to JSONL format for download."""
    lines = []
    for pair in qa_set.pairs:
        lines.append(json.dumps({
            "question": pair.question,
            "ideal_response": pair.ideal_response,
            "phrasing_style": pair.phrasing_style,
            "failure_pattern": qa_set.failure_pattern,
            "cluster_label": qa_set.cluster_label,
        }, ensure_ascii=False))
    return "\n".join(lines)


def qa_set_to_csv(qa_set: QATrainingSet) -> str:
    """Serialise a QATrainingSet to CSV format for download."""
    import csv, io
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=["question", "ideal_response", "phrasing_style"])
    writer.writeheader()
    for pair in qa_set.pairs:
        writer.writerow({
            "question": pair.question,
            "ideal_response": pair.ideal_response,
            "phrasing_style": pair.phrasing_style,
        })
    return out.getvalue()


def generate_training_sample(
    hypothesis: "Hypothesis",
    failure_examples: list[dict],
    llm_client,
) -> TrainingSample:
    """Full pipeline: synthetic doc + follow-up questions for one MISSING_KB hypothesis."""
    doc = generate_synthetic_doc(hypothesis, failure_examples, llm_client)
    questions = generate_followup_questions(doc, llm_client)
    return TrainingSample(doc=doc, questions=questions, hypothesis_id=hypothesis.hypothesis_id)
