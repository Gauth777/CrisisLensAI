# CrisisLens AI

CrisisLens AI is a **location-aware Generative AI pipeline** that converts unstructured disaster reports plus environmental context into structured crisis intelligence for Chennai.

Initial pilot locations: **Tambaram, Chromepet, and Velachery**.

## Core pipeline

Citizen / field report  
-> input validation  
-> deterministic location + environmental grounding  
-> prompt construction  
-> model-agnostic LLM  
-> Pydantic schema validation  
-> structured crisis intelligence

The generated output includes:

- disaster type,
- evidence-grounded severity,
- affected groups,
- resource requirements,
- recommended response actions,
- missing information, and
- a concise situation report.

## Non-agentic by design

CrisisLens does **not** autonomously choose tools, contact authorities, deploy resources, execute emergency actions, or pursue goals.

Data acquisition happens before LLM invocation in deterministic application code. The LLM only receives prepared context and generates an advisory structured report for human decision-makers.

## Environmental grounding

V0.2 adds a source-aware environmental layer.

Source precedence is:

1. Chennai Flood Monitor / RTFF & SDSS — preferred local official source.
2. IMD AWS/ARG — official weather observations; documented API requires public-IP whitelisting.
3. Open-Meteo — gridded weather fallback used for development.
4. UNKNOWN — when evidence is unavailable.

Open-Meteo currently supplies development-time rainfall, temperature, humidity, wind speed and wind direction for the three pilot localities. Local water level remains unknown until an official Chennai source is connected.

See `docs/DATA_SOURCES.md` for the source policy.

## Model portability

The model layer is abstracted behind one provider interface. The same pipeline can use:

- Gemini,
- OpenAI,
- a future local/open-source model.

This lets us benchmark models under identical prompts and output schemas instead of designing the project around one vendor.

## Setup

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
copy .env.example .env
```

Configure one provider in `.env`.

### Gemini

```env
CRISISLENS_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```

### OpenAI

```env
CRISISLENS_PROVIDER=openai
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5-mini
```

## Run

Use the stored development scenario:

```bash
python demo.py --scenario velachery
```

Replace its development weather values with current gridded weather context:

```bash
python demo.py --scenario velachery --live-weather
```

Available scenarios:

- `tambaram`
- `chromepet`
- `velachery`

The `--live-weather` option does **not** imply that the values are official station observations. Provenance is included in the environmental payload as `gridded_weather_fallback`.

## Tests

Tests do not require an API key.

```bash
pytest -q
```

## Current milestone: V0.2

Completed:

- Pydantic input/output contracts
- evidence-grounded severity
- explicit missing-information handling
- deterministic non-agentic prompt
- Gemini provider
- OpenAI provider
- Chennai pilot locality layer
- source provenance
- live weather fallback
- offline environmental parser tests
- offline inference pipeline tests

Next:

1. verify/integrate a stable Chennai Flood Monitor data path,
2. integrate IMD after deploy-time IP whitelisting if feasible,
3. build 30-50 controlled crisis evaluation scenarios,
4. benchmark candidate LLMs for schema adherence, groundedness, hallucination rate, latency and cost,
5. add dashboard/UI after model evaluation.
