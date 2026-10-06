from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import api
from crisislens.data.environment import EnvironmentalDataError
from crisislens.providers.base import LLMProvider


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return TestClient(api.app)


def sample(client):
    return client.get("/api/scenarios").json()[0]["input"]


class StubProvider(LLMProvider):
    model = "test-model"

    def generate_json(self, **kwargs):
        return {
            "location": "Velachery", "disaster_type": "urban_flooding", "severity": "high",
            "severity_evidence": [{"statement": "The report describes stopped traffic.", "source": "field_report"}],
            "affected_people": ["commuters"], "resources_required": ["Traffic support"],
            "recommended_actions": ["Human responders should verify affected roads."],
            "missing_information": ["Exact incident address"],
            "situation_report": "The supplied report describes traffic disruption near Velachery MRTS.",
        }


def test_health_and_samples_do_not_require_credentials(client):
    health = client.get("/api/health").json()
    assert health["status"] == "ok"
    assert not health["providers"]["gemini"]["configured"]
    samples = client.get("/api/scenarios").json()
    assert len(samples) == 3
    assert all(s["input"]["environment"]["source_kind"] == "manual_development_input" for s in samples)


def test_missing_key_is_actionable(client):
    response = client.post("/api/analyse", json={"input": sample(client), "provider": "gemini"})
    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]


def test_analysis_uses_pipeline_and_returns_input_snapshot(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only")
    monkeypatch.setattr(api, "build_provider", lambda name: StubProvider())
    payload = sample(client)
    response = client.post("/api/analyse", json={"input": payload, "provider": "gemini"})
    assert response.status_code == 200
    body = response.json()
    assert body["assessment"]["severity"] == "high"
    assert body["input"] == payload
    assert body["metadata"]["model"] == "test-model"
    assert body["metadata"]["latency_ms"] >= 0


def test_location_mismatch_never_becomes_assessment(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only")
    monkeypatch.setattr(api, "build_provider", lambda name: StubProvider())
    payload = sample(client)
    payload["location"] = "Tambaram"
    response = client.post("/api/analyse", json={"input": payload})
    assert response.status_code == 502
    assert "assessment" not in response.json()


def test_provider_error_does_not_leak_credentials(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "private-key")
    def failing_provider(name):
        raise RuntimeError("upstream private-key and private report")
    monkeypatch.setattr(api, "build_provider", failing_provider)
    response = client.post("/api/analyse", json={"input": sample(client)})
    assert response.status_code == 502
    assert "private-key" not in response.text
    assert "private report" not in response.text


@pytest.mark.parametrize("change", [{"location": "Mumbai"}, {"report": "hi"}, {"report": "     "}, {"report": "x" * 12001}, {"environment": {"humidity_percent": 101}}])
def test_invalid_input_is_rejected_before_model_call(client, change):
    payload = sample(client)
    payload.update(change)
    assert client.post("/api/analyse", json={"input": payload}).status_code == 422


def test_weather_failure_is_explicit(client, monkeypatch):
    def failure(self, location):
        raise EnvironmentalDataError("offline")
    monkeypatch.setattr(api.OpenMeteoWeatherClient, "fetch", failure)
    response = client.get("/api/weather/Velachery")
    assert response.status_code == 503
    assert "Weather unavailable" in response.json()["detail"]
    assert client.get("/api/weather/Mumbai").status_code == 422
