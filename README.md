# CrisisLens AI

CrisisLens AI is a **source-linked recommendation system for NGOs**. Ask about a locality, available resources or a reported incident, then inspect the recommendations, supporting records and missing information before deciding how to help.

Initial pilot locations: **Tambaram, Chromepet, and Velachery**.

## Run the NGO recommendation interface

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
lets you choose Gemini, OpenAI or Groq; keys remain on the backend. A configured key
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
backend before using the UI. A `ready` result verifies the legacy assessment pipeline; also generate a recommendation in the browser to verify the new route. `/api/health` only checks whether a key is present.

### Free-plan setup with Groq

Create a key at https://console.groq.com/keys and keep the account on the Free
plan. Add these values to your local `.env` (pulling code does not edit it):

```dotenv
CRISISLENS_PROVIDER=groq
GROQ_API_KEY=your_private_groq_key
GROQ_MODEL=openai/gpt-oss-120b
```

Then run `python -m crisislens.doctor --provider groq --env-file-only`.
The provider uses Groq's endpoint and key, with no tools, and retains the same
Chennai grounding, strict structured output and Pydantic validation. The model
name identifies OpenAI's open-weight GPT-OSS model **hosted by Groq**, rather
than the OpenAI API or its prepaid account.

Groq lists this model on its Free plan. Check your account's active limits:
https://console.groq.com/docs/rate-limits. Free usage is limited; 429 errors are
reported without automatic retries or switching to another provider. Strict
output support: https://console.groq.com/docs/structured-outputs.
Rebuild the frontend and restart the backend after pulling to see the Groq
option. Backend `CRISISLENS_PROVIDER=groq` selects it on initial page load.

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

Interface features:

- question-first hero with locality selection and prompts for incidents, supplies and rain,
- modelled weather and a 24-hour rain outlook, with missing values kept unknown,
- recent relevant publisher-feed reports, original links and source availability,
- interactive Why / Evidence / Unknowns panels for claims and recommendations,
- affected groups and suggested supplies linked to the specific input records,
- mobile evidence sheet, keyboard-accessible panels and JSON briefing export,
- clearly separated hypothetical scenarios and safe provider errors.

There is **no simulated AI output fallback**. A working provider is required to generate recommendations. Source retrieval failures remain visible rather than becoming fabricated evidence.

### Retrieval and evidence

`GET /api/context/{location}` gathers Open-Meteo weather/forecast and bounded excerpts from the Indian Express and The Hindu Chennai RSS feeds. Reports are filtered to hazard-related mentions from the last seven days; city-wide reports are labelled context rather than locality confirmation. Retrieval is cached for five minutes. `?refresh=true` bypasses that cache.

`POST /api/recommend` accepts `{ "location": "Velachery", "question": "What should our volunteers verify?", "provider": "groq", "demo": false }`. It retrieves source records on the server, marks the question as unverified user input and validates the model's schema, locality and citation IDs. A weather record or user report alone cannot support an operational incident claim. Unknown citation IDs are rejected. Hypothetical mode excludes live sources from generation.

A source-linked claim is an interpretation for human review. Checking citation IDs does not validate semantic accuracy. Weather cannot prove flooding, affected-person counts, supply demand or safe roads. Missing news does not establish that a report is false. There are no official incident alerts or street-level observations connected yet.

Publisher coverage is limited and feeds may be unavailable. No full articles are scraped. The Indian Express RSS catalog specifies personal, non-commercial use; this academic prototype requires a licensing/access review before production NGO use: https://indianexpress.com/rss/. Weather documentation: https://open-meteo.com/en/docs.

This localhost demo has no authentication, dispatch or persistent incident history. Deployment requires access controls, request limits and appropriate handling of submitted reports.

Faculty walkthrough and next stages: [docs/FACULTY_DEMO.md](docs/FACULTY_DEMO.md).

## Legacy assessment pipeline

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
- Groq-hosted GPT-OSS,
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
