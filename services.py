from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from config import AppConfig, current_config


def get_openai_client(config: AppConfig | None = None) -> OpenAI:
    resolved = config or current_config()
    if not resolved.openai_api_key.strip():
        raise RuntimeError("OPENAI_API_KEY is required before creating an OpenAI client.")
    return OpenAI(api_key=resolved.openai_api_key)


@dataclass(frozen=True)
class DigestAnalystService:
    enabled: bool
    model: str
    timeout_seconds: int


def get_digest_analyst_service(config: AppConfig | None = None) -> DigestAnalystService:
    resolved = config or current_config()
    return DigestAnalystService(
        enabled=bool(
            resolved.digest_analyst_agent_enabled and resolved.openai_api_key.strip()
        ),
        model=resolved.digest_analyst_agent_model,
        timeout_seconds=resolved.digest_analyst_agent_timeout_seconds,
    )
