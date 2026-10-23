"""Fictional training sessions. Never read or write the live operations database."""
from __future__ import annotations
import json
import os
import threading
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from .workflow import Workflow, ReportInput, ReportUpdate, UpdateReview, PlanInput, PlanChange
from .data.operations import utcnow, timestamp

router = APIRouter(prefix="/api/simulations", tags=["Fictional simulations"])
lock = threading.RLock()
AREAS = ("Velachery", "Tambaram", "Chromepet")
SCENARIOS = {
    "rain": {"id": "rain", "title": "Rain is not a rescue call", "area": "Chromepet", "eyebrow": "01 / READ THE SIGNALS", "summary": "A wet forecast. An unverified message. Would you mobilise?", "lesson": "Separate forecast rain from an actual request for help.", "duration": "3 min", "level": "Preparedness", "rain": 4},
    "waterlogging": {"id": "waterlogging", "title": "From report to response", "area": "Velachery", "eyebrow": "02 / FOLLOW THE EVIDENCE", "summary": "Waterlogging disrupts access. A community asks for drinking water.", "lesson": "Check a request, prepare supplies and adapt when access changes.", "duration": "5 min", "level": "Local response", "rain": 28},
    "urgent": {"id": "urgent", "title": "Every decision matters", "area": "Tambaram", "eyebrow": "03 / KNOW YOUR ROLE", "summary": "Residents need trained rescue. Your team has supplies, not rescue equipment.", "lesson": "Keep urgent rescue visible while planning support within your capability.", "duration": "5 min", "level": "Urgent assistance", "rain": 42},
    "multi": {"id": "multi", "title": "Three areas. One team.", "area": "All three areas", "eyebrow": "04 / MAKE THE TRADE-OFF", "summary": "Different needs, limited supplies and an access update that changes your plan.", "lesson": "Compare evidenced needs and resource fit without hiding unmet requests.", "duration": "6 min", "level": "Coordination", "rain": 35},
}
SCENARIOS.update({
    "conflict": {"id":"conflict", "title":"The stories don’t agree", "area":"Velachery", "eyebrow":"05 / RESOLVE DISAGREEMENT", "summary":"Two reports. One site. Different quantities and opposite access observations.", "lesson":"Hold recommendations until the conflicting records are reconciled.", "duration":"5 min", "level":"Conflicting reports", "rain":28},
    "incomplete": {"id":"incomplete", "title":"Help needed. How much?", "area":"Velachery", "eyebrow":"06 / KEEP THE UNKNOWN VISIBLE", "summary":"A water request is corroborated, but nobody has established the quantity.", "lesson":"Do not invent supply quantities when the request is incomplete.", "duration":"4 min", "level":"Incomplete information", "rain":18},
})
STAGES = ["Read the conditions", "A report arrives", "Check the evidence", "Access changes", "Recheck the plan", "Review the outcome"]
STORIES = {
 "rain": [
  ("A forecast is a reason to check.", "4 mm is forecast over one hour in this fictional scenario. There is no reported assistance request.", "Read the weather context; keep resources available."),
  ("A message is not yet evidence.", "An unverified message claims homes are affected. No location-specific corroboration or supply request is attached.", "Open the report and check what is missing."),
  ("The claim was not corroborated.", "A scripted on-site check rejects the message: the observer found a passable street and no assistance request at the training site.", "Do not generalise this one check to all of Chromepet."),
  ("The forecast eases.", "The training forecast falls to 1 mm over one hour. The earlier rejection stands independently of the weather.", "Keep monitoring; lower rainfall is not proof of universal safety."),
  ("Preparedness is enough here.", "No corroborated demand has entered this scenario. A preparedness draft remains useful; response approval remains blocked.", "Save a preparedness note if helpful. Do not invent a delivery."),
  ("You avoided an unsupported response.", "This fictional exercise ends with no corroborated assistance request at the checked site.", "Explain which evidence was missing and why rain alone was insufficient."),
 ],
 "response": [
  ("Start with what is known.", "The fictional forecast indicates sustained rain. Street conditions and assistance needs are still unknown.", "Choose your resources. Do not infer a need from the rainfall."),
  ("People report a specific need.", "Training field reports have arrived. They are unreviewed and cannot yet support an approved response.", "Open a request to inspect people, quantities and uncertainties."),
  ("A check makes the request usable.", "A scripted coordinator call corroborates the reported needs at the named training sites. This is simulated evidence, not a real call.", "Check the evidence, save a draft and practise coordinator approval."),
  ("Your old plan needs a fresh look.", "A new field update reports changed access at the primary site. It is pending review; existing plans are flagged for rechecking.", "Inspect the update. Approval of an old draft is now blocked."),
  ("Needs change as help arrives.", "A scripted check accepts an alternative receiving point and partial supply fulfilment at the primary site. Remaining quantities are updated.", "Compare the remaining need and create a fresh draft."),
  ("Close the loop, honestly.", "The primary request is resolved by a scripted field update. In the three-area exercise, other requests remain open.", "Review what your team planned and what the scenario actually reports."),
 ],
}
PROFILES = {
 "Velachery": {"landmark": "SIMULATION · Lakeside community point", "description": "SIMULATION: waterlogging has interrupted access to a community point. Residents sheltering there request drinking water.", "needs": "Drinking water for the community point", "resources": [{"kind": "water", "quantity": 120}], "groups": ["Residents sheltering at the training community point"], "specialist": False},
 "Tambaram": {"landmark": "SIMULATION · South neighbourhood point", "description": "SIMULATION: a volunteer reports residents unable to leave flooded homes, including older residents. Trained rescue assistance is requested; supply volunteers must not enter floodwater.", "needs": "Trained rescue coordination and food at a receiving point", "resources": [{"kind": "food", "quantity": 40}], "groups": ["Residents reportedly unable to leave homes", "Older residents mentioned in the report"], "specialist": True},
 "Chromepet": {"landmark": "SIMULATION · Community support point", "description": "SIMULATION: a staffed support point requests sealed medical supply kits. No injuries or diagnosis are established by this request.", "needs": "Sealed medical supply kits for the staffed support point", "resources": [{"kind": "medical", "quantity": 10}], "groups": ["People using the training support point"], "specialist": False},
}

