from fastapi.testclient import TestClient
import api


def start(client, scenario="waterlogging"):
    r = client.post("/api/simulations", json={"scenario": scenario})
    assert r.status_code == 201
    return r.json()


def advance(client, session, action="next"):
    r = client.post(f"/api/simulations/{session['id']}/events", json={"revision": session["revision"], "action": action})
    assert r.status_code == 200, r.text
    return r.json()


def draft(client, session, report=None):
    r = client.post(f"/api/simulations/{session['id']}/plans", json={"location": report["location"] if report else session["primary_area"], "report_id": report["id"] if report else None, "volunteers": 6, "resources": [{"kind": "water", "quantity": 80}], "notes": "SIMULATION test plan"})
    assert r.status_code == 201, r.text
    return r.json()


def approve(client, session, plan, **overrides):
    return client.post(f"/api/simulations/{session['id']}/plans/{plan['id']}", json={"revision": plan["revision"], "action": "approve", "contact_checked": True, "access_checked": True, "receiving_time_checked": True, "actor": "Test participant", "note": "SIMULATION: checked the current scenario evidence and receiving arrangement.", **overrides})


def test_training_journey_uses_real_plan_guards_and_never_changes_live_data():
    with TestClient(api.app) as client:
        live_before = client.get("/api/plans").json()
        s = start(client)
        assert s["reports"] == [] and s["simulation"]
        s = advance(client, s)
        s = draft(client, s, s["reports"][0])
        assert approve(client, s, s["plans"][0]).status_code == 409
        s = advance(client, s)
        s = draft(client, s, s["reports"][0])
        plan = s["plans"][0]
        assert approve(client, s, plan, access_checked=False).status_code == 409
        response = approve(client, s, plan)
        assert response.status_code == 200
        assert response.json()["plans"][0]["status"] == "approved"
        s = advance(client, response.json())
        assert s["reports"][0]["pending_updates"] == 1
        assert all(p["source_changed"] for p in s["plans"])
        s = advance(client, s)
        assert s["reports"][0]["resources"] == [{"kind": "water", "quantity": 80.0}]
        assert s["reports"][0]["pending_updates"] == 0
        assert len(s["reports"][0]["updates"]) == 2
        s = advance(client, s)
        assert s["reports"][0]["status"] == "resolved"
        assert client.get("/api/plans").json() == live_before
        assert all(client.get(f"/api/operations/{a}").json()["reports"] == [] for a in ("Velachery", "Tambaram", "Chromepet"))
        # A live endpoint cannot approve a simulation plan, even with its id.
        assert client.post(f"/api/plans/{plan['id']}", json={"revision": 0, "action": "save"}).status_code == 404


def test_rain_scenario_never_manufactures_demand_or_permits_response_approval():
    with TestClient(api.app) as client:
        s = start(client, "rain")
        s = draft(client, s)
        assert approve(client, s, s["plans"][0]).status_code == 409
        for _ in range(5):
            s = advance(client, s)
        assert s["weather"]["rain_mm"] == 1
        assert s["reports"][0]["status"] == "rejected"
        assert s["reports"][0]["resources"] == []
        assert s["reports"][0]["groups"] == []
        assert client.post(f"/api/simulations/{s['id']}/events", json={"revision": s["revision"], "action": "next"}).status_code == 409


def test_multi_area_outcome_does_not_silently_resolve_other_requests():
    with TestClient(api.app) as client:
        s = start(client, "multi")
        for _ in range(5):
            s = advance(client, s)
        reports = {r["location"]: r for r in s["reports"]}
        assert reports["Velachery"]["status"] == "resolved"
        assert reports["Tambaram"]["status"] == "reviewed" and reports["Tambaram"]["specialist"]
        assert reports["Chromepet"]["status"] == "reviewed"
        # Persisted state can be resumed without replaying events.
        assert client.get(f"/api/simulations/{s['id']}").json()["stage"] == 5


def test_reset_and_revision_guard_and_cross_session_isolation():
    with TestClient(api.app) as client:
        s = start(client, "urgent")
        old_revision = s["revision"]
        s = advance(client, s)
        report = s["reports"][0]
        assert client.post(f"/api/simulations/{s['id']}/events", json={"revision": old_revision}).status_code == 409
        other = start(client)
        assert client.post(f"/api/simulations/{other['id']}/plans", json={"location": "Tambaram", "report_id": report["id"], "resources": [], "volunteers": 3}).status_code == 404
        s = draft(client, s, report)
        s = advance(client, s, "reset")
        assert s["stage"] == 0 and not s["reports"] and not s["plans"]
        assert client.get("/api/simulations/not-a-uuid").status_code == 422


def test_urgent_story_keeps_rescue_role_distinct_and_completes():
    with TestClient(api.app) as client:
        s = start(client, "urgent")
        s = advance(client, s)
        assert s["reports"][0]["specialist"] is True
        assert "Trained rescue" in s["reports"][0]["needs"]
        for _ in range(4):
            s = advance(client, s)
        assert s["reports"][0]["status"] == "resolved"
        assert len(s["reports"][0]["updates"]) == 3
