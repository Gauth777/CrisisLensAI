"""Bounded, deterministic retrieval. No model-selected URLs or tools."""
from __future__ import annotations

import hashlib
import json
import math
import re
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

from .environment import OpenMeteoWeatherClient, PILOT_COORDINATES
from ..schemas import PilotLocation

IST = ZoneInfo("Asia/Kolkata")
FEEDS = (
    ("The Indian Express", "https://indianexpress.com/section/cities/chennai/feed/", "indianexpress.com"),
    ("The Hindu", "https://www.thehindu.com/news/cities/chennai/feeder/default.rss", "thehindu.com"),
)
ALIASES = {"Velachery": ("velachery", "velacheri"), "Tambaram": ("tambaram",), "Chromepet": ("chromepet", "chrompet")}
HAZARDS = re.compile(r"\b(rain\w*|flood\w*|cyclon\w*|waterlog\w*|storm\w*|rescue\w*|relief|evacuat\w*|shelter\w*|fire|outage\w*)\b", re.I)


class SameHostRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlparse(newurl).scheme != "https" or urlparse(newurl).hostname != urlparse(req.full_url).hostname:
            raise ValueError("Cross-host retrieval redirect rejected")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def read_public(url: str, limit: int = 1_000_000, timeout: int = 8) -> bytes:
    request = Request(url, headers={"User-Agent": "CrisisLensAI academic prototype/0.5", "Accept": "application/xml, application/json, text/xml"})
    with build_opener(SameHostRedirect()).open(request, timeout=timeout) as response:
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Source response exceeded retrieval limit")
    return raw


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def text_only(value: str) -> str:
    parser = PlainText()
    parser.feed(value)
    return " ".join(" ".join(parser.parts).split())


def parse_feed(raw: bytes, publisher: str, domain: str, location: PilotLocation, now: datetime) -> list[dict]:
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("Unsupported XML declarations")
    root = ET.fromstring(raw)
    records = []
    seen = set()
    for item in root.findall(".//item")[:80]:
        title = text_only(item.findtext("title", ""))[:240]
        url = item.findtext("link", "").strip()
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in {domain, "www." + domain} or url in seen:
            continue
        try:
            published = parsedate_to_datetime(item.findtext("pubDate", ""))
            if published.tzinfo is None:
                continue
            if not now - timedelta(days=7) <= published <= now + timedelta(minutes=5):
                continue
        except (ValueError, TypeError, OverflowError):
            continue
        # Publisher RSS excerpt only: bounded snippet, never a scraped full article.
        excerpt = " ".join(text_only(item.findtext("description", "")).split()[:24])
        combined = title + " " + excerpt
        if not HAZARDS.search(combined):
            continue
        local = any(re.search(r"\b" + alias + r"\b", combined, re.I) for alias in ALIASES[location])
        if not local and not re.search(r"\b(chennai|tamil nadu)\b", combined, re.I):
            continue
        seen.add(url)
        records.append({"id": "N" + hashlib.sha256(url.encode()).hexdigest()[:12], "kind": "news",
                        "title": title, "publisher": publisher, "url": url,
                        "published_at": published.isoformat(), "retrieved_at": now.isoformat(),
                        "excerpt": excerpt, "scope": "locality" if local else "city_context",
                        "content_scope": "feed_excerpt" if excerpt else "headline_only",
                        "limitation": "Publisher feed excerpt, not independently verified ground conditions. City-wide coverage does not confirm a locality incident."})
    records.sort(key=lambda r: (r["scope"] == "locality", r["published_at"]), reverse=True)
    return records[:3]


def _number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return float(value)
    return None