class Start(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: Literal["rain", "waterlogging", "urgent", "multi", "conflict", "incomplete"]

class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)
    action: Literal["next", "reset"] = "next"


def directory():
    return Path(os.getenv("CRISISLENS_SIM_DB_DIR", str(Path(__file__).resolve().parents[1] / "runtime" / "simulations")))


def write_meta(work, meta):
    with work.connect() as db:
        db.execute("INSERT OR REPLACE INTO state VALUES ('simulation', ?)", (json.dumps(meta),))


def get_session(identifier):
    path = directory() / (str(identifier) + ".sqlite3")
    if not path.is_file():
        raise HTTPException(404, "Simulation not found. Start a new scenario.")
    work = Workflow(path)
    with work.connect() as db:
        row = db.execute("SELECT data FROM state WHERE key='simulation'").fetchone()
    if not row:
        raise HTTPException(404, "Simulation not found.")
    meta = json.loads(row[0])
    if utcnow() - timestamp(meta["created_at"]) > timedelta(hours=4):
        raise HTTPException(410, "This training session expired. Start a new scenario to use fresh observations.")
    return work, meta


def primary(meta):
    return "Velachery" if meta["scenario"] == "multi" else SCENARIOS[meta["scenario"]]["area"]


def find_report(work, identifier):
    for area in AREAS:
        for report in work.snapshot(area)["reports"]:
            if report["id"] == identifier:
                return report
    raise KeyError(identifier)


def review(work, report, status="reviewed", update_id=None, note=None):
    return work.review(report["id"], UpdateReview(revision=report["revision"], status=status, update_id=update_id,
        reviewer="SIMULATION coordinator", method="phone", note=note or "SIMULATION: scripted contact check confirms this training request, quantities and receiving arrangement. No actual call occurred."))


