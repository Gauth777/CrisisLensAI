from __future__ import annotations

import argparse
import json
from pathlib import Path

from crisislens.config import build_provider
from crisislens.data import OpenMeteoWeatherClient
from crisislens.pipeline import CrisisLensPipeline
from crisislens.schemas import CrisisInput

SCENARIOS_PATH = Path(__file__).parent / "sample_data" / "crisis_examples.json"

def load_scenario(name: str) -> CrisisInput:
    scenarios = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    return CrisisInput.model_validate(scenarios[name])

def main() -> None:
    parser = argparse.ArgumentParser(description="Run a CrisisLens AI pilot scenario.")
    parser.add_argument(
        "--scenario",
        choices=["tambaram", "chromepet", "velachery"],
        default="velachery",
    )
    parser.add_argument(
        "--live-weather",
        action="store_true",
        help=(
            "Replace development weather values with current Open-Meteo gridded "
            "weather context. This is a fallback source, not an official Chennai observation."
        ),
    )
    args = parser.parse_args()

    crisis_input = load_scenario(args.scenario)

    if args.live_weather:
        environment = OpenMeteoWeatherClient().fetch(crisis_input.location)
        crisis_input = crisis_input.model_copy(update={"environment": environment})

    pipeline = CrisisLensPipeline(build_provider())
    result = pipeline.analyse(crisis_input)
    print(result.model_dump_json(indent=2))

if __name__ == "__main__":
    main()
