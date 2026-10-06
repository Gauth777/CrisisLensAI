from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

from .base import LLMProvider
from ..schemas import CrisisOutput

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        key = (api_key or os.getenv("OPENAI_API_KEY") or "").strip()
        if not key:
            raise ValueError("OPENAI_API_KEY is required for the OpenAI provider.")
        self.model = (model or os.getenv("OPENAI_MODEL") or "").strip() or "gpt-5-mini"
        self.client = OpenAI(api_key=key, timeout=90.0, max_retries=0)

    def generate_json(self, *, system_prompt: str, user_prompt: str, output_schema: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.client.responses.create(
            model=self.model,
            instructions=system_prompt,
            input=user_prompt,
            text={"format": {"type": "json_schema", "name": "crisis_assessment", "strict": True, "schema": output_schema or CrisisOutput.model_json_schema()}},
        )
        text = response.output_text
        if not text:
            raise ValueError("OpenAI returned an empty response.")
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("OpenAI response was valid JSON but not a JSON object.")
        return parsed
