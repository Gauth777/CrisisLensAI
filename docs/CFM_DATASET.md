# CFM DSS: dataset audit and first historical benchmark

Audit date: 29 October 2026. **Research only; not connected to live assessments.**

## What was actually done

Downloaded two revision-pinned third-party CFM-DSS mirrors: 47 files, including 45 Parquet tables and two README files. Audited every table with zero download/parse failures. Recorded SHA-256 hashes, row counts, missing values, date coverage, selected numeric ranges, locality text matches and transaction duplicate keys. Trained a small random forest on historical Tambaram rainfall and compared it against persistence and a training-only monthly mean.

Sources:

- Official system: https://chennaifloodmonitor.tn.gov.in/
- Sensor mirror: https://huggingface.co/datasets/CashlessConsumer/chennai-flood-monitor-transactions
- Historical layers mirror: https://huggingface.co/datasets/CashlessConsumer/chennai-flood-history
- Exact revisions and filenames: [source manifest](data/cfm_sources.json)
- Measured findings and file hashes: [audit results](data/cfm_audit_2026-10-29.json)
- Measured model results: [benchmark results](data/cfm_benchmark_2026-10-29.json)

These mirrors are not an official training release. Their cards identify unspecified original publisher reuse terms. Do not assume a redistribution licence. Raw data, local examples and model binaries remain in ignored `runtime/cfm/`; only code and aggregate findings are committed. Public availability does not establish permission for operational reuse. No live CFM feed or government endorsement was verified.

## Findings from the downloaded files

| Table | Rows | Recorded date coverage | Important limitation |
|---|---:|---|---|
| SRG rainfall | 662,904 | 1975-12-31 to 2026-02-17 | Not continuous across all stations/years; 111 station identifiers |
| AWS/ARG weather | 669,147 | 2012-09-30 to 2022-09-06 | Only 9 identifiers; 3,033 duplicate station/date/time keys; just 3 rows in 2022 |
| AWLR water levels | 385,950 | 2021-09-05 to 2026-08-16 in `date` | 49 identifiers; 2,330 missing numeric levels; maximum 1,000 requires investigation |
| 2015 NRSC flood extent | 4,001 | Event year from source description | Geometries, not hourly incident labels |
| 2005 IRS flood extent | 235 | Event year from source description | Geometries, not confirmed non-flood examples |
| Ward modelled depths | 200 | All timestamped 2021-08-11 | Must never be displayed as current conditions |
| Crowdsourced reports | 173 | 2022-11-14 to 2025-12-04 | 169 are from 2025; no independent verification established |

The three sensor tables contain **1,718,001 rows** in total. This is not the number of usable flood-training examples.

AWLR timestamp disagreement: 314,222 records have a `combined_datetime` calendar date one day later than their separate `date`; 71,727 agree; one cannot be compared. This is an observed discrepancy, not proof of its cause. Do not silently shift dates or choose a field without documentation. Similarly, decimal-looking times such as `8.3` need a documented convention.

The mirror description suggesting recent AWS/ARG monsoon coverage is contradicted by its downloaded rows. Verify actual observation timestamps independently of capture dates. A null reading remains unknown, never dry weather.

## Coverage of our pilot locations

- **Tambaram:** exact `srgid=Tambaram` gives 11,688 readings, dated 1987-12-31 through 2019-12-30. The historical PWD station registry contains a Tambaram station at 12.935278, 80.126944. This is a candidate name match, not a verified station-history join. A newer registry has “Tambaram Taluk Office”; do not silently merge them.
- **Velachery:** two location-name matches in the 2015 GCC hotspots and a “Velachery Tank” station-registry entry. No Velachery-named transaction series was found. Nearby or differently named sensors require a spatial/catchment join.
- **Chromepet/Chrompet:** no matching transaction station name. Absence of a text match does not prove absence of sensor coverage. Geographic coverage remains unresolved.

Text hits in district names or escape-route descriptions are not site-specific evidence. Proposed station lists must not count as active measurements.

