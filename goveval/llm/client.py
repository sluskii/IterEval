"""
goveval/llm/client.py
Thin wrapper around Anthropic and Groq clients.
All eval modules call llm_client.complete(prompt).
"""

from __future__ import annotations

import time


_GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
]

_ANTHROPIC_MODELS = [
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
]

_GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

_OPENAI_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-3.5-turbo",
]


class LLMClient:
    def __init__(
        self,
        model: str,
        api_key: str,
        rate_limit_delay: float = 1.0,
        provider: str = "anthropic",
    ):
        self.model = model
        self.provider = provider
        self.rate_limit_delay = rate_limit_delay
        self._last_call: float = 0.0

        if provider == "groq":
            from groq import Groq
            self._client = Groq(api_key=api_key)
        elif provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self._client = genai.GenerativeModel(model)
        elif provider == "openai":
            from openai import OpenAI
            self._client = OpenAI(api_key=api_key)
        else:
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)

    def complete(self, prompt: str, max_tokens: int = 1500) -> str:
        """Send prompt, return response text. Enforces rate_limit_delay between calls."""
        elapsed = time.time() - self._last_call
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)

        if self.provider == "groq":
            msg = self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            result = msg.choices[0].message.content
        elif self.provider == "gemini":
            response = self._client.generate_content(prompt)
            result = response.text
        elif self.provider == "openai":
            msg = self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            result = msg.choices[0].message.content
        else:
            msg = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            result = msg.content[0].text

        self._last_call = time.time()
        return result


def make_client(cfg) -> LLMClient:
    """Build LLMClient from a GovEvalConfig."""
    return LLMClient(
        model=cfg.llm.model,
        api_key=cfg.llm.api_key,
        rate_limit_delay=cfg.eval.rate_limit_delay,
        provider=cfg.llm.provider,
    )


def _model_family(model: str) -> str:
    """Return a coarse family tag so we can detect same-family judge/target collisions."""
    m = model.lower()
    if "claude" in m or "anthropic" in m:
        return "anthropic"
    if "llama" in m or "mixtral" in m or "groq" in m:
        return "groq"
    if "gpt" in m or "openai" in m:
        return "openai"
    if "gemini" in m or "google" in m:
        return "google"
    return "unknown"


def make_heterogeneous_judge_client(
    target_model: str,
    anthropic_key: str = "",
    groq_key: str = "",
    rate_limit_delay: float = 0.5,
) -> LLMClient:
    """
    Return a judge LLMClient whose model family differs from target_model.

    If the target bot is on Anthropic (Claude), defaults the judge to Groq Llama.
    If the target bot is on Groq, defaults the judge to Anthropic Claude Haiku.
    Falls back gracefully when only one key is available.

    This prevents judge-target collusion: a Claude judge scoring a Claude bot
    may share systematic blind spots and undercount hallucinations.
    """
    target_family = _model_family(target_model)

    # Prefer the heterogeneous provider; fall back to whatever key is available.
    if target_family == "anthropic" and groq_key:
        return LLMClient(
            model="llama-3.3-70b-versatile",
            api_key=groq_key,
            rate_limit_delay=rate_limit_delay,
            provider="groq",
        )
    if target_family != "anthropic" and anthropic_key:
        return LLMClient(
            model="claude-haiku-4-5-20251001",
            api_key=anthropic_key,
            rate_limit_delay=rate_limit_delay,
            provider="anthropic",
        )
    # Fallback: use whatever key is available
    if groq_key:
        return LLMClient(
            model="llama-3.3-70b-versatile",
            api_key=groq_key,
            rate_limit_delay=rate_limit_delay,
            provider="groq",
        )
    if anthropic_key:
        return LLMClient(
            model="claude-haiku-4-5-20251001",
            api_key=anthropic_key,
            rate_limit_delay=rate_limit_delay,
            provider="anthropic",
        )
    raise ValueError(
        "make_heterogeneous_judge_client requires at least one of: anthropic_key, groq_key"
    )


def is_same_family(model_a: str, model_b: str) -> bool:
    """Return True if both models are from the same provider family."""
    return _model_family(model_a) == _model_family(model_b)
