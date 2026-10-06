from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

from .base import LLMProvider
from ..schemas import CrisisOutput

DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


class GroqProvider(LLMProvider):
    """Groq-hosted generation using its OpenAI-compatible API, without tools."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        key = (api_key or os.getenv("GROQ_API_KEY") or "").strip()
        if not key:
            raise ValueError("GROQ_API_KEY is required for the Groq provider.")
        self.model = (model or os.getenv("GROQ_MODEL") or "").strip() or DEFAULT_GROQ_MODEL
        # Explicit endpoint and key keep Groq separate from OpenAI billing/settings.
        self.client = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1",
                             timeout=90.0, max_retries=0)

    def generate_json(self, *, system_prompt: str, user_prompt: str, output_schema: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": user_prompt}],
            response_format={"type": "json_schema", "json_schema": {
                "name": "crisis_assessment", "strict": True,
                "schema": output_schema or CrisisOutput.model_json_schema(),
            }},
            max_completion_tokens=2048,
            reasoning_effort="low",
        )
        if not response.choices or response.choices[0].finish_reason != "stop":
            raise ValueError("Groq did not return a complete assessment.")
        text = response.choices[0].message.content
        if not text:
            raise ValueError("Groq returned an empty assessment.")
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("Groq response was not a JSON object.")
        return parsed
