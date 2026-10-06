from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from openai import OpenAI
from openai import _base_client as sdk_transport

import api
from crisislens.providers.groq_provider import DEFAULT_GROQ_MODEL, GroqProvider
from crisislens.schemas import CrisisOutput
from test_api import StubProvider

httpx = getattr(sdk_transport, "httpx", None) or sdk_transport.httpx2


@pytest.fixture(autouse=True)
def isolated_transport(monkeypatch):
    # All requests below use MockTransport; don't initialise runner proxy mounts.
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(name, raising=False)


def completion(content, finish_reason="stop"):
    return {"id": "test", "object": "chat.completion", "created": 0,
            "model": DEFAULT_GROQ_MODEL,
            "choices": [{"index": 0, "finish_reason": finish_reason,
                         "message": {"role": "assistant", "content": content}}]}


def test_groq_uses_separate_endpoint_and_key(monkeypatch):
    from crisislens.providers import groq_provider
    captured = {}
    monkeypatch.setenv("OPENAI_API_KEY", "wrong-provider-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://wrong-endpoint.invalid")
    def client(**kwargs):
        captured.update(kwargs)
        return object()
    monkeypatch.setattr(groq_provider, "OpenAI", client)
    provider = GroqProvider(api_key="groq-private-key")
    assert captured["api_key"] == "groq-private-key"
    assert captured["base_url"] == "https://api.groq.com/openai/v1"
    assert captured["max_retries"] == 0
    assert provider.model == DEFAULT_GROQ_MODEL


def test_groq_http_contract_through_real_sdk_and_pipeline(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq-private-key")
    received = []
    def handler(request):
        assert request.url == "https://api.groq.com/openai/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer groq-private-key"
        body = json.loads(request.content)
        received.append(body)
        assert body["response_format"]["json_schema"]["strict"] is True
        assert body["response_format"]["json_schema"]["schema"] == CrisisOutput.model_json_schema()
        assert "tools" not in body
        return httpx.Response(200, json=completion(json.dumps(StubProvider().generate_json())))
    provider = GroqProvider()
    provider.client.close()
    provider.client = OpenAI(api_key="groq-private-key", base_url="https://api.groq.com/openai/v1",
                             http_client=httpx.Client(transport=httpx.MockTransport(handler)), max_retries=0)
    monkeypatch.setattr(api, "build_provider", lambda name: provider)
    with TestClient(api.app) as client:
        payload = client.get("/api/scenarios").json()[0]["input"]
        response = client.post("/api/analyse", json={"provider": "groq", "input": payload})
    provider.client.close()
    assert response.status_code == 200
    assert response.json()["metadata"]["provider"] == "groq"
    assert len(received) == 1
    assert "groq-private-key" not in response.text


@pytest.mark.parametrize("content,reason", [("{}", "length"), (None, "stop"), ("[]", "stop"), ("not json", "stop")])
def test_groq_never_accepts_incomplete_or_nonobject_output(content, reason):
    provider = GroqProvider(api_key="test-only")
    provider.client.close()
    provider.client = OpenAI(api_key="test-only", base_url="https://api.groq.com/openai/v1",
                             http_client=httpx.Client(transport=httpx.MockTransport(
                                 lambda request: httpx.Response(200, json=completion(content, reason)))), max_retries=0)
    with pytest.raises(ValueError):
        provider.generate_json(system_prompt="Return JSON.", user_prompt="Test")
    provider.client.close()


def test_groq_missing_key_is_actionable(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with TestClient(api.app) as client:
        payload = client.get("/api/scenarios").json()[0]["input"]
        response = client.post("/api/analyse", json={"provider": "groq", "input": payload})
    assert response.status_code == 503
    assert "GROQ_API_KEY" in response.json()["detail"]


def test_groq_rate_limit_is_not_reported_as_openai_billing(monkeypatch):
    from openai import RateLimitError
    monkeypatch.setenv("GROQ_API_KEY", "private-key")
    def fail(name):
        raise RateLimitError("private-key private report", response=httpx.Response(429,
                             request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")),
                             body={"error": {"code": "rate_limit_exceeded"}})
    monkeypatch.setattr(api, "build_provider", fail)
    with TestClient(api.app) as client:
        payload = client.get("/api/scenarios").json()[0]["input"]
        response = client.post("/api/analyse", json={"provider": "groq", "input": payload})
    assert response.status_code == 429
    assert "Groq" in response.json()["detail"]
    assert "OpenAI" not in response.text
    assert "private-key" not in response.text
