"""Local faculty-demo API. Run: python -m uvicorn api:app --reload."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, ValidationError

from crisislens.config import build_provider
from crisislens.data import OpenMeteoWeatherClient
from crisislens.data.environment import EnvironmentalDataError
from crisislens.pipeline import CrisisLensPipeline
from crisislens.schemas import CrisisInput, CrisisOutput, PilotLocation

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
ProviderName = Literal["gemini", "openai"]
app = FastAPI(title="CrisisLens AI", version="0.4.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
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
        "version": "0.4.0",
        "providers": {
            "gemini": {"configured": bool(os.getenv("GEMINI_API_KEY")), "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash")},
            "openai": {"configured": bool(os.getenv("OPENAI_API_KEY")), "model": os.getenv("OPENAI_MODEL", "gpt-5-mini")},
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
    key_name = "GEMINI_API_KEY" if request.provider == "gemini" else "OPENAI_API_KEY"
    if not os.getenv(key_name):
        raise HTTPException(503, f"Configure {key_name} in the backend .env and restart the server.")
    started = time.perf_counter()
    try:
        provider = build_provider(request.provider)
        assessment = CrisisLensPipeline(provider).analyse(request.input)
    except (ValidationError, ValueError, TypeError) as exc:
        raise HTTPException(502, "The model returned an invalid assessment. No result was accepted; retry generation.") from exc
    except Exception as exc:
        # Never return provider exception text: it can contain request details or credentials.
        raise HTTPException(502, "Model request failed. Check backend credentials, quota, model access and connectivity.") from exc
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


# Build the frontend before starting this server to use a single localhost URL.
DIST = ROOT / "frontend/dist"
if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="frontend")
