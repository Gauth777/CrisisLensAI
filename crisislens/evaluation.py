from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field

from .pipeline import CrisisLensPipeline
from .providers.base import LLMProvider
from .schemas import CrisisInput, CrisisOutput, PilotLocation, Severity


SEVERITY_ORDER: dict[Severity, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}


class BenchmarkExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disaster_type: str
    severity: Severity

    # Each inner list is one concept. Matching any term in that inner list
    # counts as one concept hit.
    evidence_term_groups: list[list[str]] = Field(default_factory=list)
    resource_term_groups: list[list[str]] = Field(default_factory=list)
    missing_information_term_groups: list[list[str]] = Field(default_factory=list)

    # Phrases that should never appear as factual claims for this scenario.
    forbidden_claim_terms: list[str] = Field(default_factory=list)


class BenchmarkScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    location: PilotLocation
    rationale: str
    input: CrisisInput
    expected: BenchmarkExpectation


class ScenarioScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    provider: str
    model: str | None = None
    latency_ms: float

    execution_ok: bool
    schema_valid: bool

    disaster_type_correct: bool = False
    severity_correct: bool = False
    severity_distance: int | None = None

    evidence_recall: float = 0.0
    resource_recall: float = 0.0
    missing_information_recall: float = 0.0
    forbidden_claim_violations: list[str] = Field(default_factory=list)

    composite_score: float = 0.0
    error: str | None = None
    output: dict[str, Any] | None = None


class BenchmarkSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str | None
    scenarios: int
    execution_success_rate: float
    schema_valid_rate: float
    disaster_type_accuracy: float
    severity_accuracy: float
    severity_mae: float | None
    mean_evidence_recall: float
    mean_resource_recall: float
    mean_missing_information_recall: float
    hallucination_free_rate: float
    mean_latency_ms: float
    mean_composite_score: float


@dataclass(frozen=True)
class BenchmarkRun:
    summary: BenchmarkSummary
    scores: list[ScenarioScore]


def load_scenarios(path: str | Path) -> list[BenchmarkScenario]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Benchmark dataset must be a JSON list.")
    return [BenchmarkScenario.model_validate(item) for item in payload]


def run_benchmark(
    provider: LLMProvider,
    scenarios: Iterable[BenchmarkScenario],
    *,
    provider_name: str | None = None,
) -> BenchmarkRun:
    pipeline = CrisisLensPipeline(provider)
    name = provider_name or provider.__class__.__name__
    model = getattr(provider, "model", None)

    scores: list[ScenarioScore] = []
    for scenario in scenarios:
        scores.append(
            evaluate_scenario(
                pipeline,
                scenario,
                provider_name=name,
                model=model,
            )
        )

    return BenchmarkRun(
        summary=summarize_scores(name, model, scores),
        scores=scores,
    )


def evaluate_scenario(
    pipeline: CrisisLensPipeline,
    scenario: BenchmarkScenario,
    *,
    provider_name: str,
    model: str | None,
) -> ScenarioScore:
    started = time.perf_counter()

    try:
        result = pipeline.analyse(scenario.input)
        latency_ms = (time.perf_counter() - started) * 1000.0
    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000.0
        return ScenarioScore(
            scenario_id=scenario.id,
            provider=provider_name,
            model=model,
            latency_ms=round(latency_ms, 2),
            execution_ok=False,
            schema_valid=False,
            error=f"{exc.__class__.__name__}: {exc}",
        )

    return score_output(
        scenario,
        result,
        provider_name=provider_name,
        model=model,
        latency_ms=latency_ms,
    )


def score_output(
    scenario: BenchmarkScenario,
    output: CrisisOutput,
    *,
    provider_name: str,
    model: str | None,
    latency_ms: float,
) -> ScenarioScore:
    expected = scenario.expected

    disaster_type_correct = output.disaster_type == expected.disaster_type
    severity_correct = output.severity == expected.severity
    severity_distance = abs(
        SEVERITY_ORDER[output.severity] - SEVERITY_ORDER[expected.severity]
    )

    evidence_text = " ".join(
        item.statement for item in output.severity_evidence
    )
    resources_text = " ".join(output.resources_required)
    missing_text = " ".join(output.missing_information)
    full_text = _flatten_output(output)

    evidence_recall = _concept_recall(
        evidence_text,
        expected.evidence_term_groups,
    )
    resource_recall = _concept_recall(
        resources_text,
        expected.resource_term_groups,
    )
    missing_recall = _concept_recall(
        missing_text,
        expected.missing_information_term_groups,
    )

    violations = [
        term
        for term in expected.forbidden_claim_terms
        if _contains_term(full_text, term)
    ]

    # Transparent rubric; no LLM-as-judge is used.
    # Schema validity: 20
    # disaster type: 15
    # severity: 20
    # grounded evidence coverage: 20
    # resource concept coverage: 10
    # missing-info coverage: 10
    # no forbidden claims: 5
    composite = (
        20.0
        + (15.0 if disaster_type_correct else 0.0)
        + (20.0 if severity_correct else max(0.0, 20.0 - 7.0 * severity_distance))
        + 20.0 * evidence_recall
        + 10.0 * resource_recall
        + 10.0 * missing_recall
        + (5.0 if not violations else 0.0)
    )

    return ScenarioScore(
        scenario_id=scenario.id,
        provider=provider_name,
        model=model,
        latency_ms=round(latency_ms, 2),
        execution_ok=True,
        schema_valid=True,
        disaster_type_correct=disaster_type_correct,
        severity_correct=severity_correct,
        severity_distance=severity_distance,
        evidence_recall=round(evidence_recall, 4),
        resource_recall=round(resource_recall, 4),
        missing_information_recall=round(missing_recall, 4),
        forbidden_claim_violations=violations,
        composite_score=round(composite, 2),
        output=output.model_dump(mode="json"),
    )


def summarize_scores(
    provider_name: str,
    model: str | None,
    scores: list[ScenarioScore],
) -> BenchmarkSummary:
    if not scores:
        raise ValueError("Cannot summarize an empty benchmark run.")

    successful = [score for score in scores if score.execution_ok]
    valid = [score for score in scores if score.schema_valid]

    distances = [
        score.severity_distance
        for score in valid
        if score.severity_distance is not None
    ]

    return BenchmarkSummary(
        provider=provider_name,
        model=model,
        scenarios=len(scores),
        execution_success_rate=round(_rate(successful, len(scores)), 4),
        schema_valid_rate=round(_rate(valid, len(scores)), 4),
        disaster_type_accuracy=round(
            _bool_rate(valid, "disaster_type_correct"),
            4,
        ),
        severity_accuracy=round(_bool_rate(valid, "severity_correct"), 4),
        severity_mae=round(mean(distances), 4) if distances else None,
        mean_evidence_recall=round(
            _field_mean(valid, "evidence_recall"),
            4,
        ),
        mean_resource_recall=round(
            _field_mean(valid, "resource_recall"),
            4,
        ),
        mean_missing_information_recall=round(
            _field_mean(valid, "missing_information_recall"),
            4,
        ),
        hallucination_free_rate=round(
            (
                sum(1 for score in valid if not score.forbidden_claim_violations)
                / len(valid)
            )
            if valid
            else 0.0,
            4,
        ),
        mean_latency_ms=round(
            mean(score.latency_ms for score in scores),
            2,
        ),
        mean_composite_score=round(
            mean(score.composite_score for score in scores),
            2,
        ),
    )


def _concept_recall(text: str, groups: list[list[str]]) -> float:
    if not groups:
        return 1.0

    hits = 0
    for alternatives in groups:
        if any(_contains_term(text, term) for term in alternatives):
            hits += 1
    return hits / len(groups)


def _contains_term(text: str, term: str) -> bool:
    haystack = _normalize(text)
    needle = _normalize(term)
    return needle in haystack


def _normalize(text: str) -> str:
    value = text.lower()
    value = re.sub(r"[^a-z0-9.%/+-]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _flatten_output(output: CrisisOutput) -> str:
    pieces = [
        output.location,
        output.disaster_type,
        output.severity,
        *(item.statement for item in output.severity_evidence),
        *output.affected_people,
        *output.resources_required,
        *output.recommended_actions,
        *output.missing_information,
        output.situation_report,
    ]
    return " ".join(pieces)


def _rate(items: list[Any], total: int) -> float:
    return len(items) / total if total else 0.0


def _bool_rate(scores: list[ScenarioScore], field: str) -> float:
    if not scores:
        return 0.0
    return sum(bool(getattr(score, field)) for score in scores) / len(scores)


def _field_mean(scores: list[ScenarioScore], field: str) -> float:
    if not scores:
        return 0.0
    return mean(float(getattr(score, field)) for score in scores)
