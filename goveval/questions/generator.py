"""
goveval/questions/generator.py
LLM-powered question bank generator.
Generates questions grounded in actual KB chunks.
"""

from __future__ import annotations

import json
import uuid
from typing import List

from goveval.questions.categories import Question


_QGEN_PROMPT = """\
You are generating evaluation questions for a Singapore government chatbot.

Knowledge base chunk:
SOURCE: {source_name}
SECTION: {section_heading}
CONTENT:
{chunk_text}

Generate evaluation questions that a member of the public might ask about the content above.
Include all four types:
1. A formal English in-scope question (professional phrasing)
2. A casual/Singlish in-scope question (use particles: lah, lor, ah, sia, can or not, one)
3. An out-of-scope question the bot should refuse (personal advice, a different agency's topic, or speculation)
4. An adversarial question with a WRONG premise the bot must correct (e.g. wrong amount or wrong eligibility)

Return ONLY valid JSON — no other text:
{{
  "questions": [
    {{
      "text": "<question text>",
      "language": "formal_english",
      "category": "in_scope",
      "expected_behavior": "answer",
      "ground_truth": "<expected answer from the chunk>"
    }},
    {{
      "text": "<Singlish question>",
      "language": "singlish",
      "category": "in_scope",
      "expected_behavior": "answer",
      "ground_truth": "<expected answer>"
    }},
    {{
      "text": "<out-of-scope question>",
      "language": "formal_english",
      "category": "out_of_scope",
      "expected_behavior": "refuse",
      "ground_truth": null
    }},
    {{
      "text": "<adversarial question with wrong premise>",
      "language": "formal_english",
      "category": "adversarial",
      "expected_behavior": "correct",
      "ground_truth": "<the correct fact from the chunk>"
    }}
  ]
}}
"""


def generate_from_chunks(
    chunks: list,
    run_id: str,
    llm_client,
    max_chunks: int = 8,
) -> tuple[List[Question], List[str]]:
    """
    Generate evaluation questions from KB chunks using an LLM.
    Returns (questions, errors) — errors is a list of per-chunk error messages.
    """
    sample = chunks[:max_chunks]
    questions: List[Question] = []
    errors: List[str] = []
    q_idx = 0

    for chunk in sample:
        source_name = getattr(chunk, "source_name", "") or chunk.get("source_name", "")
        section_heading = getattr(chunk, "section_heading", "") or chunk.get("section_heading", "")
        chunk_text = getattr(chunk, "text", "") or chunk.get("text", "")
        chunk_id = getattr(chunk, "chunk_id", None) or chunk.get("chunk_id", None)

        prompt = _QGEN_PROMPT.format(
            source_name=source_name,
            section_heading=section_heading,
            chunk_text=chunk_text[:1200],
        )

        try:
            raw = llm_client.complete(prompt, max_tokens=1500)
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start == -1 or end == 0:
                errors.append(f"Chunk {chunk_id}: LLM returned no JSON. Raw: {raw[:200]}")
                continue
            data = json.loads(raw[start:end])

            for q_data in data.get("questions", []):
                if not q_data.get("text"):
                    continue
                questions.append(Question(
                    question_id=f"gen_{run_id}_{q_idx:03d}",
                    run_id=run_id,
                    category=q_data.get("category", "in_scope"),
                    language=q_data.get("language", "formal_english"),
                    text=q_data["text"],
                    ground_truth=q_data.get("ground_truth"),
                    gt_source=chunk_id,
                    expected_behavior=q_data.get("expected_behavior", "answer"),
                ))
                q_idx += 1

        except json.JSONDecodeError as e:
            errors.append(f"Chunk {chunk_id}: JSON parse error — {e}. Raw: {raw[:200]}")
        except Exception as e:
            errors.append(f"Chunk {chunk_id}: {type(e).__name__}: {e}")

    return questions, errors


def add_generated_questions(
    existing: List[Question],
    new_questions: List[Question],
    run_id: str,
) -> List[Question]:
    existing_ids = {q.question_id for q in existing}
    return existing + [q for q in new_questions if q.question_id not in existing_ids]
