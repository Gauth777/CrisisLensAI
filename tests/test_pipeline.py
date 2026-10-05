from __future__ import annotations

from typing import Any

import pytest

from crisislens.pipeline import CrisisLensPipeline
from crisislens.providers.base import LLMProvider
from crisislens.schemas import CrisisInput

class MockProvider(LLMProvider):
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response

    def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        assert "not an autonomous emergency-response agent" in system_prompt
        assert "OUTPUT JSON SCHEMA" in user_prompt
        return self.response

def valid_input() -> CrisisInput:
    return CrisisInput.model_validate({
        "report": "Knee-deep water is reported near Velachery MRTS and traffic has stopped.",
        "location": "Velachery",
        "environment": {
            "rainfall_1h_mm": 42.0,
            "rainfall_24h_mm": 128.0,
            "humidity_percent": 91,
            "wind_speed_kmph": 31
        }
    })

def valid_output() -> dict[str, Any]:
    return {
        "location": "Velachery",
        "disaster_type": "urban_flooding",
        "severity": "high",
        "severity_evidence": [
            {"statement": "The report describes knee-deep water and stopped traffic.", "source": "field_report"},
            {"statement": "The supplied 24-hour rainfall is 128 mm.", "source": "environmental_context"}
        ],
        "affected_people": ["commuters"],
        "resources_required": ["traffic management support"],
        "recommended_actions": ["Restrict access to visibly inundated roads where required by human responders."],
        "missing_information": ["Exact number of affected residents"],
        "situation_report": "Reported urban flooding near Velachery MRTS is disrupting traffic. The supplied rainfall measurements support an elevated flood concern."
    }

def test_pipeline_returns_validated_output() -> None:
    pipeline = CrisisLensPipeline(MockProvider(valid_output()))
    result = pipeline.analyse(valid_input())
    assert result.location == "Velachery"
    assert result.severity == "high"
    assert result.disaster_type == "urban_flooding"

def test_pipeline_rejects_location_change() -> None:
    output = valid_output()
    output["location"] = "Tambaram"
    pipeline = CrisisLensPipeline(MockProvider(output))
    with pytest.raises(ValueError, match="does not match"):
        pipeline.analyse(valid_input())

def test_environment_rejects_impossible_humidity() -> None:
    payload = valid_input().model_dump()
    payload["environment"]["humidity_percent"] = 140
    with pytest.raises(ValueError):
        CrisisInput.model_validate(payload)
