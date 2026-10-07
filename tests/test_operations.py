"""Explicit synthetic CAP fixtures. No fixture is used as live application data."""
from datetime import timedelta
from xml.sax.saxutils import escape

import pytest
from fastapi.testclient import TestClient

from crisislens.data.operations import (Operations, FieldReport, Review, RSS, utcnow,
                                        parse_cap, feed_urls, operational_sources)

NOW = utcnow()
URL = "https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=100"


def cap(identifier="test-1", message="Alert", references="", status="Actual", expires=None, district="Chengalpattu", effective=None):
    expires = expires if expires is not None else (NOW + timedelta(hours=2)).isoformat()
    return f'''<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
    <identifier>{identifier}</identifier><sender>IMD-Chennai</sender><sent>{NOW.isoformat()}</sent>
    <status>{status}</status><scope>Public</scope><msgType>{message}</msgType><references>{references}</references>
    <info><language>en-IN</language><event>TEST rain warning</event><severity>Moderate</severity>
    <certainty>Possible</certainty><headline>TEST warning; not a real incident.</headline>
    <effective>{effective or NOW.isoformat()}</effective><expires>{expires}</expires>
    <instruction>TEST instruction</instruction><area><areaDesc>{district} districts of Tamil Nadu</areaDesc></area></info></alert>'''.encode()


def feed(*urls):
    return ('<rss><channel>' + ''.join(f'<item><author>controlroom@ndma.gov.in (IMD Chennai)</author><link>{escape(u)}</link></item>' for u in urls) + '</channel></rss>').encode()


def seed(store, records):
    store.poll(lambda url: feed(*records) if url == RSS else records[url])


def report():
    return FieldReport(location="Tambaram", landmark="TEST landmark", observed_at=NOW,
                       description="TEST ONLY: volunteer reports standing water.", needs="TEST request for food")


def review(revision=0, status="reviewed"):
    return Review(revision=revision, status=status, reviewer="Test reviewer", method="phone",
                  note="TEST ONLY: contacted the reporting volunteer and checked location and time.")


def test_official_district_warning_is_not_a_local_incident(tmp_path):
    store = Operations(tmp_path / "ops.db")
    seed(store, {URL: cap()})
    snapshot = store.snapshot("Tambaram", NOW + timedelta(seconds=1))
    assert snapshot["alerts"][0]["match_scope"] == "district"
    assert snapshot["alerts"][0]["state"] == "active"
    assert not snapshot["feed"]["stale"]
    assert not store.snapshot("Velachery")["alerts"]
    assert operational_sources(snapshot)[0]["content_scope"] == "official_warning"
    assert not store.snapshot("Tambaram", NOW + timedelta(hours=3))["alerts"]


def test_cap_timestamps_test_alerts_and_substring_matching(tmp_path):
    store = Operations(tmp_path / "ops.db")
    seed(store, {URL: cap(status="Test")})
    assert not store.snapshot("Tambaram")["alerts"]
    parsed = parse_cap(cap(district="NotChennai"), URL, NOW)
    assert parsed["infos"][0]["locations"] == []
    parsed = parse_cap(cap(expires="2026-10-07T16:00:00+05:30"), URL, NOW)
    assert parsed["infos"][0]["expires_at"].endswith("+05:30")
    with pytest.raises(ValueError):
        parse_cap(b'<!DOCTYPE x><alert/>', URL, NOW)


def test_missing_expiry_and_future_effective_are_not_current_evidence(tmp_path):
    store = Operations(tmp_path / "ops.db")
    other = URL.replace("100", "101")
    seed(store, {URL: cap(expires=""), other: cap(identifier="test-2", effective=(NOW + timedelta(hours=1)).isoformat())})
    snapshot = store.snapshot("Tambaram", NOW)
    assert {a["state"] for a in snapshot["alerts"]} == {"unknown_expiry", "scheduled"}
    assert operational_sources(snapshot) == []


