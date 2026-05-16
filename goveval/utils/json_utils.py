"""
goveval/utils/json_utils.py
Robust JSON extraction from LLM output that may contain surrounding prose.
"""

from __future__ import annotations

import json


def extract_json(text: str) -> dict:
    """
    Find and parse the first complete {...} JSON object in text.
    Works even when the LLM wraps output in markdown fences or prose.
    """
    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in LLM output: {text[:300]}")
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError as e:
                    raise ValueError(f"Malformed JSON in LLM output: {e}\n{text[start:i+1][:400]}")
    raise ValueError(f"Unterminated JSON object in: {text[:300]}")
