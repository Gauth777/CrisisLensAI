"""Persistent NGO drafts and reviewed report updates. No automatic dispatch."""
import json
import uuid
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from .data.operations import Operations, FieldReport, Review, utcnow, timestamp
from .schemas import PilotLocation
from .reliability import annotate_reports, resource_check


class Resource(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    kind: Literal["food", "water", "medical", "shelter", "other"]
    quantity: float = Field(gt=0, le=1000000)


def unique_resources(value):
    if len({r.kind for r in value}) != len(value):
        raise ValueError("Enter one quantity per resource kind.")
    return value


class ReportInput(FieldReport):
    access_status: Literal["unknown", "passable", "blocked"] = "unknown"
    demand_status: Literal["unknown", "needed", "not_needed"] = "unknown"
    resources: list[Resource] = Field(default_factory=list, max_length=5)
    _unique_resources = field_validator("resources")(unique_resources)


class ReportUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    access_status: Literal["unknown", "passable", "blocked"] = "unknown"
    demand_status: Literal["unknown", "needed", "not_needed"] = "unknown"
    outcome: Literal["still_needed", "partly_fulfilled", "resolved"]
    observed_at: datetime
    note: str = Field(min_length=15, max_length=2000)
    needs: str = Field(max_length=500)
    resources: list[Resource] = Field(default_factory=list, max_length=5)
    _unique_resources = field_validator("resources")(unique_resources)

    @field_validator("observed_at")
    @classmethod
    def check_time(cls, value):
        return FieldReport.valid_observed(value)


class UpdateReview(Review):
    update_id: str | None = None


class PlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    location: PilotLocation
    report_id: str | None = None
    briefing_id: str | None = None
    volunteers: int = Field(ge=0, le=10000)
    resources: list[Resource] = Field(default_factory=list, max_length=5)
    _unique_resources = field_validator("resources")(unique_resources)
    notes: str = Field(default="", max_length=3000)


class PlanChange(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    revision: int = Field(ge=0)
    action: Literal["save", "approve", "close"]
    contact_checked: bool = False
    access_checked: bool = False
    receiving_time_checked: bool = False
    actor: str = Field(default="", max_length=80)
    note: str = Field(default="", max_length=2000)


class Workflow(Operations):
    def __init__(self, path):
        super().__init__(path)
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS report_updates(id TEXT PRIMARY KEY, report_id TEXT NOT NULL, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY, data TEXT NOT NULL, revision INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS briefings(id TEXT PRIMARY KEY, data TEXT NOT NULL);
            ''')

    def add_update(self, identifier, update):
        with self.lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT data FROM reports WHERE id=?", (identifier,)).fetchone()
            if not row:
                raise KeyError(identifier)
            report = json.loads(row[0])
            if update.observed_at < timestamp(report["observed_at"]):
                raise ValueError("An update cannot predate the current observation.")
            record = {**update.model_dump(mode="json"), "id": uuid.uuid4().hex,
                      "submitted_at": utcnow().isoformat(), "status": "pending"}
            db.execute("INSERT INTO report_updates VALUES (?, ?, ?)", (record["id"], identifier, json.dumps(record)))
        return record

    def review(self, identifier, review):
        with self.lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT data, revision FROM reports WHERE id=?", (identifier,)).fetchone()
            if not row:
                raise KeyError(identifier)
            if row[1] != review.revision:
                raise ValueError("Report changed. Reload before reviewing.")
            record = json.loads(row[0])
            update_id = getattr(review, "update_id", None)
            if update_id:
                row = db.execute("SELECT data FROM report_updates WHERE id=? AND report_id=?", (update_id, identifier)).fetchone()
                if not row:
                    raise KeyError(update_id)
                update = json.loads(row[0])
                if update["status"] != "pending":
                    raise ValueError("This update has already been reviewed.")
                if review.status != "rejected":
                    if timestamp(update["observed_at"]) < timestamp(record["observed_at"]):
                        raise ValueError("This update predates the current observation. Reject it or check a newer report.")
                    if (update["outcome"] == "resolved") != (review.status == "resolved"):
                        raise ValueError("A resolved update requires a resolved review outcome.")
                    record.update(description=update["note"], observed_at=update["observed_at"],
                                  needs=update["needs"], resources=update["resources"], status=review.status,
                                  access_status=update.get("access_status", "unknown"), demand_status=update.get("demand_status", "unknown"))
                update.update(status="rejected" if review.status == "rejected" else "accepted", reviewed_at=utcnow().isoformat())
                db.execute("UPDATE report_updates SET data=? WHERE id=?", (json.dumps(update), update_id))
            else:
                record["status"] = review.status
            audit = {**review.model_dump(), "reviewed_at": utcnow().isoformat()}
            record.update(revision=review.revision + 1)
            if not update_id or review.status != "rejected":
                record["last_review"] = audit
            db.execute("UPDATE reports SET data=?, revision=? WHERE id=?", (json.dumps(record), record["revision"], identifier))
            db.execute("INSERT INTO reviews(report_id, data) VALUES (?, ?)", (identifier, json.dumps(audit)))
        return record

    def snapshot(self, location, now=None):
        result = super().snapshot(location, now)
        with self.lock, self.connect() as db:
            updates = [(rid, json.loads(data)) for rid, data in db.execute("SELECT report_id, data FROM report_updates")]
        for report in result["reports"]:
            report["updates"] = sorted([u for rid, u in updates if rid == report["id"]], key=lambda u: u["submitted_at"], reverse=True)
            report["pending_updates"] = sum(u["status"] == "pending" for u in report["updates"])
        annotate_reports(result["reports"])
        return result

    def save_briefing(self, data):
        identifier = uuid.uuid4().hex
        with self.lock, self.connect() as db:
            db.execute("INSERT INTO briefings VALUES (?, ?)", (identifier, json.dumps(data)))
        return identifier

    def create_plan(self, payload):
        with self.lock, self.connect() as db:
            source = None
            if payload.report_id:
                row = db.execute("SELECT data FROM reports WHERE id=?", (payload.report_id,)).fetchone()
                if not row:
                    raise KeyError(payload.report_id)
                source = json.loads(row[0])
                if source["location"] != payload.location:
                    raise ValueError("Report and plan locations differ.")
            briefing = None
            if payload.briefing_id:
                row = db.execute("SELECT data FROM briefings WHERE id=?", (payload.briefing_id,)).fetchone()
                if not row:
                    raise KeyError(payload.briefing_id)
                briefing = json.loads(row[0])
                question = briefing["question"]
                if source and briefing.get("report_revision") != source["revision"]:
                    raise ValueError("The report changed after generation. Reopen the report and generate fresh steps.")
                if (question["location"] != payload.location or question.get("report_id") != payload.report_id or
                        question.get("resources", []) != [r.model_dump() for r in payload.resources] or
                        question.get("volunteers", 0) != payload.volunteers):
                    raise ValueError("The recommendation belongs to different resources or a different request. Generate it again.")
            now = utcnow().isoformat()
            record = {**payload.model_dump(), "briefing": briefing, "id": uuid.uuid4().hex, "revision": 0, "status": "draft",
                      "created_at": now, "updated_at": now, "report_snapshot": source,
                      "contact_checked": False, "access_checked": False, "receiving_time_checked": False,
                      "history": [{"at": now, "action": "created", "note": "Draft saved; nothing dispatched."}]}
            db.execute("INSERT INTO plans VALUES (?, ?, 0)", (record["id"], json.dumps(record)))
        return record

    def plans(self):
        with self.lock, self.connect() as db:
            records = [json.loads(row[0]) for row in db.execute("SELECT data FROM plans")]
            reports = {rid: json.loads(data) for rid, data in db.execute("SELECT id, data FROM reports")}
            pending = {rid for rid, data in db.execute("SELECT report_id, data FROM report_updates") if json.loads(data)["status"] == "pending"}
        annotated = {r["id"]: r for a in ("Velachery", "Tambaram", "Chromepet") for r in self.snapshot(a)["reports"]}
        for plan in records:
            check = annotated.get(plan["report_id"])
            plan["resource_check"] = resource_check(check, plan["resources"])
            current = reports.get(plan["report_id"])
            plan["source_changed"] = bool(plan["report_id"]) and (not current or current["revision"] != plan["report_snapshot"]["revision"] or current["status"] != "reviewed" or utcnow() - timestamp(current["observed_at"]) > timedelta(hours=6) or plan["report_id"] in pending or bool((check or {}).get("conflicts")) or (check or {}).get("access_status") == "blocked" or (check or {}).get("demand_status") == "not_needed")
        return sorted(records, key=lambda p: p["updated_at"], reverse=True)

    def change_plan(self, identifier, change):
        with self.lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT data, revision FROM plans WHERE id=?", (identifier,)).fetchone()
            if not row:
                raise KeyError(identifier)
            if row[1] != change.revision:
                raise ValueError("Plan changed. Reload before saving.")
            record = json.loads(row[0])
            if record["status"] == "closed":
                raise ValueError("This plan is closed.")
            if change.action == "approve":
                if record["status"] != "draft":
                    raise ValueError("Only a draft can be approved.")
                if not change.actor.strip() or len(change.note.strip()) < 15:
                    raise ValueError("Record the coordinator and the checks performed.")
                if not all((change.contact_checked, change.access_checked, change.receiving_time_checked)):
                    raise ValueError("Check contact, access and receiving time before approval.")
                if not record["resources"] and record["volunteers"] == 0:
                    raise ValueError("Record available supplies or volunteers in a new draft before approval.")
                if not record["report_id"]:
                    raise ValueError("Preparedness drafts have no confirmed request; they cannot be approved for a response.")
                current_row = db.execute("SELECT data FROM reports WHERE id=?", (record["report_id"],)).fetchone()
                current = json.loads(current_row[0]) if current_row else None
                pending = [json.loads(row[0]) for row in db.execute("SELECT data FROM report_updates WHERE report_id=?", (record["report_id"],))]
                if (not current or current["status"] != "reviewed" or current["revision"] != record["report_snapshot"]["revision"] or
                        utcnow() - timestamp(current["observed_at"]) > timedelta(hours=6) or any(u["status"] == "pending" for u in pending)):
                    raise ValueError("The request is outdated, changed or awaiting review. Check it and create a fresh draft.")
                checked = next((r for r in self.snapshot(current["location"])["reports"] if r["id"] == current["id"]), {})
                if checked.get("conflicts") or current.get("access_status") == "blocked" or current.get("demand_status") == "not_needed":
                    raise ValueError("Conflicting reports, blocked access or no current demand: resolve the evidence before approval.")
                if not current.get("needs", "").strip() and not current.get("resources"):
                    raise ValueError("No assistance request is recorded. Keep this as a preparedness draft until needs are established.")
                record["status"] = "approved"
            elif change.action == "close":
                if len(change.note.strip()) < 15:
                    raise ValueError("Record why this plan is being closed.")
                record["status"] = "closed"
            elif record["status"] != "draft":
                raise ValueError("Approved plans are immutable; close this plan and create a new draft.")
            now = utcnow().isoformat()
            record.update(contact_checked=change.contact_checked, access_checked=change.access_checked,
                          receiving_time_checked=change.receiving_time_checked, revision=change.revision+1, updated_at=now)
            record["history"].append({"at": now, "action": change.action, "actor": change.actor, "note": change.note})
            db.execute("UPDATE plans SET data=?, revision=? WHERE id=?", (json.dumps(record), record["revision"], identifier))
        return record