def test_updates_cancellations_dedup_and_restart(tmp_path):
    path = tmp_path / "ops.db"
    store = Operations(path)
    update_url, cancel_url = URL.replace("100", "101"), URL.replace("100", "102")
    seed(store, {URL: cap()})
    seed(store, {URL: cap(), update_url: cap("test-2", "Update", f"IMD-Chennai,test-1,{NOW.isoformat()}")})
    assert [a["identifier"] for a in store.snapshot("Tambaram")["alerts"]] == ["test-2"]
    seed(store, {cancel_url: cap("test-3", "Cancel", f"IMD-Chennai,test-2,{NOW.isoformat()}")})
    assert not Operations(path).snapshot("Tambaram")["alerts"]
    called = []
    store.poll(lambda url: called.append(url) or feed(URL, update_url, cancel_url))
    assert called == [RSS]


def test_feed_failure_partial_failure_and_age_mark_cached_records_stale(tmp_path):
    store = Operations(tmp_path / "ops.db")
    seed(store, {URL: cap()})
    assert store.snapshot("Tambaram", NOW + timedelta(minutes=6))["feed"]["stale"]
    def fail(url):
        raise OSError("Disconnected")
    store.poll(fail)
    snapshot = store.snapshot("Tambaram")
    assert snapshot["alerts"] and snapshot["feed"]["stale"]
    assert operational_sources(snapshot) == []
    seed(store, {URL: cap(), URL.replace("100", "101"): b"not xml"})
    assert store.snapshot("Tambaram")["feed"]["failed_entries"] == 1
    assert store.snapshot("Tambaram")["feed"]["stale"]


def test_feed_does_not_fetch_arbitrary_links_or_generic_ndma_author():
    assert feed_urls(feed(URL, "https://evil.example/secret", URL + "&other=x")) == [URL]
    assert feed_urls(feed(URL).replace(b"IMD Chennai", b"IMD Jaipur")) == []


def test_report_review_audit_revision_and_observation_freshness(tmp_path):
    path = tmp_path / "ops.db"
    store = Operations(path)
    record = store.submit(report())
    assert operational_sources(store.snapshot("Tambaram")) == []
    store.review(record["id"], review())
    snapshot = Operations(path).snapshot("Tambaram")
    assert operational_sources(snapshot)[0]["kind"] == "field_report"
    assert len(snapshot["reports"][0]["review_history"]) == 1
    with pytest.raises(ValueError):
        store.review(record["id"], review())
    assert operational_sources(store.snapshot("Tambaram", NOW + timedelta(hours=7))) == []
    store.review(record["id"], review(1, "resolved"))
    snapshot = store.snapshot("Tambaram")
    assert len(snapshot["reports"][0]["review_history"]) == 2
    assert operational_sources(snapshot) == []
    with pytest.raises(ValueError):
        FieldReport(**{**report().model_dump(), "observed_at": NOW.replace(tzinfo=None)})


def test_api_without_model_key_and_protected_review(tmp_path, monkeypatch):
    import api
    monkeypatch.setattr(api, "_operations", Operations(tmp_path / "api.db"))
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("CRISISLENS_REVIEW_TOKEN", raising=False)
    client = TestClient(api.app)
    assert client.get("/api/operations/Tambaram").status_code == 200
    result = client.post("/api/reports", json=report().model_dump(mode="json"))
    assert result.status_code == 201 and result.json()["status"] == "unreviewed"
    url = f'/api/reports/{result.json()["id"]}/review'
    body = review().model_dump()
    assert client.post(url, json=body).status_code == 503
    monkeypatch.setenv("CRISISLENS_REVIEW_TOKEN", "test-only-review-token")
    assert client.post(url, json=body).status_code == 403
    assert client.post(url, json=body, headers={"X-Review-Token": "wrong"}).status_code == 403
    assert client.post(url, json=body, headers={"X-Review-Token": "test-only-review-token"}).status_code == 200
    assert client.post(url, json=body, headers={"X-Review-Token": "test-only-review-token"}).status_code == 409