## Historical benchmark: measured, not claimed flood accuracy

Target: **next recorded Tambaram rainfall value**, in the source's numeric units. Rainfall interval/unit and date conventions are not independently established, so results are not advertised as physical forecasting accuracy.

Inputs: seven preceding daily-indexed readings plus calendar-month sine/cosine. Missing dates/readings remain missing; examples crossing them are discarded. Negative readings are excluded. Duplicate or unparseable Tambaram dates fail the benchmark. No flood labels, risk thresholds, assistance needs or synthetic training rows are invented.

Chronological partitions use the **target date**:

- Train: 1988-01-07 to 2013-12-31 — 9,491 examples.
- Validation: 2014–2016 — 1,096 examples.
- Test: 2017-01-01 to 2019-12-30 — 1,094 examples.

Fixed random forest: 100 trees, depth 8, minimum leaf size 20, seed 42. No hyperparameter search. Monthly baseline uses training data only. Earlier observations from a preceding partition may inform the next day's prediction, as in a rolling one-step forecast; future targets never enter features.

| Test model | MAE, source units | RMSE, source units |
|---|---:|---:|
| Repeat previous reading | 3.9921 | 13.4291 |
| Training monthly mean | 4.9247 | 11.1636 |
| Random forest | 4.0181 | 10.3718 |

The forest improves RMSE but is slightly worse than persistence on MAE. These mixed results do **not** establish operational benefit, flood-detection accuracy or better GenAI recommendations. Flood accuracy is explicitly null and promotion is disabled. No uncertainty intervals or independent physical ground-truth validation have been performed.

## Reproduce on Windows

From the repository root, no PowerShell activation is required:

```powershell
git pull origin main
.\.venv\Scripts\python.exe -m pip install -r requirements-data.txt
.\.venv\Scripts\python.exe scripts/audit_cfm.py
.\.venv\Scripts\python.exe scripts/benchmark_cfm.py
.\.venv\Scripts\python.exe -m unittest discover -s tests/data -v
```

The downloader uses fixed repository revisions, four workers, timeouts/retries, and atomic writes. Subsequent runs reuse local files. To recheck downloaded files without network: `python scripts/audit_cfm.py --offline`. The recorded hashes allow comparison against this audit; locally modified cache files must be investigated or deleted and fetched again.

Outputs in `runtime/cfm/`: raw source files, `audit.json`, compact `findings.json`, and `benchmark/` with chronological examples, validation/test predictions, `metrics.json`, and a research-only model binary. Model binaries are not loaded by the web app. Install optional dependencies only for this offline work; ordinary site startup is unchanged.

## What must happen before flood-model training or live integration

1. Obtain the publisher's measurement definitions: rainfall accumulation interval/units, sensor datum, station history, timezone/date conventions, quality flags and permitted reuse.
2. Validate spatial/catchment mappings for the three pilot areas; distinguish proposed, installed and actually reporting sensors.
3. Assemble independently reviewed event labels with locality, onset/end, observed depth or confirmed waterlogging, source, verification status and observation coverage. A missing incident report is not a negative label. Historical extent polygons are not hourly outcomes.
4. Join only observations available before each prediction time. Hold out entire storms and locations, with a temporal buffer for overlapping windows. Compare against simple baselines; measure event recall, false alarms, lead time and calibration.
5. Keep GenAI central: retrieve dated, relevant observations/history and generate concise explanations, contradictions and information gaps. A supporting risk model may supply evidence after validation. It must not infer supply quantities or replace reviewed assistance requests. This remains non-agentic.

Until these gates are met, historical layers can support explicitly dated historical context; they cannot establish a current emergency. This audit and benchmark are completed. A validated flood classifier and live CFM integration are not.

## Follow-up evidence pack (30 October 2026)

See [the station and incident evidence pack](../research/cfm/README.md) for a self-contained interactive coverage atlas, six sourced historical cases, preserved reporting conflicts, a sensor/event availability check and a human-review sheet. This follow-up does not remove the modelling or reuse limitations above.
