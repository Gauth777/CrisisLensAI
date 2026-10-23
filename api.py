"""Local faculty-demo API. Run: python -m uvicorn api:app --reload."""
from __future__ import annotations

import json
import logging
import os
import time
import secrets
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from crisislens.config import build_provider, load_environment
from crisislens.data import OpenMeteoWeatherClient
from crisislens.data.environment import EnvironmentalDataError
from crisislens.data.context import collect_context
from crisislens.data.operations import operational_sources
from crisislens.workflow import Workflow as Operations, ReportInput, UpdateReview, ReportUpdate, PlanInput, PlanChange, Resource
from crisislens.recommendations import RecommendationQuestion, recommend
from crisislens.reliability import resource_check
from crisislens.pipeline import CrisisLensPipeline
from crisislens.simulation import router as simulation_router
from crisislens.provider_failures import classify_provider_failure
from crisislens.providers.gemini import DEFAULT_GEMINI_MODEL
from crisislens.providers.groq_provider import DEFAULT_GROQ_MODEL
from crisislens.schemas import CrisisInput, CrisisOutput, PilotLocation

ROOT = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)
load_environment()
ProviderName = Literal["gemini", "openai", "groq"]
_operations = None
_operations_lock = threading.Lock()


def operations():
    global _operations
    with _operations_lock:
        if _operations is None:
            _operations = Operations(os.getenv("CRISISLENS_DB_PATH", str(ROOT / "runtime/operations.sqlite3")))
        return _operations


@asynccontextmanager
async def lifespan(app):
    stop = threading.Event()
    def poll():
        while not stop.is_set():
            try:
                operations().poll()
            except Exception:
                logger.exception("Official-alert intake failed")
            stop.wait(120)
    worker = None
    if os.getenv("CRISISLENS_ALERT_POLLING", "1") != "0":
        worker = threading.Thread(target=poll, name="sachet-intake", daemon=True)
        worker.start()
    yield
    stop.set()
    if worker:
        worker.join(timeout=1)


app = FastAPI(title="CrisisLens AI", version="0.8.0", lifespan=lifespan)
app.include_router(simulation_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Review-Token"],
)


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: CrisisInput
    provider: ProviderName = "gemini"


class AnalysisMetadata(BaseModel):
    provider: ProviderName
    model: str
    generated_at: str
    latency_ms: float


class AnalysisResponse(BaseModel):
    input: CrisisInput
    assessment: CrisisOutput
    metadata: AnalysisMetadata


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": "0.8.0",
        "default_provider": os.getenv("CRISISLENS_PROVIDER", "gemini").strip().lower(),
        "providers": {
            "gemini": {"configured": bool((os.getenv("GEMINI_API_KEY") or "").strip()), "model": (os.getenv("GEMINI_MODEL") or "").strip() or DEFAULT_GEMINI_MODEL},
            "openai": {"configured": bool((os.getenv("OPENAI_API_KEY") or "").strip()), "model": (os.getenv("OPENAI_MODEL") or "").strip() or "gpt-5-mini"},
            "groq": {"configured": bool((os.getenv("GROQ_API_KEY") or "").strip()), "model": (os.getenv("GROQ_MODEL") or "").strip() or DEFAULT_GROQ_MODEL},
        },
    }


@app.get("/api/scenarios")
def scenarios():
    data = json.loads((ROOT / "sample_data/crisis_examples.json").read_text(encoding="utf-8"))
    return [{"id": key, "input": CrisisInput.model_validate(value).model_dump(mode="json")} for key, value in data.items()]


@app.get("/api/weather/{location}")
def weather(location: PilotLocation):
    try:
        return OpenMeteoWeatherClient().fetch(location).model_dump(mode="json")
    except (EnvironmentalDataError, ValidationError, ValueError, KeyError) as exc:
        raise HTTPException(503, "Weather unavailable. Retry or explicitly use unknown/manual context.") from exc


@app.post("/api/analyse", response_model=AnalysisResponse)
def analyse(request: AnalysisRequest):
    key_name = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY", "groq": "GROQ_API_KEY"}[request.provider]
    if not os.getenv(key_name):
        raise HTTPException(503, f"Configure {key_name} in the backend .env and restart the server.")
    started = time.perf_counter()
    try:
        provider = build_provider(request.provider)
        assessment = CrisisLensPipeline(provider).analyse(request.input)
    except (ValidationError, ValueError, TypeError) as exc:
        logger.warning("CrisisLens failure: provider=%s category=invalid_assessment", request.provider)
        raise HTTPException(502, "The model returned an invalid assessment. No result was accepted; retry generation.") from exc
    except Exception as exc:
        failure = classify_provider_failure(exc, request.provider)
        logger.warning("CrisisLens failure: provider=%s category=%s upstream_status=%s error_type=%s provider_code=%s", request.provider, failure.category, failure.upstream_status, type(exc).__name__, failure.provider_code)
        headers = {"X-CrisisLens-Error": failure.category}
        if failure.provider_code:
            headers["X-CrisisLens-Provider-Code"] = failure.provider_code
        raise HTTPException(failure.http_status, failure.detail, headers=headers) from exc
    return AnalysisResponse(
        input=request.input,
        assessment=assessment,
        metadata=AnalysisMetadata(
            provider=request.provider,
            model=getattr(provider, "model", "unknown"),
            generated_at=datetime.now(timezone.utc).isoformat(),
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        ),
    )


@app.get("/api/context/{location}")
def context(location: PilotLocation, refresh: bool = False):
    return collect_context(location, refresh=refresh)


@app.get("/api/operations/{location}")
def operational_context(location: PilotLocation):
    return operations().snapshot(location)


