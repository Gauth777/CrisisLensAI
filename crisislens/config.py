from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from .providers import GeminiProvider, LLMProvider, OpenAIProvider, GroqProvider

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def load_environment() -> None:
    """Use the repository .env consistently; deployment environment wins."""
    load_dotenv(ENV_FILE, override=False)


def build_provider(provider_name: str | None = None) -> LLMProvider:
    """Build one configured LLM provider.

    provider_name is explicit for benchmarking; when omitted the environment
    variable CRISISLENS_PROVIDER is used.
    """
    load_environment()
    provider = (provider_name or os.getenv("CRISISLENS_PROVIDER", "gemini")).strip().lower()

    if provider == "gemini":
        return GeminiProvider()
    if provider == "openai":
        return OpenAIProvider()
    if provider == "groq":
        return GroqProvider()

    raise ValueError(
        f"Unsupported provider={provider!r}. Expected 'gemini', 'openai' or 'groq'."
    )
