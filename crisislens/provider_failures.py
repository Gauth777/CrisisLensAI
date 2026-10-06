"""Actionable provider diagnostics without returning upstream messages or secrets."""
from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class ProviderFailure:
    category: str
    detail: str
    upstream_status: int | None = None
    http_status: int = 502


def classify_provider_failure(exc: Exception) -> ProviderFailure:
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    status = status if isinstance(status, int) and not isinstance(status, bool) else None
    # Read upstream text only to recognise a fixed authentication signal. Never
    # include that text, request URL, response body or traceback in output/logs.
    invalid_key = "API_KEY_INVALID" in str(exc) or "api key not valid" in str(exc).lower()
    if status == 401 or (status == 400 and invalid_key):
        return ProviderFailure("authentication", "The provider rejected the API key. Check the key in backend .env, its project and restrictions, then restart the backend.", status)
    if status == 403:
        return ProviderFailure("permission", "The provider denied access (HTTP 403). Check API-key restrictions, project permissions and access to the configured model.", status)
    if status == 404:
        return ProviderFailure("model_access", "The configured model/resource is unavailable (HTTP 404). Verify the model ID and project access. New Gemini projects should use GEMINI_MODEL=gemini-3.5-flash-lite rather than the restricted 2.5 models; restart after editing .env.", status)
    if status == 429:
        return ProviderFailure("quota", "Provider quota or rate limit reached (HTTP 429). Check this project's model limits and billing in the provider console. Wait for reset if exhausted; if the limit is zero, retrying alone will not fix it.", status, 429)
    if status == 402:
        return ProviderFailure("billing", "The provider reports a billing/credit problem (HTTP 402). Check the API project's billing status and available credits.", status)
    if status == 400:
        return ProviderFailure("request_rejected", "The provider rejected the request (HTTP 400). Check API-key validity, project billing/region eligibility and model support for structured output.", status)
    if status in (408, 504) or isinstance(exc, (TimeoutError, httpx.TimeoutException)) or type(exc).__name__ == "APITimeoutError":
        return ProviderFailure("timeout", "The model request timed out. Check connectivity and provider availability, then retry.", status, 504)
    if status is not None and status >= 500:
        return ProviderFailure("provider_unavailable", "The model provider is temporarily unavailable. Retry shortly; check its service status if the failure persists.", status, 503)
    if isinstance(exc, (httpx.TransportError, ConnectionError, OSError)) or type(exc).__name__ == "APIConnectionError":
        return ProviderFailure("connectivity", "Cannot connect to the model provider. Check internet access, proxy/VPN settings and firewall restrictions on the backend machine.", status)
    return ProviderFailure("unexpected", "Unexpected model request failure. Share the safe 'CrisisLens failure' category from the backend terminal for diagnosis.", status)
