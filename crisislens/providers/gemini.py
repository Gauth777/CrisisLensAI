from __future__ import annotations

import json
import os
from typing import Any

from google import genai
from google.genai import types

from .base import LLMProvider

class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY is required for the Gemini provider.")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.client = genai.Client(api_key=key)

    def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        response = self.client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        if not response.text:
            raise ValueError("Gemini returned an empty response.")
        parsed = json.loads(response.text)
        if not isinstance(parsed, dict):
            raise ValueError("Gemini response was valid JSON but not a JSON object.")
        return parsed
