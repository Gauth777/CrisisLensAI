# CrisisLens AI

CrisisLens AI is a **location-aware Generative AI pipeline** that converts unstructured disaster reports plus environmental context into structured crisis intelligence for Chennai.

Initial pilot locations: **Tambaram, Chromepet, and Velachery**.

## Run the custom React workspace (V0.4)

The faculty demo now has a React + TypeScript frontend and a FastAPI backend.
Use **Python 3.11+ and Node.js 22+**. From the repository root:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and configure at least one provider key. The UI
lets you choose Gemini or OpenAI; keys remain on the backend. A configured key
is not proof of valid credentials or available quota. Restart the backend after
changing `.env`.

Before the demo, verify a **real, schema-validated assessment** with:

```bash
python -m crisislens.doctor
```

This makes one synthetic assessment per configured provider (normal API usage),
prints safe diagnostics and tells you which provider passed. It detects shell
variables overriding `.env`, unavailable Gemini quotas, and OpenAI billing vs
rate limits. It never prints keys or upstream response bodies. If shell settings
are stale, compare using `python -m crisislens.doctor --env-file-only`; this only
prefers file values for that check. Correct the shell settings and restart the
backend before using the UI. A `ready` result verifies the actual pipeline,
whereas `/api/health` only checks whether a key is present.

Build the frontend, then start the single-server demo:

```bash
cd frontend
npm ci
npm run build
cd ..
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. API documentation: http://127.0.0.1:8000/docs.
Build before starting the backend; the backend serves `frontend/dist` when it exists.

For frontend development, run the backend as above, then in a second terminal:

```bash
cd frontend
npm run dev
```

Open http://127.0.0.1:5173. Vite proxies `/api` to the local backend.
`npm run preview` alone does not connect to the backend; use the single-server
demo or the development proxy.

Workspace features:

- editable synthetic scenarios for all three pilot localities,
- sample, unknown, manual and live gridded-weather context with explicit provenance,
- real provider generation through the existing validated pipeline,
- severity evidence, situation report, resources, advisory actions and unknowns,
- input snapshot, provider/model metadata, generation duration and JSON export,
- clear errors for missing credentials, failed weather and invalid model responses.

There is **no simulated AI output fallback**. Without a valid provider key,
you can inspect inputs and the interface but cannot generate an assessment.
This localhost demo has no authentication or persistence. Do not expose it
publicly without access controls, request limits and a privacy review.

Faculty demo walkthrough: `docs/FACULTY_DEMO.md`.

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
GEMINI_MODEL=gemini-3.5-flash-lite
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
python -m pytest -q
```

Frontend checks (browser tests use explicit fixtures, not live API calls):

```bash
cd frontend
npm run build
npx playwright install chromium
npm run test:e2e
```

## Current milestone: V0.4

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
- custom responsive React assessment workspace
- FastAPI health, scenario, weather and assessment endpoints
- schema-constrained model generation and bounded provider request timeouts
- frontend production build and API tests in CI

Next:

1. run the benchmark with real Gemini/OpenAI credentials,
2. compare the actual scores and inspect failure cases,
3. refine prompt/schema where failures are systematic,
4. verify a stable Chennai Flood Monitor integration path,
5. strengthen factual-grounding checks and inspect model failure cases before wider use.
