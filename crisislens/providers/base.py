from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

class LLMProvider(ABC):
    @abstractmethod
    def generate_json(self, *, system_prompt: str, user_prompt: str, output_schema: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError
