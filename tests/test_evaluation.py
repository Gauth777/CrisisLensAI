from __future__ import annotations

from pathlib import Path

from crisislens.evaluation import (
    BenchmarkScenario,
    load_scenarios,
    score_output,
    summarize_scores,
)
from crisislens.schemas import CrisisOutput


def _scenario() -> BenchmarkScenario:
    return BenchmarkScenario.model_validate(
        {
            "id": "TEST-01",
            "title": "Controlled flood case",
            "location": "Velachery",
            "rationale": "Unit-test scenario.",
            "input": {
                "report": (
                    "Knee-deep water is blocking traffic in Velachery and "
                    "an elderly resident needs help leaving a house."
                ),
                "location": "Velachery",
                "environment": {
                    "rainfall_1h_mm": 40,
                    "source_kind": "manual_development_input",
                },
            },
            "expected": {
                "disaster_type": "urban_flooding",
                "severity": "high",
                "evidence_term_groups": [
                    ["knee-deep", "knee deep"],
                    ["traffic"],
                    ["elderly"],
                ],
                "resource_term_groups": [
                    ["rescue", "evacuation"],
                ],
                "missing_information_term_groups": [
                    ["exact number", "affected count"],
                ],
                "forbidden_claim_terms": ["confirmed deaths"],
            },
        }
    )


def _output() -> CrisisOutput:
    return CrisisOutput.model_validate(
        {
            "location": "Velachery",
            "disaster_type": "urban_flooding",
            "severity": "high",
            "severity_evidence": [
                {
                    "statement": "The report states knee-deep water is blocking traffic.",
                    "source": "field_report",
                },
                {
                    "statement": "An elderly resident needs help leaving a house.",
                    "source": "field_report",
                },
            ],
            "affected_people": ["elderly resident", "commuters"],
            "resources_required": ["rescue assistance"],
            "recommended_actions": [
                "Human responders should assess safe evacuation access."
            ],
            "missing_information": ["Exact number of affected residents"],
            "situation_report": (
                "Reported flooding in Velachery is disrupting traffic and "
                "affecting a vulnerable resident."
            ),
        }
    )


def test_score_output_awards_full_controlled_match() -> None:
    score = score_output(
        _scenario(),
        _output(),
        provider_name="mock",
        model="mock-model",
        latency_ms=25.0,
    )

    assert score.schema_valid is True
    assert score.disaster_type_correct is True
    assert score.severity_correct is True
    assert score.severity_distance == 0
    assert score.evidence_recall == 1.0
    assert score.resource_recall == 1.0
    assert score.missing_information_recall == 1.0
    assert score.forbidden_claim_violations == []
    assert score.composite_score == 100.0


def test_forbidden_claim_reduces_hallucination_score() -> None:
    output = _output().model_copy(
        update={
            "situation_report": (
                "Confirmed deaths were reported, despite that fact not being "
                "present in the supplied scenario."
            )
        }
    )

    score = score_output(
        _scenario(),
        output,
        provider_name="mock",
        model="mock-model",
        latency_ms=25.0,
    )

    assert "confirmed deaths" in score.forbidden_claim_violations
    assert score.composite_score == 95.0


def test_summary_aggregates_scores() -> None:
    first = score_output(
        _scenario(),
        _output(),
        provider_name="mock",
        model="mock-model",
        latency_ms=20.0,
    )
    second = score_output(
        _scenario(),
        _output().model_copy(update={"severity": "medium"}),
        provider_name="mock",
        model="mock-model",
        latency_ms=30.0,
    )

    summary = summarize_scores("mock", "mock-model", [first, second])

    assert summary.scenarios == 2
    assert summary.schema_valid_rate == 1.0
    assert summary.disaster_type_accuracy == 1.0
    assert summary.severity_accuracy == 0.5
    assert summary.severity_mae == 0.5
    assert summary.mean_latency_ms == 25.0


def test_repository_dataset_has_24_balanced_scenarios() -> None:
    scenarios = load_scenarios(Path("evaluation/scenarios.json"))

    assert len(scenarios) == 24

    counts = {
        location: sum(1 for scenario in scenarios if scenario.location == location)
        for location in ("Tambaram", "Chromepet", "Velachery")
    }
    assert counts == {
        "Tambaram": 8,
        "Chromepet": 8,
        "Velachery": 8,
    }

    ids = [scenario.id for scenario in scenarios]
    assert len(ids) == len(set(ids))
