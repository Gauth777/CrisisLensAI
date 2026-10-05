from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PilotLocation = Literal["Tambaram", "Chromepet", "Velachery"]
Severity = Literal["low", "medium", "high", "critical"]

class EnvironmentalData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rainfall_1h_mm: float | None = Field(default=None, ge=0)
    rainfall_24h_mm: float | None = Field(default=None, ge=0)
    temperature_c: float | None = Field(default=None, ge=-20, le=60)
    humidity_percent: float | None = Field(default=None, ge=0, le=100)
    wind_speed_kmph: float | None = Field(default=None, ge=0)
    wind_direction_deg: float | None = Field(default=None, ge=0, le=360)
    water_level_m: float | None = Field(default=None, ge=0)

    # Provenance is carried into the LLM prompt so the model can distinguish
    # official observations from development fallbacks.
    observed_at: str | None = None
    source_name: str | None = None
    source_kind: Literal[
        "official_observation",
        "official_flood_monitor",
        "gridded_weather_fallback",
        "manual_development_input",
    ] | None = None

class CrisisInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report: str = Field(min_length=5)
    location: PilotLocation
    timestamp: str | None = None
    environment: EnvironmentalData = Field(default_factory=EnvironmentalData)
    source_label: str = "citizen_or_field_report"

class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    statement: str = Field(min_length=1)
    source: Literal["field_report", "environmental_context", "location_context"]

class CrisisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    location: PilotLocation
    disaster_type: Literal[
        "urban_flooding",
        "cyclone",
        "heavy_rainfall",
        "waterlogging",
        "infrastructure_damage",
        "medical_emergency",
        "fire",
        "other",
    ]
    severity: Severity
    severity_evidence: list[EvidenceItem] = Field(min_length=1)
    affected_people: list[str]
    resources_required: list[str]
    recommended_actions: list[str]
    missing_information: list[str]
    situation_report: str = Field(min_length=20)
