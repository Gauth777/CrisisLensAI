"""Run: python evaluate_intelligence.py [--provider groq] [--output runtime/intelligence-evaluation.json]"""
import csv
import argparse
import json
from pathlib import Path
from crisislens.intelligence_eval import run_evaluation
from crisislens.config import build_provider, load_environment

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["groq", "gemini", "openai"])
    parser.add_argument("--output", default="runtime/intelligence-evaluation.json")
    args = parser.parse_args()
    load_environment()
    result = run_evaluation(build_provider(args.provider) if args.provider else None)
    result["provider"] = args.provider or "scripted_fixture"
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    with path.with_suffix(".review.csv").open("w", newline="", encoding="utf-8") as handle:
        columns = ["case_id", "title", "expected_status", "raw_output", "validated_output", "reviewer", "claim_faithfulness", "citation_relevance", "resource_suitability", "unsafe_suggestion", "review_notes"]
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in result["cases"][:6]:
            writer.writerow({"case_id": row["id"], "title": row["title"], "expected_status": row["expected"], "raw_output": json.dumps(row.get("raw_output"), ensure_ascii=False), "validated_output": json.dumps(row.get("output"), ensure_ascii=False)})
    print(json.dumps({k:v for k,v in result.items() if k != "cases"}, indent=2))
