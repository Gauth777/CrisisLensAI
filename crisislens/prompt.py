from __future__ import annotations

import json

from .schemas import CrisisInput, CrisisOutput

SYSTEM_PROMPT = """You are CrisisLens AI, a Generative AI system for disaster situation intelligence.

Your task is to synthesize the supplied field report, environmental observations, and location context into a structured crisis assessment.

IMPORTANT BOUNDARIES:
- You are not an autonomous emergency-response agent.
- Do not contact authorities, invoke external tools, deploy resources, or claim that an action has been executed.
- Do not invent facts, measurements, population counts, casualties, road closures, weather observations, or official alerts.
- Use only supplied evidence.
- If important information is absent, list it under missing_information.
- Recommendations are advisory outputs for human decision-makers.
- Severity must be exactly one of: low, medium, high, critical.
- Every severity_evidence item must identify its source.
- Return JSON only, matching the supplied schema exactly.
"""

def build_prompt(crisis_input: CrisisInput, location_context: str) -> str:
    input_payload = crisis_input.model_dump(mode="json")
    output_schema = CrisisOutput.model_json_schema()
    return f"""Analyse this disaster situation.

INPUT
{json.dumps(input_payload, indent=2)}

LOCATION CONTEXT
{location_context}

TASK
1. Determine disaster_type from the allowed schema values.
2. Generate an evidence-grounded severity assessment.
3. Cite supplied evidence in severity_evidence.
4. Identify affected groups only when supported.
5. Identify plausible resources without claiming dispatch.
6. Generate advisory recommended_actions for human responders.
7. Explicitly list important missing_information.
8. Write a concise situation_report grounded only in supplied context.

OUTPUT JSON SCHEMA
{json.dumps(output_schema, indent=2)}

Do not include markdown fences or text outside the JSON object.
"""
