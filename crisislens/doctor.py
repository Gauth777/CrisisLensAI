"""Run live provider checks: python -m crisislens.doctor.

Uses one synthetic CrisisLens request per configured provider. This consumes
normal provider quota/credits. Keys and upstream response bodies are never printed.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from dotenv import dotenv_values
from pydantic import ValidationError

from .config import ENV_FILE, build_provider, load_environment
from .pipeline import CrisisLensPipeline
from .provider_failures import classify_provider_failure
from .schemas import CrisisInput

SETTINGS = ("GEMINI_API_KEY", "GEMINI_MODEL", "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL", "GROQ_API_KEY", "GROQ_MODEL")
KEY_NAMES = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY", "groq": "GROQ_API_KEY"}
PLACEHOLDERS = {"your_api_key", "your_key_here", "your-api-key", "replace_me", "..."}


def environment_report(env_file: Path = ENV_FILE) -> dict:
    file_values = dotenv_values(env_file) if env_file.is_file() else {}
    # Capture conflicts before loading; never display either conflicting value.
    conflicts = [name for name in SETTINGS if name in os.environ and
                 file_values.get(name) is not None and os.environ[name] != file_values[name]]
    return {"env_file_found": env_file.is_file(), "shell_overrides_env_file": conflicts,
            "custom_openai_endpoint": bool(os.getenv("OPENAI_BASE_URL") or file_values.get("OPENAI_BASE_URL"))}


def probe(provider_name: str, crisis_input: CrisisInput) -> dict:
    key_name = KEY_NAMES[provider_name]
    key = (os.getenv(key_name) or "").strip()
    if not key:
        return {"provider": provider_name, "status": "missing_key", "action": f"Set {key_name} in backend .env."}
    if key.lower() in PLACEHOLDERS:
        return {"provider": provider_name, "status": "placeholder_key", "action": f"Replace the placeholder in {key_name}."}
    started = time.perf_counter()
    model_name = None
    try:
        provider = build_provider(provider_name)
        model_name = provider.model
        assessment = CrisisLensPipeline(provider).analyse(crisis_input)
    except (ValidationError, ValueError, TypeError):
        return {"provider": provider_name, "status": "failed", "model": model_name, "category": "invalid_assessment_or_configuration",
                "action": "Check provider configuration or schema support; the returned assessment was not accepted."}
    except Exception as exc:
        failure = classify_provider_failure(exc, provider_name)
        return {"provider": provider_name, "status": "failed", "model": model_name, "category": failure.category,
                "upstream_status": failure.upstream_status, "provider_code": failure.provider_code,
                "action": failure.detail}
    return {"provider": provider_name, "status": "ready", "model": provider.model,
            "latency_seconds": round(time.perf_counter() - started, 1),
            "schema_validated": True, "location": assessment.location}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["all", "both", "gemini", "openai", "groq"], default="all",
                        help="all checks all three providers; both retains the Gemini/OpenAI comparison.")
    parser.add_argument("--env-file-only", action="store_true",
                        help="Temporarily prefer .env settings for this check; does not edit files or your shell.")
    args = parser.parse_args(argv)
    env_report = environment_report()
    if args.env_file_only:
        file_values = dotenv_values(ENV_FILE) if ENV_FILE.is_file() else {}
        for name in SETTINGS:
            if name in file_values:
                os.environ[name] = file_values[name] or ""
        env_report["using_env_file_values_for_this_check"] = True
    load_environment()
    print("CrisisLens live check: one synthetic assessment per configured provider. No automatic retries.", flush=True)
    print(json.dumps({"environment": env_report}, indent=2), flush=True)
    if env_report["shell_overrides_env_file"]:
        print("NOTICE: listed shell variables override .env in the backend. Correct/remove stale shell settings, then restart. "
              "Use --env-file-only to compare against .env without changing your shell.", flush=True)
    scenarios = json.loads((ENV_FILE.parent / "sample_data/crisis_examples.json").read_text(encoding="utf-8"))
    crisis_input = CrisisInput.model_validate(next(iter(scenarios.values())))
    providers = list(KEY_NAMES) if args.provider == "all" else (["gemini", "openai"] if args.provider == "both" else [args.provider])
    ready = []
    for name in providers:
        print(f"Checking {name}...", flush=True)
        result = probe(name, crisis_input)
        print(json.dumps(result, indent=2), flush=True)
        if result["status"] == "ready":
            ready.append(name)
    if ready:
        print(f"LIVE PIPELINE VERIFIED: select {' or '.join(ready)} in the frontend. Restart backend after configuration changes.")
        return 0
    print("NO LIVE PROVIDER VERIFIED. Copy this safe output for diagnosis; do not share .env or API keys.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