def parse_outlook(payload: dict, now: datetime) -> dict:
    environment = OpenMeteoWeatherClient._parse(payload)
    current_time = payload.get("current", {}).get("time")
    observed = datetime.fromisoformat(current_time) if current_time else None
    if observed and observed.tzinfo is None:
        observed = observed.replace(tzinfo=IST)
    if observed is None or abs((now - observed).total_seconds()) > 7200:
        raise ValueError("Weather is missing or stale")
    environment.observed_at = observed.isoformat()
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    amounts = hourly.get("precipitation", [])
    probabilities = hourly.get("precipitation_probability", [])
    rows = []
    for i, value in enumerate(times):
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST)
        # Hourly accumulation is for the hour ending at this timestamp.
        if not now < dt <= now + timedelta(hours=24):
            continue
        amount = _number(amounts[i]) if i < len(amounts) else None
        probability = _number(probabilities[i]) if i < len(probabilities) else None
        if probability is not None and not 0 <= probability <= 100:
            probability = None
        if amount is not None and amount < 0:
            amount = None
        rows.append({"time": dt.isoformat(), "precipitation_mm": amount, "probability_percent": probability})
    rows.sort(key=lambda row: row["time"])
    next_rain = next((row for row in rows if row["precipitation_mm"] is not None and row["precipitation_mm"] >= 0.1), None)
    complete = len(rows) == 24 and all(row["precipitation_mm"] is not None for row in rows)
    return {"environment": environment.model_dump(mode="json"), "hours": rows,
            "next_rain": next_rain, "forecast_complete": complete,
            "rain_threshold_mm": 0.1, "timezone": "Asia/Kolkata",
            "limitation": "Modelled weather and forecast, not official station observations or proof of flooding. Rain window uses hourly accumulation >= 0.1 mm."}


def fetch_outlook(location: PilotLocation, now: datetime) -> tuple[dict, dict]:
    point = PILOT_COORDINATES[location]
    params = {"latitude": point.latitude, "longitude": point.longitude,
              "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m",
              "hourly": "precipitation,precipitation_probability", "past_days": 1,
              "forecast_days": 3, "timezone": "Asia/Kolkata", "wind_speed_unit": "kmh"}
    url = OpenMeteoWeatherClient.endpoint + "?" + urlencode(params)
    outlook = parse_outlook(json.loads(read_public(url)), now)
    source = {"id": "W1", "kind": "weather", "title": "Weather context and 24-hour rain outlook",
              "publisher": "Open-Meteo", "url": url, "published_at": outlook["environment"]["observed_at"],
              "retrieved_at": now.isoformat(), "scope": "locality_grid", "content_scope": "modelled_weather",
              "excerpt": "Coordinate-based modelled weather; no street depth, road access or affected-person observations.",
              "limitation": outlook["limitation"], "data": outlook["environment"], "next_rain": outlook["next_rain"],
              "forecast_complete": outlook["forecast_complete"], "rain_threshold_mm": outlook["rain_threshold_mm"]}
    return outlook, source


_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()


def collect_context(location: PilotLocation, refresh: bool = False) -> dict:
    # Three pilot locations bound the cache; no user URLs or search strings.
    with _lock:
        cached = _cache.get(location)
        if not refresh and cached and time.monotonic() - cached[0] < 300:
            return json.loads(json.dumps(cached[1]))
        now = datetime.now(timezone.utc)
        sources, statuses = [], []
        outlook = None
        with ThreadPoolExecutor(max_workers=3) as executor:
            weather_job = executor.submit(fetch_outlook, location, now)
            jobs = [(publisher, domain, executor.submit(read_public, url)) for publisher, url, domain in FEEDS]
            try:
                outlook, source = weather_job.result()
                sources.append(source)
                statuses.append({"name": "Open-Meteo", "status": "available"})
            except Exception:
                statuses.append({"name": "Open-Meteo", "status": "unavailable"})
            for publisher, domain, job in jobs:
                try:
                    articles = parse_feed(job.result(), publisher, domain, location, now)
                    sources.extend(articles)
                    statuses.append({"name": publisher, "status": "available" if articles else "no_recent_match"})
                except Exception:
                    statuses.append({"name": publisher, "status": "unavailable"})
        unique = {s["id"]: s for s in sources}
        result = {"location": location, "retrieved_at": now.isoformat(), "outlook": outlook,
                  "sources": list(unique.values()), "source_status": statuses,
                  "coverage_note": "Two publisher city feeds and gridded weather only. This is not a comprehensive news search or official incident verification."}
        _cache[location] = (time.monotonic(), result)
        return json.loads(json.dumps(result))
