"""
goveval/config/loader.py
Typed dataclasses for all runtime configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class TargetConfig:
    name: str
    endpoint: str
    type: str = "api"           # api | chat


@dataclass
class ScrapeSource:
    name: str
    url: str
    depth: int = 1


@dataclass
class ConnectSource:
    name: str
    path: str
    type: str                   # pdf | json | txt


@dataclass
class KnowledgeBaseConfig:
    mode: str                   # scrape | connect | both
    scrape_sources: List[ScrapeSource] = field(default_factory=list)
    connect_sources: List[ConnectSource] = field(default_factory=list)


@dataclass
class LLMConfig:
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    api_key_env: str = "ANTHROPIC_API_KEY"

    @property
    def api_key(self) -> str:
        key = os.environ.get(self.api_key_env, "")
        if not key:
            raise EnvironmentError(f"{self.api_key_env} not set")
        return key


@dataclass
class EvalConfig:
    question_bank_size: int = 200
    held_out_size: int = 50
    human_label_sample: int = 30
    iterations: int = 3
    improvement_threshold: float = 0.02
    singlish: bool = True
    rate_limit_delay: float = 1.0


@dataclass
class StorageConfig:
    db_path: str = "goveval.db"
    results_dir: str = "results"


@dataclass
class GovEvalConfig:
    target: TargetConfig
    knowledge_base: KnowledgeBaseConfig
    llm: LLMConfig
    eval: EvalConfig
    storage: StorageConfig
