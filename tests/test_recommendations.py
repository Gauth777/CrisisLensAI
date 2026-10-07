from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import api
from crisislens.data.context import IST, parse_feed, parse_outlook
from crisislens.recommendations import RecommendationQuestion, recommend


def output():
    return {"location": "Velachery", "headline": "Verify local needs before allocating food kits",
            "answer": "The available weather does not establish local flooding or supply demand.",
            "claims": [{"statement": "Flooding is reported near the MRTS", "category": "incident", "status": "supported",
                        "explanation": "This is only a supplied report.", "source_ids": ["U1", "W1"]}],
            "recommendations": [{"title": "Contact a local coordinator", "explanation": "Verify needs before deployment.", "source_ids": ["U1"]}],
            "affected_groups": [], "supplies": [], "missing_information": ["Current street access"]}


def bundle():
    return {"sources": [{"id": "U1", "kind": "user", "scope": "locality", "content_scope": "unverified_input"},
                        {"id": "W1", "kind": "weather", "scope": "locality_grid", "content_scope": "modelled_weather"}],
            "source_status": [], "coverage_note": "Weather and unverified user input only."}


class Provider:
    model = "test"
    def __init__(self, result=None):
        self.result = result or output()
    def generate_json(self, **kwargs):
        assert "sources" in kwargs["user_prompt"]
        assert "claims" in kwargs["output_schema"]["properties"]
        return deepcopy(self.result)


def test_weather_and_user_input_cannot_confirm_flooding():
    result = recommend(Provider(), RecommendationQuestion(location="Velachery", question="Is this flood report supported?"), bundle())
    assert result.claims[0].status == "insufficient_evidence"


def test_weather_can_support_weather_claim_but_absence_cannot_disprove_incident():
    response = output()
    response["claims"][0].update(category="weather", statement="The supplied model forecast indicates rain")
    assert recommend(Provider(response), RecommendationQuestion(location="Velachery", question="What is the weather?"), bundle()).claims[0].status == "supported"
    response["claims"][0].update(category="incident", status="contradicted", source_ids=[])
    assert recommend(Provider(response), RecommendationQuestion(location="Velachery", question="What is the weather?"), bundle()).claims[0].status == "insufficient_evidence"


@pytest.mark.parametrize("change", ["unknown_source", "location"])
def test_fabricated_citations_and_location_are_rejected(change):
    response = output()
    if change == "location": response["location"] = "Tambaram"
    else: response["recommendations"][0]["source_ids"] = ["FAKE"]
    with pytest.raises(ValueError):
        recommend(Provider(response), RecommendationQuestion(location="Velachery", question="Which evidence?"), bundle())


def test_city_news_and_headline_only_cannot_confirm_locality():
    for scope, content_scope in [("city_context", "feed_excerpt"), ("locality", "headline_only")]:
        evidence = bundle()
        evidence["sources"].append({"id": "N1", "kind": "news", "scope": scope, "content_scope": content_scope})
        response = output()
        response["claims"][0]["source_ids"] = ["N1"]
        result = recommend(Provider(response), RecommendationQuestion(location="Velachery", question="Is the incident real?"), evidence)
        assert result.claims[0].status == "insufficient_evidence"


def test_demo_never_has_confirmation_even_with_independent_record():
    response = output()
    response["claims"][0].update(category="weather")
    result = recommend(Provider(response), RecommendationQuestion(location="Velachery", question="Hypothetical situation", demo=True), bundle())
    assert result.claims[0].status == "insufficient_evidence"
    assert result.answer.startswith("Hypothetical demonstration")


def test_feed_filters_stale_future_wrong_locality_and_untrusted_links():
    now = datetime(2026, 10, 7, tzinfo=timezone.utc)
    def item(title, link, date, description="A publisher reports waterlogging near Velachery."):
        return f"<item><title>{title}</title><link>{link}</link><pubDate>{date}</pubDate><description>{description}</description></item>"
    raw = ("<rss><channel>" +
        item("Velachery flooding report", "https://indianexpress.com/article/example", "Tue, 06 Oct 2026 18:00:00 GMT") +
        item("Chennai rainfall forecast", "https://indianexpress.com/article/city", "Tue, 06 Oct 2026 19:00:00 GMT", "Chennai weather outlook") +
        item("Velachery old flood", "https://indianexpress.com/article/old", "Tue, 01 Sep 2026 18:00:00 GMT") +
        item("Velachery future flood", "https://indianexpress.com/article/future", "Thu, 08 Oct 2026 18:00:00 GMT") +
        item("Velachery flood", "http://127.0.0.1/private", "Tue, 06 Oct 2026 18:00:00 GMT") +
        "</channel></rss>").encode()
    records = parse_feed(raw, "The Indian Express", "indianexpress.com", "Velachery", now)
    assert len(records) == 2
    assert records[0]["scope"] == "locality"
    assert records[1]["scope"] == "city_context"
    assert records[0]["published_at"] != records[0]["retrieved_at"]


