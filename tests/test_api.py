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


def test_provider_error_does_not_leak_credentials(client, monkeypatch, caplog):
    monkeypatch.setenv("GEMINI_API_KEY", "private-key")
    def failing_provider(name):
        raise RuntimeError("upstream private-key and private report")
    monkeypatch.setattr(api, "build_provider", failing_provider)
    response = client.post("/api/analyse", json={"input": sample(client)})
    assert response.status_code == 502
    assert "private-key" not in response.text
    assert "private report" not in response.text
    assert "private-key" not in caplog.text
    assert "private report" not in caplog.text
    assert "category=unexpected" in caplog.text


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


@pytest.mark.parametrize("status,category,http_status", [(400, "request_rejected", 502), (401, "authentication", 502), (402, "billing", 502), (403, "permission", 502), (404, "model_access", 502), (429, "quota", 429), (503, "provider_unavailable", 503), (504, "timeout", 504)])
def test_real_gemini_errors_are_specific_and_safe(client, monkeypatch, caplog, status, category, http_status):
    from google.genai.errors import APIError
    monkeypatch.setenv("GEMINI_API_KEY", "private-key")
    def failing_provider(name):
        raise APIError(status, {"error": {"message": "private-key private report", "status": "TEST"}})
    monkeypatch.setattr(api, "build_provider", failing_provider)
    response = client.post("/api/analyse", json={"input": sample(client)})
    assert response.status_code == http_status
    assert response.headers["X-CrisisLens-Error"] == category
    assert f"upstream_status={status}" in caplog.text
    assert "private-key" not in response.text + caplog.text
    assert "private report" not in response.text + caplog.text


def test_gemini_invalid_key_400_is_authentication(client, monkeypatch):
    from google.genai.errors import APIError
    monkeypatch.setenv("GEMINI_API_KEY", "test-only")
    def failing_provider(name):
        raise APIError(400, {"error": {"message": "API key not valid. API_KEY_INVALID"}})
    monkeypatch.setattr(api, "build_provider", failing_provider)
    response = client.post("/api/analyse", json={"input": sample(client)})
    assert response.headers["X-CrisisLens-Error"] == "authentication"


def test_gemini_default_and_health_match(monkeypatch):
    from types import SimpleNamespace
    from crisislens.providers import gemini
    from crisislens.providers.gemini import GeminiProvider, DEFAULT_GEMINI_MODEL
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setattr(gemini.genai, "Client", lambda **kwargs: SimpleNamespace())
    provider = GeminiProvider(api_key="test-only")
    assert provider.model == DEFAULT_GEMINI_MODEL == api.health()["providers"]["gemini"]["model"]


@pytest.mark.parametrize("code,category", [("insufficient_quota", "api_billing_quota"), ("credit_balance_exhausted", "api_billing_quota"), ("organization_spend_limit_exceeded", "api_billing_quota"), ("project_spend_limit_exceeded", "api_billing_quota"), ("organization_usage_limit_exceeded", "api_billing_quota"), ("rate_limit_exceeded", "rate_limit"), ("slow_down", "rate_limit")])
def test_openai_429_distinguishes_billing_from_throttling(client, monkeypatch, caplog, code, category):
    import httpx
    from openai import RateLimitError
    monkeypatch.setenv("OPENAI_API_KEY", "private-key")
    def failing_provider(name):
        response = httpx.Response(429, request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
        raise RateLimitError("private-key private report", response=response, body={"error": {"code": code, "type": "insufficient_quota", "message": "private-key private report"}})
    monkeypatch.setattr(api, "build_provider", failing_provider)
    response = client.post("/api/analyse", json={"input": sample(client), "provider": "openai"})
    assert response.status_code == 429
    assert response.headers["X-CrisisLens-Error"] == category
    assert response.headers["X-CrisisLens-Provider-Code"] == code
    assert f"provider_code={code}" in caplog.text
    assert "private-key" not in response.text + caplog.text
    assert "private report" not in response.text + caplog.text


def test_unknown_provider_code_is_not_exposed():
    from crisislens.provider_failures import safe_provider_code
    error = RuntimeError("private-key")
    error.code = "private-key"
    error.body = {"error": {"code": "private report"}}
    assert safe_provider_code(error) is None


@pytest.mark.parametrize("value,quota_id,category", [("0", "GenerateRequestsPerMinutePerProjectPerModel-FreeTier", "quota_zero"), ("20", "GenerateRequestsPerDayPerProjectPerModel-FreeTier", "daily_quota"), ("20", "GenerateRequestsPerMinutePerProjectPerModel-FreeTier", "quota")])
def test_gemini_structured_quota_details(client, monkeypatch, value, quota_id, category):
    from google.genai.errors import APIError
    monkeypatch.setenv("GEMINI_API_KEY", "private-key")
    def fail(name):
        raise APIError(429, {"error": {"message": "private-key private report", "details": [{
            "@type": "type.googleapis.com/google.rpc.QuotaFailure",
            "violations": [{"quotaId": quota_id, "quotaValue": value}]
        }]}})
    monkeypatch.setattr(api, "build_provider", fail)
    response = client.post("/api/analyse", json={"input": sample(client)})
    assert response.headers["X-CrisisLens-Error"] == category
    assert "private-key" not in response.text
    assert "private report" not in response.text


def test_repository_env_loading_does_not_depend_on_working_directory(tmp_path, monkeypatch):
    from crisislens import config
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_MODEL=file-model\n")
    monkeypatch.setattr(config, "ENV_FILE", env_file)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.chdir(tmp_path.parent)
    config.load_environment()
    assert api.os.environ["OPENAI_MODEL"] == "file-model"


def test_repository_env_preserves_deployment_settings(tmp_path, monkeypatch):
    from crisislens import config
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_MODEL=file-model\n")
    monkeypatch.setattr(config, "ENV_FILE", env_file)
    monkeypatch.setenv("OPENAI_MODEL", "deployment-model")
    config.load_environment()
    assert api.os.environ["OPENAI_MODEL"] == "deployment-model"


def test_zero_quota_can_be_in_message_with_structured_violation():
    from google.genai.errors import APIError
    from crisislens.provider_failures import classify_provider_failure
    error = APIError(429, {"error": {"message": "Quota exceeded for metric, limit: 0, private-key", "details": [{
        "@type": "type.googleapis.com/google.rpc.QuotaFailure",
        "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]
    }]}})
    assert classify_provider_failure(error).category == "quota_zero"


def test_blank_settings_do_not_misreport_ready_key(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "  ")
    monkeypatch.setenv("OPENAI_API_KEY", "  ")
    assert api.health()["providers"]["openai"] == {"configured": False, "model": "gpt-5-mini"}
