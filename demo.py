from __future__ import annotations

import argparse
import json
from pathlib import Path

from crisislens.config import build_provider
from crisislens.pipeline import CrisisLensPipeline
from crisislens.schemas import CrisisInput

SCENARIOS_PATH = Path(__file__).parent / "sample_data" / "crisis_examples.json"

def load_scenario(name: str) -> CrisisInput:
    scenarios = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    return CrisisInput.model_validate(scenarios[name])

def main() -> None:
    parser = argparse.ArgumentParser(description="Run a CrisisLens AI pilot scenario.")
    parser.add_argument("--scenario", choices=["tambaram", "chromepet", "velachery"], default="velachery")
    args = parser.parse_args()
    crisis_input = load_scenario(args.scenario)
    pipeline = CrisisLensPipeline(build_provider())
    result = pipeline.analyse(crisis_input)
    print(result.model_dump_json(indent=2))

if __name__ == "__main__":
    main()
