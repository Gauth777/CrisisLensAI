from __future__ import annotations

import os

from dotenv import load_dotenv

from .providers import GeminiProvider, LLMProvider, OpenAIProvider

def build_provider() -> LLMProvider:
    load_dotenv()
    provider = os.getenv("CRISISLENS_PROVIDER", "gemini").strip().lower()
    if provider == "gemini":
        return GeminiProvider()
    if provider == "openai":
        return OpenAIProvider()
    raise ValueError(f"Unsupported CRISISLENS_PROVIDER={provider!r}. Expected 'gemini' or 'openai'.")