@app.post("/api/reports", status_code=201)
def submit_report(report: ReportInput):
    return operations().submit(report)


def authorize_coordinator(x_review_token):
    expected = os.getenv("CRISISLENS_REVIEW_TOKEN", "").strip()
    if not expected:
        raise HTTPException(503, "Coordinator review is disabled. Configure CRISISLENS_REVIEW_TOKEN on the server.")
    if not secrets.compare_digest(x_review_token.encode(), expected.encode()):
        raise HTTPException(403, "A valid coordinator review token is required.")


@app.post("/api/reports/{identifier}/review")
def review_report(identifier: str, review: UpdateReview, x_review_token: str = Header(default="")):
    authorize_coordinator(x_review_token)
    try:
        return operations().review(identifier, review)
    except KeyError:
        raise HTTPException(404, "Field report not found.")
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@app.post("/api/reports/{identifier}/updates", status_code=201)
def report_update(identifier: str, update: ReportUpdate):
    try:
        return operations().add_update(identifier, update)
    except KeyError:
        raise HTTPException(404, "Report not found.")
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@app.get("/api/plans")
def list_plans():
    return operations().plans()


@app.post("/api/plans", status_code=201)
def save_plan(plan: PlanInput):
    try:
        return operations().create_plan(plan)
    except KeyError:
        raise HTTPException(404, "Report or briefing not found.")
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@app.post("/api/plans/{identifier}")
def change_plan(identifier: str, change: PlanChange, x_review_token: str = Header(default="")):
    if change.action in ("approve", "close"):
        authorize_coordinator(x_review_token)
    try:
        return operations().change_plan(identifier, change)
    except KeyError:
        raise HTTPException(404, "Plan not found.")
    except ValueError as exc:
        raise HTTPException(409, str(exc))


class RecommendationRequest(RecommendationQuestion):
    provider: ProviderName = "groq"
    report_id: str | None = None
    resources: list[Resource] = Field(default_factory=list, max_length=5)
    volunteers: int = Field(default=0, ge=0, le=10000)


@app.post("/api/recommend")
def recommendations(request: RecommendationRequest):
    key_name = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY", "groq": "GROQ_API_KEY"}[request.provider]
    if not (os.getenv(key_name) or "").strip():
        raise HTTPException(503, f"Configure {key_name} in backend .env and restart.")
    started = time.perf_counter()
    bundle = collect_context(request.location)
    snapshot = operations().snapshot(request.location)
    if request.report_id and not any(r["id"] == request.report_id for r in snapshot["reports"]):
        raise HTTPException(404, "This report is no longer in the current seven-day area snapshot.")
    operational = operational_sources(snapshot)
    if request.report_id:
        operational = [s for s in operational if s["kind"] != "field_report" or s["id"] == "F" + request.report_id]
    bundle["sources"].extend(operational)
    selected = next((r for r in snapshot["reports"] if r["id"] == request.report_id), None)
    bundle["evidence_issues"] = resource_check(selected, [r.model_dump() for r in request.resources])
    bundle["source_status"].append({"name": "SACHET official alerts", "status": "stale_or_unavailable" if snapshot["feed"]["stale"] else "available"})
    bundle["coverage_note"] += " " + snapshot["feed"]["coverage"]
    bundle["sources"].append({"id": "U1", "kind": "user", "title": "Your question or report",
        "publisher": "User supplied", "url": None, "published_at": None,
        "retrieved_at": datetime.now(timezone.utc).isoformat(), "excerpt": request.question,
        "scope": "locality", "content_scope": "unverified_input",
        "limitation": "Not independently verified. A question is not evidence that an incident occurred."})
    if request.demo:
        # Never combine synthetic development measurements with live sources.
        bundle = {"location": request.location, "retrieved_at": datetime.now(timezone.utc).isoformat(),
                  "outlook": None, "source_status": [], "coverage_note": "Fictional demonstration, not a real incident.",
                  "sources": [bundle["sources"][-1]]}
    try:
        provider = build_provider(request.provider)
        answer = recommend(provider, request, bundle)
    except (ValidationError, ValueError, TypeError) as exc:
        logger.warning("CrisisLens recommendation failure: provider=%s category=invalid_citations_or_output", request.provider)
        raise HTTPException(502, "The response failed structure or citation checks. No recommendation was accepted; try again.") from exc
    except Exception as exc:
        failure = classify_provider_failure(exc, request.provider)
        logger.warning("CrisisLens recommendation failure: provider=%s category=%s provider_code=%s", request.provider, failure.category, failure.provider_code)
        raise HTTPException(failure.http_status, failure.detail) from exc
    response = {"question": request.model_dump(), "recommendation": answer.model_dump(), "context": bundle,
            "metadata": {"provider": request.provider, "model": provider.model,
                         "generated_at": datetime.now(timezone.utc).isoformat(),
                         "latency_ms": round((time.perf_counter() - started) * 1000, 2)}}
    selected = next((r for r in snapshot["reports"] if r["id"] == request.report_id), None)
    response["resource_check"] = resource_check(selected, [r.model_dump() for r in request.resources])
    response["validation"] = {"citation_ids_checked": True, "source_types_checked": True, "semantic_truth_verified": False, "claim_count": len(answer.claims), "uncertain_claims": sum(c.status == "insufficient_evidence" for c in answer.claims)}
    response["report_revision"] = next((r["revision"] for r in snapshot["reports"] if r["id"] == request.report_id), None)
    response["briefing_id"] = operations().save_briefing(response)
    return response


@app.get("/api/evaluation")
def evaluation_results():
    from crisislens.intelligence_eval import run_evaluation
    return run_evaluation()


# Build the frontend before starting this server to use a single localhost URL.
DIST = ROOT / "frontend/dist"
if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="frontend")
