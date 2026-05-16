"""
goveval/prober/bot_prober.py
Sends questions to the target bot and logs responses.
Supports: HTTP API, local function.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional

from goveval.questions.categories import Question
from goveval.storage.db import DB


@dataclass
class BotResponse:
    response_id: str
    run_id: str
    question_id: str
    iteration: int
    response_text: str
    latency_ms: float
    timestamp: str


def probe_all(
    questions: List[Question],
    cfg: GovEvalConfig,
    run_id: str,
    iteration: int,
    db: DB,
    local_fn: Optional[Callable[[str], str]] = None,
) -> List[BotResponse]:
    """
    Send all questions to the target bot.

    Target dispatch:
      - local_fn provided → call it directly (for testing the harness)
      - cfg.target.type == "api" → HTTP POST to cfg.target.endpoint

    Rate limiting: sleep cfg.eval.rate_limit_delay seconds between calls.
    All responses saved to DB.
    """
    delay = getattr(getattr(cfg, "eval", None), "rate_limit_delay", 0.5)
    responses: List[BotResponse] = []

    for i, q in enumerate(questions):
        if local_fn is not None:
            text, latency = _probe_local(q, local_fn)
        else:
            text, latency = _probe_api(q, cfg.target)

        resp = BotResponse(
            response_id=str(uuid.uuid4())[:8],
            run_id=run_id,
            question_id=q.question_id,
            iteration=iteration,
            response_text=text,
            latency_ms=latency,
            timestamp=datetime.now().isoformat(),
        )

        db.save_response({
            "response_id": resp.response_id,
            "run_id": resp.run_id,
            "question_id": resp.question_id,
            "iteration": resp.iteration,
            "response_text": resp.response_text,
            "latency_ms": resp.latency_ms,
            "timestamp": resp.timestamp,
        })

        responses.append(resp)

        if i < len(questions) - 1:
            time.sleep(delay)

    return responses


def _probe_api(question: Question, cfg: TargetConfig) -> tuple[str, float]:
    """POST to REST API endpoint. Returns (response_text, latency_ms)."""
    import requests

    t0 = time.time()
    resp = requests.post(
        cfg.endpoint,
        json={"question": question.text},
        timeout=30,
    )
    resp.raise_for_status()
    latency = round((time.time() - t0) * 1000, 1)

    data = resp.json()
    text = data.get("answer") or data.get("response") or data.get("text") or str(data)
    return text, latency



def _probe_local(question: Question, fn: Callable[[str], str]) -> tuple[str, float]:
    """Call a local function. Used for self-evaluation."""
    t0 = time.time()
    text = fn(question.text)
    return text, round((time.time() - t0) * 1000, 1)
