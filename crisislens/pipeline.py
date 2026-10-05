from __future__ import annotations

from .data import get_location_context
from .prompt import SYSTEM_PROMPT, build_prompt
from .providers.base import LLMProvider
from .schemas import CrisisInput, CrisisOutput

class CrisisLensPipeline:
    """Deterministic orchestration for a single CrisisLens inference."""

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def analyse(self, crisis_input: CrisisInput) -> CrisisOutput:
        location_context = get_location_context(crisis_input.location)
        user_prompt = build_prompt(crisis_input, location_context)
        raw_output = self.provider.generate_json(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)
        output = CrisisOutput.model_validate(raw_output)

        if output.location != crisis_input.location:
            raise ValueError(
                "Model output location does not match the requested input location: "
                f"{output.location!r} != {crisis_input.location!r}"
            )
        return output
