from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from crisislens.config import build_provider
from crisislens.evaluation import BenchmarkRun, load_scenarios, run_benchmark


DEFAULT_DATASET = Path("evaluation/scenarios.json")


def _select_scenarios(args):
    scenarios = load_scenarios(args.dataset)

    if args.location:
        scenarios = [s for s in scenarios if s.location == args.location]

    if args.scenario_id:
        wanted = set(args.scenario_id)
        scenarios = [s for s in scenarios if s.id in wanted]

    if args.limit is not None:
        scenarios = scenarios[: args.limit]

    if not scenarios:
        raise SystemExit("No benchmark scenarios matched the requested filters.")

    return scenarios


def _print_summary(run: BenchmarkRun) -> None:
    s = run.summary
    print()
    print(f"Provider:                 {s.provider}")
    print(f"Model:                    {s.model or 'unknown'}")
    print(f"Scenarios:                {s.scenarios}")
    print(f"Execution success:        {s.execution_success_rate:.1%}")
    print(f"Schema validity:          {s.schema_valid_rate:.1%}")
    print(f"Disaster type accuracy:   {s.disaster_type_accuracy:.1%}")
    print(f"Severity accuracy:        {s.severity_accuracy:.1%}")
    print(
        "Severity MAE:             "
        + (f"{s.severity_mae:.3f}" if s.severity_mae is not None else "n/a")
    )
    print(f"Evidence recall:          {s.mean_evidence_recall:.1%}")
    print(f"Resource recall:          {s.mean_resource_recall:.1%}")
    print(f"Missing-info recall:      {s.mean_missing_information_recall:.1%}")
    print(f"Hallucination-free:       {s.hallucination_free_rate:.1%}")
    print(f"Mean latency:             {s.mean_latency_ms:.1f} ms")
    print(f"Composite score:          {s.mean_composite_score:.2f}/100")


def _save_run(run: BenchmarkRun, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_provider = run.summary.provider.lower().replace(" ", "_")

    json_path = output_dir / f"{safe_provider}_{stamp}.json"
    csv_path = output_dir / f"{safe_provider}_{stamp}.csv"

    json_payload = {
        "summary": run.summary.model_dump(mode="json"),
        "scores": [score.model_dump(mode="json") for score in run.scores],
    }
    json_path.write_text(
        json.dumps(json_payload, indent=2),
        encoding="utf-8",
    )

    fields = [
        "scenario_id",
        "provider",
        "model",
        "latency_ms",
        "execution_ok",
        "schema_valid",
        "disaster_type_correct",
        "severity_correct",
        "severity_distance",
        "evidence_recall",
        "resource_recall",
        "missing_information_recall",
        "forbidden_claim_violations",
        "composite_score",
        "error",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for score in run.scores:
            row = score.model_dump(mode="json")
            row["forbidden_claim_violations"] = "; ".join(
                score.forbidden_claim_violations
            )
            writer.writerow({field: row.get(field) for field in fields})

    return json_path, csv_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark CrisisLens providers on controlled Chennai scenarios."
    )
    parser.add_argument(
        "--provider",
        choices=["gemini", "openai", "both"],
        default="gemini",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
    )
    parser.add_argument(
        "--location",
        choices=["Tambaram", "Chromepet", "Velachery"],
    )
    parser.add_argument(
        "--scenario-id",
        action="append",
        help="Run only a specific scenario ID. May be repeated.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Run only the first N scenarios after filtering.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmark_results"),
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Print results without writing JSON/CSV artifacts.",
    )
    args = parser.parse_args()

    scenarios = _select_scenarios(args)
    providers = (
        ["gemini", "openai"]
        if args.provider == "both"
        else [args.provider]
    )

    failures = 0
    for provider_name in providers:
        print(f"\nRunning {provider_name} on {len(scenarios)} scenarios...")

        try:
            provider = build_provider(provider_name)
        except Exception as exc:
            failures += 1
            print(f"Could not initialize {provider_name}: {exc}")
            continue

        run = run_benchmark(
            provider,
            scenarios,
            provider_name=provider_name,
        )
        _print_summary(run)

        if not args.no_save:
            json_path, csv_path = _save_run(run, args.output_dir)
            print(f"Saved JSON: {json_path}")
            print(f"Saved CSV:  {csv_path}")

    if failures == len(providers):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
