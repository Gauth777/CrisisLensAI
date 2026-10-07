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
- draggable OpenStreetMap Chennai map with live weather and historical-flooding layers,
- top Past trends panel with source-linked historical cases and an interactive rain guide,
- modelled weather and a 24-hour rain outlook, with missing values kept unknown,
- recent relevant publisher-feed reports, original links and source availability,
- interactive Why / Evidence / Unknowns panels for claims and recommendations,
- action-first results: short DO / WHY cards, with claims and longer context available on demand,
- affected groups and suggested supplies linked to the specific input records,
- mobile evidence sheet, keyboard-accessible panels and JSON briefing export,
- clearly separated hypothetical scenarios and safe provider errors.

There is **no simulated AI output fallback**. A working provider is required to generate recommendations. Source retrieval failures remain visible rather than becoming fabricated evidence.

### Interactive Chennai map

The hero uses Leaflet 1.9.4 and OpenStreetMap tiles, with visible attribution. Drag to pan, use +/− to zoom, or select a pilot marker. Representative weather points are used, not exact incident locations or locality boundaries. Marker selection updates the question area and clears an old answer.

Live weather displays modelled temperature and the next 24-hour rainfall total from `/api/context/{location}`. Totals are shown only for a complete 24-hour forecast with numeric values; missing data stays unknown. The map refreshes context every five minutes while the page is visible; manual refresh requests fresh retrieval. Observation timestamps and original weather links remain visible.

Past flooding displays curated December 2023 cases, with a link to their historical sources. It is static historical context. Current incident risk is explicitly unverified: no flood probability, street-depth estimate, safe-route assessment or official alert layer is inferred from rainfall. Coverage is three representative pilot points, not every area visible on the map. Clicking elsewhere reports the coverage gap.

Map tiles need internet access and follow [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/). Browser tests intercept tile requests and use explicit fixtures; they test interaction and data handling, not live tile availability. There is no tile prefetch or offline-download feature. Optional `VITE_MAP_TILE_URL` and `VITE_MAP_ATTRIBUTION` build settings let deployment use a different properly licensed tile provider; these values are public frontend configuration. Production deployments should use a suitable tile service and its attribution terms.

### Past trends and rainfall literacy

Past trends opens a curated learning panel, available without an API key. Each pilot has a December 2023 case, alongside regional 2015 flood and NGO-relief examples. Event dates, locality coverage, source links and missing evidence remain visible. This is qualitative historical context, not statistical trend analysis or an automatically updated incident archive. These records are not inserted into live recommendations.

The Rain guide explains rainfall depth, duration and daily IMD categories, with illustrative 4 mm / 24 h versus 4 mm / 1 h examples. Categories are not evacuation thresholds. No universal rainfall amount establishes safety or a relief requirement. Source notes and maintenance instructions: [docs/HISTORICAL_CONTEXT.md](docs/HISTORICAL_CONTEXT.md).

### Official alerts and field reports

The **On the ground** panel works without a model key or generation request:

- A background worker retrieves [NDMA SACHET RSS](https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml) and its official CAP documents. It monitors IMD Chennai, Tamil Nadu issuer and CWC entries, waits 120 seconds between completed polls, caches immutable CAP records and displays their issuer, certainty, issue time, expiry and original link.
- Matching is **district-level**: Chennai for Velachery; Chengalpattu for Tambaram/Chromepet. Even when CAP includes polygons, this first version does not claim a street-level/geofence match. A warning is not an observed flood or a confirmed assistance request. Test/exercise, expired, cancelled and superseded records do not become active warnings. Missing expiry remains unknown; future-effective warnings remain upcoming.
- The browser checks the local snapshot every 20 seconds. Failed or incomplete intake, or a successful check older than five minutes, is labelled stale. No match is never an all-clear. Publication/observation time remains separate from retrieval time.
- **Add field report** records a landmark, actual observation time (IST), description and reported requests. Reports start unreviewed. To enable the coordinator review form, set `CRISISLENS_REVIEW_TOKEN` to a private random value in backend `.env` and restart. Enter it in the coordinator form with the check method and evidence note. This is a shared local-demo credential, not production identity verification; the token is not stored in browser storage.
- Reviews append an audit entry; conflicting edits require a reload. A human review is not independent certification. Observations older than six hours, rejected/resolved reports, and unreviewed reports are excluded from AI evidence. Reports remain visible for seven days, with stale labels.

`GET /api/operations/{location}` serves snapshots without calling the model. `POST /api/reports` accepts reports; `POST /api/reports/{id}/review` requires `X-Review-Token`. The database defaults to ignored `runtime/operations.sqlite3`, with `CRISISLENS_DB_PATH` override. Keep it across restarts. No fixture reports are inserted automatically. Use `CRISISLENS_ALERT_POLLING=0` only when intentionally disabling upstream polling.

This local prototype has persistent alerts/report history but no public-user authentication or submission rate limits. Before external deployment, add per-user roles, abuse prevention, retention/privacy rules and source monitoring. Reports submitted to another server are not automatically shared here. Direct rain-gauge, water-level, drainage, shelter and road-access integrations are still required; they are not replaced by a warning feed.

### Retrieval and evidence

`GET /api/context/{location}` gathers Open-Meteo weather/forecast and bounded excerpts from the Indian Express and The Hindu Chennai RSS feeds. Reports are filtered to hazard-related mentions from the last seven days; city-wide reports are labelled context rather than locality confirmation. Retrieval is cached for five minutes. `?refresh=true` bypasses that cache.

`POST /api/recommend` accepts `{ "location": "Velachery", "question": "What should our volunteers verify?", "provider": "groq", "demo": false }`. It combines retrieved context with current SACHET warnings and recent coordinator-reviewed field reports, marks the question as unverified user input and validates the model's schema, locality and citation IDs. A weather record, district warning or unreviewed user report alone cannot support an operational incident claim. Official warnings can support warning claims; reviewed local reports can support reported incident/needs/access claims. Unknown citation IDs are rejected. Hypothetical mode excludes live sources from generation.

A source-linked claim is an interpretation for human review. Checking citation IDs does not validate semantic accuracy. Weather cannot prove flooding, affected-person counts, supply demand or safe roads. Missing news does not establish that a report is false. SACHET supplies official district warnings, while submitted field reports supply local observations subject to coordinator review. Neither is a guaranteed street-level incident detection service.

Publisher coverage is limited and feeds may be unavailable. No full articles are scraped. The Indian Express RSS catalog specifies personal, non-commercial use; this academic prototype requires a licensing/access review before production NGO use: https://indianexpress.com/rss/. Weather documentation: https://open-meteo.com/en/docs.

This localhost demo has no automated dispatch. Coordinator review uses a shared token; deployment requires per-user access controls, request limits and appropriate handling of submitted reports.

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

## Current milestone: V0.5

Completed:

- independent SACHET warning intake, expiry/update/cancellation handling and feed freshness
- persistent field reports, protected coordinator review and audit history
- responsive NGO recommendations, official evidence panel and interactive Chennai map

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
