from __future__ import annotations

import os

from dotenv import load_dotenv

from .providers import GeminiProvider, LLMProvider, OpenAIProvider


def build_provider(provider_name: str | None = None) -> LLMProvider:
    """Build one configured LLM provider.

    provider_name is explicit for benchmarking; when omitted the environment
    variable CRISISLENS_PROVIDER is used.
    """
    load_dotenv()
    provider = (provider_name or os.getenv("CRISISLENS_PROVIDER", "gemini")).strip().lower()

    if provider == "gemini":
        return GeminiProvider()
    if provider == "openai":
        return OpenAIProvider()

    raise ValueError(
        f"Unsupported provider={provider!r}. Expected 'gemini' or 'openai'."
    )
