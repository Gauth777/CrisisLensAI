from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

from .base import LLMProvider

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY is required for the OpenAI provider.")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5-mini")
        self.client = OpenAI(api_key=key)

    def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        response = self.client.responses.create(
            model=self.model,
            instructions=system_prompt,
            input=user_prompt,
        )
        text = response.output_text
        if not text:
            raise ValueError("OpenAI returned an empty response.")
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("OpenAI response was valid JSON but not a JSON object.")
        return parsed
