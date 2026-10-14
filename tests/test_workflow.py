from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
import api
from crisislens.workflow import Workflow, ReportInput, UpdateReview, ReportUpdate, PlanInput, PlanChange
from crisislens.data.operations import utcnow, operational_sources


def report():
    return ReportInput(location="Velachery", landmark="TEST community hall", observed_at=utcnow(),
                       description="TEST ONLY: coordinator requests drinking water.", needs="Water requested", resources=[{"kind":"water","quantity":40}])


def review(revision=0, **kwargs):
    return UpdateReview(revision=revision, status=kwargs.pop("status","reviewed"), reviewer="Test coordinator", method="phone", note="TEST ONLY: contact and request were checked.", **kwargs)


def plan(report_id=None):
    return PlanInput(location="Velachery", report_id=report_id, volunteers=6, resources=[{"kind":"water","quantity":50}])


def approve(revision=0, **kwargs):
    return PlanChange(revision=revision, action="approve", actor="Test coordinator", note="TEST ONLY: access, contact and receiving time checked.", contact_checked=True, receiving_time_checked=True, access_checked=kwargs.get("access", True))


def test_plan_persistence_revision_and_approval_checks(tmp_path):
    path=tmp_path/"workflow.db"
    store=Workflow(path)
    r=store.submit(report())
    draft=store.create_plan(plan(r["id"]))
    with pytest.raises(ValueError): store.change_plan(draft["id"], approve())
    store.review(r["id"], review())
    with pytest.raises(ValueError): store.change_plan(draft["id"], approve())
    draft=store.create_plan(plan(r["id"]))
    with pytest.raises(ValueError): store.change_plan(draft["id"], approve(access=False))
    saved=store.change_plan(draft["id"], approve())
    assert saved["status"] == "approved"
    assert len(Workflow(path).plans()) == 2
    with pytest.raises(ValueError): store.change_plan(draft["id"], approve())
    assert store.change_plan(draft["id"], PlanChange(revision=1, action="close", note="TEST: delivery plan is no longer needed."))["status"] == "closed"
    assert store.snapshot("Velachery")["reports"][0]["status"] == "reviewed"


def test_pending_update_cannot_silently_resolve_report_or_allow_approval(tmp_path):
    store=Workflow(tmp_path/"ops.db")
    r=store.submit(report());store.review(r["id"],review())
    draft=store.create_plan(plan(r["id"]))
    update=store.add_update(r["id"], ReportUpdate(outcome="resolved", observed_at=utcnow(), note="TEST: reporting volunteer says the request has ended.", needs="", resources=[]))
    snap=store.snapshot("Velachery")
    assert snap["reports"][0]["status"] == "reviewed"
    assert snap["reports"][0]["pending_updates"] == 1
    assert operational_sources(snap) == []
    with pytest.raises(ValueError): store.change_plan(draft["id"],approve())
    with pytest.raises(ValueError): store.review(r["id"],review(1,update_id=update["id"]))
    store.review(r["id"],review(1,update_id=update["id"],status="resolved"))
    assert store.snapshot("Velachery")["reports"][0]["status"] == "resolved"
    assert store.plans()[0]["source_changed"]


def test_rejected_update_preserves_previously_reviewed_report(tmp_path):
    store=Workflow(tmp_path/"ops.db")
    r=store.submit(report());store.review(r["id"],review())
    u=store.add_update(r["id"],ReportUpdate(outcome="still_needed",observed_at=utcnow(),note="TEST: disputed update about conditions and needs.",needs="Different need"))
    store.review(r["id"],review(1,update_id=u["id"],status="rejected"))
    current=store.snapshot("Velachery")["reports"][0]
    assert current["status"] == "reviewed" and current["needs"] == "Water requested"
    assert current["pending_updates"] == 0
    assert len(current["review_history"]) == 2
    assert operational_sources(store.snapshot("Velachery"))


def test_old_observation_cannot_be_refreshed_by_review_alone(tmp_path):
    store=Workflow(tmp_path/"ops.db")
    r=report().model_copy(update={"observed_at":utcnow()-timedelta(hours=7)})
    entry=store.submit(r);store.review(entry["id"],review())
    draft=store.create_plan(plan(entry["id"]))
    with pytest.raises(ValueError): store.change_plan(draft["id"],approve())
    assert operational_sources(store.snapshot("Velachery")) == []
    with pytest.raises(ValueError): store.change_plan(store.create_plan(plan())["id"],approve())


def test_api_requires_token_for_approval_and_closure(monkeypatch):
    monkeypatch.setenv("CRISISLENS_REVIEW_TOKEN","test-token")
    client=TestClient(api.app)
    r=client.post("/api/reports",json=report().model_dump(mode="json")).json()
    assert client.post(f'/api/reports/{r["id"]}/review',json=review().model_dump(),headers={"X-Review-Token":"test-token"}).status_code == 200
    draft=client.post("/api/plans",json=plan(r["id"]).model_dump()).json()
    url=f'/api/plans/{draft["id"]}'
    assert client.post(url,json=approve().model_dump()).status_code == 403
    assert client.post(url,json=approve().model_dump(),headers={"X-Review-Token":"test-token"}).status_code == 200
    assert client.get("/api/plans").json()[0]["status"] == "approved"
    assert client.post(url,json=PlanChange(revision=1,action="close",note="TEST closure for a completed response.").model_dump()).status_code == 403


def test_saved_briefing_cannot_be_attached_to_different_resources(tmp_path):
    store=Workflow(tmp_path/"ops.db")
    briefing=store.save_briefing({"question":{"location":"Velachery","report_id":None,"resources":[],"volunteers":0}})
    with pytest.raises(ValueError): store.create_plan(plan().model_copy(update={"briefing_id":briefing}))
    good=store.create_plan(PlanInput(location="Velachery",volunteers=0,briefing_id=briefing))
    assert good["briefing"]["question"]["location"] == "Velachery"
