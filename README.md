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

## Controlled model evaluation

V0.3 adds a **24-scenario synthetic benchmark** covering all three pilot locations equally:

- 8 Tambaram
- 8 Chromepet
- 8 Velachery

The evaluator measures:

- execution success,
- JSON/schema validity,
- disaster-type accuracy,
- severity accuracy and ordinal error,
- evidence-concept recall,
- resource-concept recall,
- missing-information recall,
- unsupported-claim violations,
- latency,
- a transparent 100-point composite score.

The evaluator is deterministic; it does not use another LLM as a judge.

Full methodology: `docs/BENCHMARKING.md`.

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

## Run one CrisisLens scenario

Stored development context:

```bash
python demo.py --scenario velachery
```

Replace it with current gridded weather context:

```bash
python demo.py --scenario velachery --live-weather
```

## Benchmark a model

Fast smoke benchmark:

```bash
python benchmark.py --provider gemini --limit 3
```

Full Gemini benchmark:

```bash
python benchmark.py --provider gemini
```

Full OpenAI benchmark:

```bash
python benchmark.py --provider openai
```

Compare both providers:

```bash
python benchmark.py --provider both
```

Run only one pilot locality:

```bash
python benchmark.py --provider gemini --location Velachery
```

Benchmark output is saved as JSON and CSV in `benchmark_results/`.

## Tests

Tests do not require an API key.

```bash
pytest -q
```

## Current milestone: V0.3

Completed:

- model-agnostic provider interface
- Pydantic input/output contracts
- deterministic non-agentic prompt
- Gemini and OpenAI adapters
- Chennai pilot locality layer
- environmental provenance
- live gridded-weather fallback
- explicit missing-information handling
- evidence-grounded severity output
- 24 controlled benchmark scenarios
- transparent deterministic evaluation metrics
- JSON + CSV benchmark reports
- offline pipeline, weather and evaluation tests

Next:

1. run the benchmark with real Gemini/OpenAI credentials,
2. compare the actual scores and inspect failure cases,
3. refine prompt/schema where failures are systematic,
4. verify a stable Chennai Flood Monitor integration path,
5. add UI only after the model pipeline is sufficiently reliable.
