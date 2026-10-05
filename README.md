# CrisisLens AI

CrisisLens AI is a location-aware Generative AI pipeline that converts unstructured disaster reports plus environmental context into structured crisis intelligence for Chennai.

Initial pilot locations: **Tambaram, Chromepet, and Velachery**.

## Core idea

Citizen/field report -> input validation -> location context -> environmental grounding -> deterministic prompt -> model-agnostic LLM -> Pydantic validation -> structured crisis intelligence.

The system generates disaster type, evidence-grounded severity, affected groups, resource requirements, recommended response actions, missing information, and a concise situation report.

## Important boundary

CrisisLens is deliberately **non-agentic**. It does not autonomously choose tools, contact authorities, deploy resources, execute actions, or pursue goals. Recommendations are generated for human decision-makers.

## V0.1 milestone

- Model-independent LLM provider interface
- Deterministic crisis prompt
- Pydantic input/output contracts
- Missing-information handling
- Evidence-grounded severity
- Chennai pilot scenarios
- Gemini and OpenAI adapters
- Offline tests using a mock provider

## Planned progression

1. Connect official Chennai environmental/flood data.
2. Add location-specific grounding for Tambaram, Chromepet, and Velachery.
3. Build an evaluation dataset.
4. Benchmark candidate LLMs for groundedness, JSON adherence, hallucination rate, latency, and cost.
5. Add the dashboard only after the inference pipeline is stable.