def apply_stage(work, meta):
    stage, rain = meta["stage"], meta["scenario"] == "rain"
    if stage == 1:
        locations = AREAS if meta["scenario"] == "multi" else [primary(meta)]
        for area in locations:
            p = PROFILES[area]
            report = work.submit(ReportInput(location=area, landmark=p["landmark"], observed_at=utcnow(),
                description="SIMULATION: an unverified message claims homes are affected. No specific people, quantities or corroboration are supplied." if rain else p["description"],
                needs="" if rain else p["needs"], resources=[] if rain or meta["scenario"] == "incomplete" else p["resources"],
                access_status="passable" if meta["scenario"] == "conflict" else "unknown"))
            meta["report_ids"][area] = report["id"]
        if meta["scenario"] == "conflict":
            alternative = work.submit(ReportInput(location="Velachery", landmark=PROFILES["Velachery"]["landmark"], observed_at=utcnow(),
                description="SIMULATION: a second observer reports the same community point has blocked access and requests 200 litres of water. This disagrees with the first record.",
                needs="Water at the same community point", access_status="blocked", resources=[{"kind":"water","quantity":200}]))
            meta["alternative_id"] = alternative["id"]
    elif stage == 2:
        for identifier in meta["report_ids"].values():
            review(work, find_report(work, identifier), "rejected" if rain else "reviewed",
                   note="SIMULATION: scripted on-site check found a passable street and no assistance request at this one training site. Earlier message rejected." if rain else None)
        if meta.get("alternative_id"):
            review(work, find_report(work, meta["alternative_id"]))
    elif stage >= 3 and not rain:
        report = find_report(work, meta["report_ids"][primary(meta)])
        if stage == 3:
            update = work.add_update(report["id"], ReportUpdate(outcome="still_needed", observed_at=utcnow(),
                note="SIMULATION: the originally discussed approach is now reported blocked. Do not use the previous receiving arrangement until it is checked.", needs=report["needs"], resources=report["resources"]))
            meta["pending_id"] = update["id"]
        elif stage == 4:
            if meta.get("alternative_id"):
                review(work, find_report(work, meta["alternative_id"]), status="rejected", note="SIMULATION: scripted follow-up identifies the second report as incorrect for this site. Retain it as rejected; do not delete the disagreement history.")
            # Preserve the blocked-access observation, then record a separate later check.
            review(work, report, update_id=meta["pending_id"], note="SIMULATION: scripted check confirms original access is blocked. Previous access assumption is no longer usable.")
            report = find_report(work, report["id"])
            remaining = [{**r, "quantity": r["quantity"] - (40 if r["kind"] == "water" else 20)} for r in report["resources"]]
            update = work.add_update(report["id"], ReportUpdate(outcome="partly_fulfilled", observed_at=utcnow(),
                note="SIMULATION: a scripted local check agrees a different receiving point. Another simulated team supplied part of the request. Remaining quantities are recorded below.", needs=report["needs"], resources=remaining))
            review(work, report, update_id=update["id"], note="SIMULATION: scripted contact confirms the revised receiving arrangement and remaining quantities. No actual delivery occurred.")
        elif stage == 5:
            update = work.add_update(report["id"], ReportUpdate(outcome="resolved", observed_at=utcnow(),
                note="SIMULATION: a scripted field update reports the primary request resolved by training responders. This is not attributed to your plan or a real delivery.", needs="", resources=[]))
            review(work, report, status="resolved", update_id=update["id"], note="SIMULATION: scripted outcome corroboration closes this training request only. Other sites must be checked separately.")


