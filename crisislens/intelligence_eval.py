"""Repeatable synthetic evidence challenge, with optional real-model evaluation."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from time import perf_counter
from statistics import mean
from .recommendations import RecommendationQuestion
from .evidence import evidence_brief
from .reliability import annotate_reports, resource_check


def cases():
    now = datetime.now(timezone.utc).isoformat()
    field = {"id": "F1", "kind": "field_report", "scope": "locality", "content_scope": "reviewed_report", "published_at": now, "excerpt": "A coordinator reports 120 litres of drinking water requested at a Velachery community point. Access still needs checking."}
    return [
        {"id": "rain-only", "title": "Velachery: heavy rain, no incident report", "sources": [{"id": "W1", "kind": "weather", "scope": "locality_grid", "content_scope": "modelled_weather", "excerpt": "Forecast 28 mm over one hour."}], "expected": "insufficient_evidence"},
        {"id": "rumour", "title": "Tambaram: unverified rescue message", "sources": [{"id": "U1", "kind": "user", "scope": "locality", "content_scope": "unverified_input", "excerpt": "An unverified message claims residents are stranded."}], "expected": "insufficient_evidence"},
        {"id": "city-news", "title": "Chromepet: city-wide article, no local confirmation", "sources": [{"id": "N1", "kind": "news", "scope": "city_context", "content_scope": "feed_excerpt", "excerpt": "Rain has affected parts of Chennai; no Chromepet observation is supplied."}], "expected": "insufficient_evidence"},
        {"id": "reviewed", "title": "Velachery: reviewed water request", "sources": [field], "expected": "supported"},
        {"id": "conflict", "title": "Velachery: contradictory access observations", "sources": [field], "issues": {"conflicts": [{"report_id": "F2", "reasons": ["Reports disagree about access"]}]}, "expected": "insufficient_evidence"},
        {"id": "empty", "title": "Tambaram: all sources unavailable", "sources": [], "expected": "insufficient_evidence"},
    ]


class ChallengeProvider:
    """Deliberately overconfident canned output to challenge the production guards."""
    model = "scripted-adversarial-fixture"
    def __init__(self, case):
        self.case = case
        self.raw = None
    def generate_json(self, **kwargs):
        sources = self.case['sources']
        if 'reviews' in kwargs['output_schema']['properties']:
            return {'reviews':[{'claim_id':'C1','verdict':'supported','reason':'Scripted overconfident review.','omitted_source_ids':[]}]}
        if 'headline' not in kwargs['output_schema']['properties']:
            sentence = sources[0]['excerpt'].split('. ')[0] if sources else 'Water is needed at this site.'
            if not sentence.endswith('.'): sentence += '.'
            return {'claims':[{'id':'C1','statement':sentence,'category':'needs','timeframe':'current',
                'explanation':'Scripted overconfident assessment.','next_check':'Check the site contact.',
                'evidence':[{'source_id':sources[0]['id'],'direction':'supports','passage':sources[0]['excerpt'],
                    'reason':'Scripted support.'}] if sources else []}]}
        self.raw = {"location": self.case["title"].split(":")[0], "headline": "Supplies requested", "answer": "The request is supported.",
            "claims": [{"statement": "The requested drinking water is needed at the site", "category": "needs", "status": "supported", "explanation": "Supported by the supplied record.", "source_ids": [s["id"] for s in self.case["sources"]]}],
            "recommendations": [], "supplies": [], "affected_groups": [], "missing_information": []}
        return deepcopy(self.raw)


def run_evaluation(provider=None):
    rows = []
    class Recorder:
        def __init__(self, engine):
            self.engine, self.raw = engine, None
            self.outputs = []
        def generate_json(self, **kwargs):
            self.raw = deepcopy(self.engine.generate_json(**kwargs))
            self.outputs.append(deepcopy(self.raw))
            return deepcopy(self.raw)
    for case in cases():
        engine = Recorder(provider or ChallengeProvider(case))
        context = {"sources": deepcopy(case["sources"]), "source_status": [], "coverage_note": "Synthetic evaluation, not a real incident.", "evidence_issues": case.get("issues", {})}
        started = perf_counter()
        try:
            answer, assessment = evidence_brief(engine, RecommendationQuestion(location=case["title"].split(":")[0], question="Evaluate only whether this specific water request is supported. Return exactly one needs claim. Do not infer a request from weather or unverified messages."), context)
            matched = len(answer.claims) == 1 and answer.claims[0].category == "needs" and answer.claims[0].status == case["expected"]
            rows.append({"id": case["id"], "title": case["title"], "passed": matched, "expected": case["expected"], "actual": [c.status for c in answer.claims], "latency_ms": round((perf_counter()-started)*1000, 2), "output": answer.model_dump(), "raw_output": engine.outputs, "evidence_assessment": assessment, "model_calls": len(engine.outputs), "sources": case["sources"], "evidence_issues": case.get("issues", {})})
        except Exception as exc:
            rows.append({"id": case["id"], "title": case["title"], "passed": False, "expected": case["expected"], "actual": "request_failed", "error_type": type(exc).__name__, "latency_ms": round((perf_counter()-started)*1000, 2)})
    now = datetime.now(timezone.utc)
    report = {"id": "a", "location": "Velachery", "landmark": "Training hall", "status": "reviewed", "observed_at": now.isoformat(), "resources": [{"kind": "water", "quantity": 120}], "access_status": "passable"}
    other = {**report, "id": "b", "access_status": "blocked"}
    paired = annotate_reports([deepcopy(report), other])
    check = resource_check(paired[0], [{"kind": "water", "quantity": 80}])
    for identifier, title, passed in [
        ("quantity-cap", "120 litres needed, 80 available: cap proposal at 80", resource_check(report, [{"kind": "water", "quantity": 80}])["rows"][0]["suggested_max"] == 80),
        ("conflict-hold", "Contradictory reports: withhold quantity proposal", check["status"] == "hold_for_check" and check["rows"][0]["suggested_max"] is None),
        ("stale-hold", "Old report: withhold quantity proposal", resource_check({**report, "observed_at": (now-timedelta(hours=7)).isoformat()}, [])["status"] == "hold_for_check"),
        ("unknown-quantity", "Unknown quantities: do not invent supply counts", resource_check({**report, "resources": []}, [])["rows"] == []),
    ]:
        rows.append({"id": identifier, "title": title, "passed": passed, "expected": "rule holds", "actual": "rule holds" if passed else "rule failed", "latency_ms": None, "kind": "deterministic_rule"})
    return {"run_at": now.isoformat(), "dataset_version": "evidence-challenge-v2", "mode": "live_model" if provider else "scripted_guardrail_test", "model": getattr(provider, "model", "scripted-adversarial-fixture"), "total": len(rows), "passed": sum(r["passed"] for r in rows), "claim_cases": 6, "raw_claim_status_matches": None, "claim_status_matches": sum(r["passed"] for r in rows[:6]), "mean_claim_pipeline_ms": round(mean(r["latency_ms"] for r in rows[:6]),2), "human_factual_accuracy": None, "limitations": "Synthetic author-labelled cases. These measure constrained claim-status agreement and safeguards, not real-world factual accuracy. Free-text reasoning and resource suitability need independent human scoring.", "cases": rows}