def test_feed_rejects_xml_entity_expansion():
    with pytest.raises(ValueError):
        parse_feed(b'<!DOCTYPE rss [<!ENTITY x "secret">]><rss/>', "Test", "example.com", "Velachery", datetime.now(timezone.utc))


def weather_payload():
    now = datetime(2026, 10, 7, 1, 30, tzinfo=IST)
    times = [(now.replace(minute=0) + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(25)]
    return now, {"current": {"time": "2026-10-07T01:15", "temperature_2m": 28},
                 "hourly": {"time": times, "precipitation": [0, 0.2] + [0] * 23, "precipitation_probability": [20] * 25}}


def test_forecast_selects_first_future_rain_without_claiming_exact_onset():
    now, payload = weather_payload()
    outlook = parse_outlook(payload, now)
    assert outlook["next_rain"]["time"] == "2026-10-07T02:00:00+05:30"
    assert outlook["next_rain"]["probability_percent"] == 20
    assert outlook["environment"]["water_level_m"] is None
    assert outlook["forecast_complete"]


def test_missing_forecast_values_and_stale_weather_are_not_dry_forecasts():
    now, payload = weather_payload()
    payload["hourly"]["precipitation"] = [None] * 25
    outlook = parse_outlook(payload, now)
    assert outlook["next_rain"] is None
    assert not outlook["forecast_complete"]
    payload["current"]["time"] = "2026-10-01T01:15"
    with pytest.raises(ValueError): parse_outlook(payload, now)


def test_recommend_api_returns_actual_bundle_and_does_not_cache_user_input(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "private-key")
    evidence = bundle()
    evidence["sources"] = evidence["sources"][1:]
    evidence.update(location="Velachery", retrieved_at="2026-10-07T00:00:00Z", outlook=None)
    monkeypatch.setattr(api, "collect_context", lambda location: deepcopy(evidence))
    monkeypatch.setattr(api, "build_provider", lambda name: Provider())
    with TestClient(api.app) as client:
        response = client.post("/api/recommend", json={"provider": "groq", "location": "Velachery", "question": "Please verify this flood report."})
        assert response.status_code == 200
        body = response.json()
        assert body["recommendation"]["claims"][0]["status"] == "insufficient_evidence"
        assert body["context"]["sources"][-1]["id"] == "U1"
        assert "private-key" not in response.text
        assert len(evidence["sources"]) == 1


def test_recommend_api_refuses_unknown_citations(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "private-key")
    monkeypatch.setattr(api, "collect_context", lambda location: bundle())
    response = output()
    response["claims"][0]["source_ids"] = ["invented-proof"]
    monkeypatch.setattr(api, "build_provider", lambda name: Provider(response))
    with TestClient(api.app) as client:
        result = client.post("/api/recommend", json={"location": "Velachery", "question": "Is this real?"})
        assert result.status_code == 502
        assert "recommendation" not in result.json()


@pytest.mark.parametrize("kind,scope,category,expected", [
    ("official_alert", "official_warning", "warning", "supported"),
    ("official_alert", "official_warning", "incident", "insufficient_evidence"),
    ("official_alert", "official_warning", "needs", "insufficient_evidence"),
    ("field_report", "unverified_input", "incident", "insufficient_evidence"),
    ("field_report", "reviewed_report", "incident", "supported"),
])
def test_operational_evidence_cannot_promote_warning_or_unreviewed_report_to_incident(kind, scope, category, expected):
    evidence = bundle()
    evidence["sources"].append({"id": "O1", "kind": kind, "scope": "district" if kind == "official_alert" else "locality", "content_scope": scope})
    response = output()
    response["claims"][0].update(category=category, source_ids=["O1"])
    result = recommend(Provider(response), RecommendationQuestion(location="Velachery", question="What is supported?"), evidence)
    assert result.claims[0].status == expected
