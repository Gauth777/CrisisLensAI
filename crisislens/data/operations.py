"""Deterministic official-warning intake and auditable local field reports.

No LLM participates in ingestion, expiry, matching, or report review.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import uuid
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator
from .context import read_public, text_only
from ..schemas import PilotLocation

RSS = "https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml"
NS = {"c": "urn:oasis:names:tc:emergency:cap:1.2"}
DISTRICTS = {"Velachery": "Chennai", "Tambaram": "Chengalpattu", "Chromepet": "Chengalpattu"}
COVERAGE = "SACHET entries from IMD Chennai, Tamil Nadu issuers and CWC; district matches only. Not complete local incident coverage."


def read_sachet(url):
    return read_public(url, timeout=15)


def utcnow():
    return datetime.now(timezone.utc)


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else None
    except (ValueError, TypeError, AttributeError):
        return None


def xml(raw):
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("Unsupported XML declarations")
    return ET.fromstring(raw)


def feed_urls(raw):
    root = xml(raw)
    if root.tag != "rss" or root.find("channel") is None:
        raise ValueError("Expected SACHET RSS")
    urls = []
    for item in root.findall("./channel/item"):
        author = item.findtext("author", "")
        # The generic NDMA email appears on every item; match the issuer only.
        if not re.search(r"\b(IMD Chennai|Tamil\s*Nadu|TNSDMA|CWC)\b", author, re.I):
            continue
        url = item.findtext("link", "").strip()
        parsed = urlparse(url)
        if (parsed.scheme == "https" and parsed.netloc == "sachet.ndma.gov.in"
                and parsed.path == "/cap_public_website/FetchXMLFile"
                and re.fullmatch(r"identifier=\d{1,30}", parsed.query)):
            urls.append(url)
    return list(dict.fromkeys(urls))


def parse_cap(raw, url, received):
    root = xml(raw)
    if root.tag != "{" + NS["c"] + "}alert":
        raise ValueError("Expected CAP alert")
    def get(node, name):
        return text_only(node.findtext("c:" + name, "", NS))
    identifier, sender = get(root, "identifier"), get(root, "sender")
    sent = timestamp(get(root, "sent"))
    if not identifier or not sender or not sent or sent > received + timedelta(minutes=5):
        raise ValueError("Invalid CAP identity or timestamp")
    references = []
    for reference in get(root, "references").split():
        parts = reference.split(",")
        if len(parts) == 3:
            references.append([parts[0], parts[1]])
    infos = []
    for info in root.findall("c:info", NS):
        if get(info, "language") and not get(info, "language").lower().startswith("en"):
            continue
        areas = [get(area, "areaDesc") for area in info.findall("c:area", NS)]
        # Deliberately district-scoped, including when CAP provides a polygon:
        # never present this as a precise street/geofence match.
        joined = " ".join(areas)
        locations = [place for place, district in DISTRICTS.items()
                     if re.search(r"\b" + district + r"\b", joined, re.I)]
        expires = timestamp(get(info, "expires"))
        effective = timestamp(get(info, "effective")) or sent
        infos.append({"event": get(info, "event"), "headline": get(info, "headline")[:3000],
                      "instruction": get(info, "instruction")[:3000], "area": joined[:3000],
                      "locations": locations, "severity": get(info, "severity"),
                      "certainty": get(info, "certainty"), "urgency": get(info, "urgency"),
                      "effective_at": effective.isoformat(),
                      "expires_at": expires.isoformat() if expires else None})
    return {"identifier": identifier, "sender": sender, "sent_at": sent.isoformat(),
            "received_at": received.isoformat(), "status": get(root, "status"),
            "scope": get(root, "scope"), "message_type": get(root, "msgType"),
            "references": references, "infos": infos, "url": url}


class FieldReport(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    location: PilotLocation
    landmark: str = Field(min_length=3, max_length=160)
    observed_at: datetime
    description: str = Field(min_length=15, max_length=2000)
    needs: str = Field(default="", max_length=500)

    @field_validator("observed_at")
    @classmethod
    def valid_observed(cls, value):
        if value.tzinfo is None or not utcnow() - timedelta(days=7) <= value <= utcnow() + timedelta(minutes=5):
            raise ValueError("Use a timezone-aware observation time within the last seven days")
        return value


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    revision: int = Field(ge=0)
    status: Literal["reviewed", "rejected", "resolved"]
    reviewer: str = Field(min_length=2, max_length=80)
    method: Literal["on_site", "phone", "official_reference"]
    note: str = Field(min_length=20, max_length=1000)


class Operations:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        self.lock = threading.RLock()
        self.poll_lock = threading.Lock()
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS alerts(url TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY, data TEXT NOT NULL, revision INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY, report_id TEXT NOT NULL, data TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def poll(self, fetch=read_sachet):
        if not self.poll_lock.acquire(blocking=False):
            return
        try:
            now = utcnow()
            with self.lock, self.connect() as db:
                row = db.execute("SELECT data FROM state WHERE key='feed'").fetchone()
                health = json.loads(row[0]) if row else {}
                known = {row[0] for row in db.execute("SELECT url FROM alerts")}
            health.update(last_attempt=now.isoformat(), error=None)
            try:
                urls = feed_urls(fetch(RSS))
                if len(urls) > 200:
                    raise ValueError("Official feed exceeds configured intake bound")
                pending = [url for url in urls if url not in known]
                def retrieve(url):
                    try:
                        return parse_cap(fetch(url), url, utcnow())
                    except Exception:
                        return None
                failed = 0
                with ThreadPoolExecutor(max_workers=4) as pool:
                    futures = [pool.submit(retrieve, url) for url in pending]
                    for future in as_completed(futures):
                        record = future.result()
                        if record:
                            # Publish each warning immediately; don't wait for the slowest CAP document.
                            with self.lock, self.connect() as db:
                                db.execute("INSERT OR IGNORE INTO alerts VALUES (?, ?)", (record["url"], json.dumps(record)))
                        else:
                            failed += 1
                health.update(entries=len(urls), failed_entries=failed)
                if failed:
                    health["error"] = f"{failed} official alert documents could not be checked. Coverage is incomplete."
                else:
                    health["last_success"] = utcnow().isoformat()
            except Exception:
                health["error"] = "Official feed unavailable. Previously received warnings may have changed."
            with self.lock, self.connect() as db:
                db.execute("INSERT OR REPLACE INTO state VALUES ('feed', ?)", (json.dumps(health),))
        finally:
            self.poll_lock.release()

    def submit(self, report):
        record = {**report.model_dump(mode="json"), "id": uuid.uuid4().hex,
                  "submitted_at": utcnow().isoformat(), "status": "unreviewed", "revision": 0}
        with self.lock, self.connect() as db:
            db.execute("INSERT INTO reports VALUES (?, ?, 0)", (record["id"], json.dumps(record)))
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
            audit = {**review.model_dump(), "reviewed_at": utcnow().isoformat()}
            record.update(status=review.status, revision=review.revision + 1, last_review=audit)
            db.execute("UPDATE reports SET data=?, revision=? WHERE id=?", (json.dumps(record), record["revision"], identifier))
            db.execute("INSERT INTO reviews(report_id, data) VALUES (?, ?)", (identifier, json.dumps(audit)))
        return record

    def snapshot(self, location, now=None):
        now = now or utcnow()
        with self.lock, self.connect() as db:
            row = db.execute("SELECT data FROM state WHERE key='feed'").fetchone()
            health = json.loads(row[0]) if row else {}
            records = [json.loads(row[0]) for row in db.execute("SELECT data FROM alerts")]
            reports = [json.loads(row[0]) for row in db.execute("SELECT data FROM reports")]
            reviews = db.execute("SELECT report_id, data FROM reviews ORDER BY id").fetchall()
        success = timestamp(health.get("last_success"))
        health.update(stale=bool(health.get("error")) or not success or now - success > timedelta(minutes=5),
                      coverage=COVERAGE, polling_seconds=120)
        official = [r for r in records if r["status"] == "Actual" and r["scope"] == "Public"]
        superseded = {tuple(ref) for r in official if r["message_type"] in ("Update", "Cancel") for ref in r["references"]}
        alerts = []
        for record in official:
            if record["message_type"] not in ("Alert", "Update") or (record["sender"], record["identifier"]) in superseded:
                continue
            for index, info in enumerate(record["infos"]):
                if location not in info["locations"]:
                    continue
                expiry = timestamp(info["expires_at"])
                if expiry and expiry <= now:
                    continue
                state = "unknown_expiry" if not expiry else "scheduled" if timestamp(info["effective_at"]) > now else "active"
                alerts.append({**{k: v for k, v in record.items() if k not in ("infos", "references")}, **info,
                               "id": record["identifier"] + ":" + str(index), "state": state, "match_scope": "district"})
        local = []
        for report in reports:
            if report["location"] == location and now - timestamp(report["submitted_at"]) <= timedelta(days=7):
                report["stale"] = now - timestamp(report["observed_at"]) > timedelta(hours=6)
                report["review_history"] = [json.loads(data) for rid, data in reviews if rid == report["id"]]
                local.append(report)
        return {"location": location, "retrieved_at": now.isoformat(), "feed": health,
                "alerts": sorted(alerts, key=lambda a: timestamp(a["sent_at"]), reverse=True)[:20],
                "reports": sorted(local, key=lambda r: r["submitted_at"], reverse=True)[:50],
                "review_enabled": bool(os.getenv("CRISISLENS_REVIEW_TOKEN", "").strip())}


def operational_sources(snapshot):
    """Only current official warnings and recent human-reviewed reports enter AI evidence."""
    sources = []
    if not snapshot["feed"]["stale"]:
        for alert in snapshot["alerts"]:
            if alert["state"] != "active":
                continue
            sources.append({"id": "A" + str(len(sources) + 1), "kind": "official_alert",
                            "title": alert["event"], "publisher": alert["sender"], "url": alert["url"],
                            "published_at": alert["sent_at"], "retrieved_at": alert["received_at"],
                            "excerpt": alert["headline"] + " Instruction: " + alert["instruction"],
                            "scope": "district", "content_scope": "official_warning",
                            "expires_at": alert["expires_at"], "certainty": alert["certainty"],
                            "limitation": "District warning, not confirmation of street flooding, affected people or supply needs."})
    for report in snapshot["reports"]:
        if report["status"] == "reviewed" and not report["stale"]:
            sources.append({"id": "F" + report["id"], "kind": "field_report",
                            "title": report["landmark"], "publisher": "Coordinator-reviewed field report",
                            "url": None, "published_at": report["observed_at"], "retrieved_at": report["submitted_at"],
                            "excerpt": report["description"] + " Reported needs: " + report["needs"],
                            "scope": "locality", "content_scope": "reviewed_report", "review": report["last_review"],
                            "limitation": "Human-reviewed report, not independently certified ground truth. Check observation time and review method."})
    return sources
