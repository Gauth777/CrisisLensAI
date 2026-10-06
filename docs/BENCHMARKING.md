# CrisisLens model evaluation

CrisisLens V0.3 uses a controlled benchmark rather than selecting an LLM by preference or brand.

## Dataset

`evaluation/scenarios.json` contains **24 synthetic, controlled Chennai scenarios**:

- 8 Tambaram
- 8 Chromepet
- 8 Velachery

The benchmark intentionally includes different disaster types and severity levels:

- heavy rainfall
- waterlogging
- urban flooding
- infrastructure damage
- fire
- medical emergency
- cyclone-like wind/rain conditions

The measurements in this file are **synthetic test inputs**, not historical observations. Each environmental payload is marked:

```json
{
  "source_name": "Synthetic benchmark scenario",
  "source_kind": "manual_development_input"
}
```

This prevents benchmark values from being presented as real Chennai weather records.

## What is evaluated

The evaluator is deterministic. It does **not** use another LLM to judge the answer.

### 1. Execution success

Did the provider return a usable response without an API/runtime failure?

### 2. Schema validity

Did the response satisfy the CrisisLens Pydantic output contract?

A response that is not valid structured CrisisLens JSON fails here.

### 3. Disaster-type accuracy

Exact match against the controlled expected class.

### 4. Severity accuracy

Exact match against:

```text
low -> medium -> high -> critical
```

The evaluator also reports severity MAE on that ordinal scale. A one-level error is less severe than a three-level error.

### 5. Evidence recall

Each scenario defines important evidence concepts that should appear in the generated `severity_evidence`.

Example:

```json
[
  ["knee deep", "knee-deep"],
  ["traffic movement has stopped"],
  ["elderly", "cannot leave"]
]
```

Each inner list represents alternative wording for one evidence concept.

### 6. Resource recall

Checks whether expected resource concepts are represented, while allowing wording variants.

### 7. Missing-information recall

CrisisLens is supposed to say what it does **not** know rather than invent it.

This metric checks whether important unknowns such as exact affected-person count, measured water depth, patient condition, or exact incident address are surfaced.

### 8. Forbidden-claim violations

Each scenario includes phrases that would indicate unsupported factual claims, for example:

- confirmed deaths
- an official alert that was never supplied
- claiming resources have already been deployed
- claiming evacuation has already been completed

This is a narrow, transparent hallucination check. It is not a complete factuality metric.

### 9. Latency

Wall-clock latency is recorded for each inference.

## Composite score

The current transparent rubric is:

| Component | Weight |
|---|---:|
| Schema validity | 20 |
| Disaster type | 15 |
| Severity | 20 |
| Evidence coverage | 20 |
| Resource coverage | 10 |
| Missing-information coverage | 10 |
| No forbidden claim | 5 |
| **Total** | **100** |

Severity receives partial credit when it is off by one or more adjacent levels.

The composite score is useful for quick model comparison, but the individual metrics should always be reported as well.

## Run Gemini

```bash
python benchmark.py --provider gemini
```

## Run OpenAI

```bash
python benchmark.py --provider openai
```

## Compare both

Both API keys must be available in `.env`.

```bash
python benchmark.py --provider both
```

## Fast development run

Run only three scenarios:

```bash
python benchmark.py --provider gemini --limit 3
```

Run only Velachery:

```bash
python benchmark.py --provider gemini --location Velachery
```

Run specific scenarios:

```bash
python benchmark.py --provider gemini --scenario-id VEL-03 --scenario-id TAM-05
```

## Artifacts

By default, every provider run writes:

```text
benchmark_results/
  <provider>_<timestamp>.json
  <provider>_<timestamp>.csv
```

The JSON file retains the validated model output for qualitative inspection. The CSV file is designed for quick comparison and plotting.

These results are ignored by Git by default so that repeated experimental runs do not pollute the repository.

## Interpretation

Do not choose a provider only from composite score.

For CrisisLens, the most important deployment properties are:

1. schema reliability,
2. severity consistency,
3. evidence grounding,
4. low unsupported-claim rate,
5. missing-information honesty,
6. acceptable latency,
7. cost.

A model that writes a better-looking report but fabricates evidence should rank below a less fluent model that stays grounded.
