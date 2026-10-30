from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
import api
from crisislens.workflow import Workflow, ReportInput, UpdateReview, PlanInput, PlanChange
from crisislens.reliability import resource_check
from crisislens.data.operations import utcnow, operational_sources
from crisislens.intelligence_eval import run_evaluation


def add(store, access="passable", amount=120, landmark="Community hall"):
    r = store.submit(ReportInput(location="Velachery", landmark=landmark, observed_at=utcnow(), description="Training request for drinking water at the community point.", needs="Water requested", resources=[{"kind":"water","quantity":amount}], access_status=access))
    store.review(r["id"], UpdateReview(revision=0,status="reviewed",reviewer="Test coordinator",method="phone",note="Training: called the contact to check the report."))
    return r


def test_conflict_blocks_sources_and_approval_until_reconciled(tmp_path):
    store=Workflow(tmp_path/"test.sqlite3")
    a=add(store);b=add(store,"blocked",200,"COMMUNITY HALL")
    snapshot=store.snapshot("Velachery")
    assert all(r["conflicts"] for r in snapshot["reports"])
    assert operational_sources(snapshot)==[]
    plan=store.create_plan(PlanInput(location="Velachery",report_id=a["id"],volunteers=4,resources=[{"kind":"water","quantity":80}]))
    approval=PlanChange(revision=0,action="approve",contact_checked=True,access_checked=True,receiving_time_checked=True,actor="Test",note="Training contact and receiving time checked.")
    with pytest.raises(ValueError,match="Conflicting"):
        store.change_plan(plan["id"],approval)
    assert store.plans()[0]["source_changed"]
    assert store.plans()[0]["resource_check"]["rows"][0]["suggested_max"] is None
    store.review(b["id"],UpdateReview(revision=1,status="rejected",reviewer="Test",method="phone",note="Training: follow-up established second record was wrong."))
    assert not store.snapshot("Velachery")["reports"][1]["conflicts"]
    assert store.change_plan(plan["id"],approval)["status"]=="approved"


def test_distinct_sites_do_not_conflict_and_quantities_are_capped(tmp_path):
    store=Workflow(tmp_path/"test.sqlite3")
    add(store);add(store,"blocked",200,"Another hall")
    reports=store.snapshot("Velachery")["reports"]
    assert all(not r["conflicts"] for r in reports)
    report=next(r for r in reports if r["access_status"]=="passable")
    check=resource_check(report,[{"kind":"water","quantity":80}])
    assert check["rows"][0]["suggested_max"]==80
    assert check["rows"][0]["uncovered"]==40
    assert resource_check({**report,"resources":[]},[])["status"]=="hold_for_check"
    assert resource_check({**report,"observed_at":(utcnow()-timedelta(hours=7)).isoformat()},[])["status"]=="hold_for_check"


def test_benchmark_is_explicitly_not_model_accuracy():
    r=run_evaluation()
    assert r["total"]==10 and r["passed"]==10
    assert r["mode"]=="scripted_guardrail_test" and r["human_factual_accuracy"] is None
    assert r["raw_claim_status_matches"] is None and r["claim_status_matches"]==6
    assert r["dataset_version"]=="evidence-challenge-v2"
    assert all(row["model_calls"]==3 and row["evidence_assessment"]["method"]=="source-passages-v3" for row in r["cases"][:6])


@pytest.mark.parametrize("scenario",["conflict","incomplete"])
def test_scenarios_exercise_uncertainty(scenario):
    with TestClient(api.app) as c:
        s=c.post("/api/simulations",json={"scenario":scenario}).json()
        for _ in range(2):
            s=c.post(f"/api/simulations/{s['id']}/events",json={"revision":s["revision"]}).json()
        if scenario=="conflict":
            assert len(s["reports"])==2
            assert all(r["conflicts"] for r in s["reports"])
        else:
            assert not s["reports"][0]["resources"]
        for _ in range(3):
            response=c.post(f"/api/simulations/{s['id']}/events",json={"revision":s["revision"]})
            assert response.status_code==200,response.text
            s=response.json()
        assert any(r["status"]=="resolved" for r in s["reports"])


def test_duplicate_resource_categories_are_rejected():
    with pytest.raises(ValueError, match="one quantity"):
        PlanInput(location="Velachery", volunteers=2, resources=[{"kind":"water","quantity":80},{"kind":"water","quantity":80}])


def test_provisional_quantity_preserves_request_identity_and_missing_checks():
    report={'id':'selected','status':'reviewed','observed_at':utcnow().isoformat(),
        'resources':[{'kind':'water','quantity':40}],'access_status':'unknown','demand_status':'unknown'}
    check=resource_check(report,[{'kind':'water','quantity':50}])
    assert check['report_id']=='selected' and check['source_id']=='Fselected'
    assert check['rows'][0]['suggested_max']==40
    assert 'Current access is not recorded' in check['missing_checks']
    assert 'Current demand status is not recorded' in check['missing_checks']