def state(work, meta):
    scenario = SCENARIOS[meta["scenario"]]
    story = STORIES["rain" if meta["scenario"] == "rain" else "response"][meta["stage"]]
    if meta["scenario"] == "conflict" and meta["stage"] in (1, 2, 3):
        story = ("These reports disagree.", "Two training records describe the same site with different quantities and opposite access observations. Neither should silently override the other.", "Compare both records. Quantity proposals and approval are held until reconciliation.")
    if meta["scenario"] == "incomplete" and meta["stage"] in (1, 2, 3, 4):
        story = ("The need is reported. The quantity is unknown.", "The fictional site requests water but no reliable quantity is recorded. A reviewed report can still be incomplete.", "Check the missing information. Do not invent litres or people counts.")
    reports = []
    for area in AREAS:
        for report in work.snapshot(area)["reports"]:
            reports.append({**report, "groups": [] if meta["scenario"] == "rain" else PROFILES[area]["groups"],
                            "specialist": meta["scenario"] != "rain" and PROFILES[area]["specialist"]})
    return {**meta, "simulation": True, "scenario_info": scenario, "stages": STAGES,
            "event": {"title": story[0], "detail": story[1], "next_action": story[2]},
            "weather": {"rain_mm": 1 if meta["scenario"] == "rain" and meta["stage"] >= 3 else scenario["rain"],
                        "duration_hours": 1, "label": "Fictional forecast · not current weather"},
            "reports": reports, "plans": work.plans(), "primary_area": primary(meta)}


def initial(scenario, identifier, revision=0):
    return {"id": str(identifier), "scenario": scenario, "stage": 0, "revision": revision,
            "created_at": utcnow().isoformat(), "report_ids": {}, "pending_id": None}


@router.get("")
def catalog():
    return list(SCENARIOS.values())


@router.post("", status_code=201)
def start(payload: Start):
    with lock:
        directory().mkdir(parents=True, exist_ok=True)
        # Sessions expire after four hours; bound disk growth during repeated demonstrations.
        for path in directory().glob("*.sqlite3"):
            try:
                uuid.UUID(path.stem)
            except ValueError:
                continue
            if utcnow().timestamp() - path.stat().st_mtime > 86400:
                path.unlink(missing_ok=True)
        identifier = uuid.uuid4()
        work = Workflow(directory() / (str(identifier) + ".sqlite3"))
        meta = initial(payload.scenario, identifier)
        write_meta(work, meta)
        return state(work, meta)


@router.get("/{identifier}")
def read(identifier: uuid.UUID):
    with lock:
        return state(*get_session(identifier))


@router.post("/{identifier}/events")
def advance(identifier: uuid.UUID, event: Event):
    with lock:
        work, meta = get_session(identifier)
        if meta["revision"] != event.revision:
            raise HTTPException(409, "Scenario changed in another window. Reload it before continuing.")
        if event.action == "reset":
            with work.connect() as db:
                for table in ("reports", "reviews", "report_updates", "plans", "briefings"):
                    db.execute(f"DELETE FROM {table}")
            meta = initial(meta["scenario"], identifier, meta["revision"] + 1)
        else:
            if meta["stage"] == 5:
                raise HTTPException(409, "This scenario is complete. Reset it to start again.")
            meta["stage"] += 1
            apply_stage(work, meta)
            meta["revision"] += 1
        write_meta(work, meta)
        return state(work, meta)


@router.post("/{identifier}/plans", status_code=201)
def create_plan(identifier: uuid.UUID, payload: PlanInput):
    with lock:
        work, meta = get_session(identifier)
        if payload.briefing_id:
            raise HTTPException(422, "Live briefings cannot be attached to a simulation.")
        try:
            work.create_plan(payload)
        except KeyError as exc:
            raise HTTPException(404, "Report not found in this simulation.") from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return state(work, meta)


@router.post("/{identifier}/plans/{plan_id}")
def change_plan(identifier: uuid.UUID, plan_id: uuid.UUID, payload: PlanChange):
    with lock:
        work, meta = get_session(identifier)
        try:
            work.change_plan(plan_id.hex, payload)
        except KeyError as exc:
            raise HTTPException(404, "Plan not found in this simulation.") from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return state(work, meta)
