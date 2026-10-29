# Chennai evidence pack — 30 October 2026

Completed: a reproducible station-candidate map, six source-checked historical locality cases, an availability join audit, a measurement-definition checklist and a blank human-review sheet. **This is a research seed, not a training-ready flood dataset or a live feed.**

## Open the evidence atlas

After pulling the repository, double-click `research/cfm/generated/coverage_map.html`. It works offline and has locality tabs, station-family filters, clickable station details and expandable incident evidence. Source links and the optional OpenStreetMap link require internet. The geographic plot has no street basemap, risk colouring or sensor-coverage polygons.

```powershell
git pull origin main
Start-Process .\research\cfm\generated\coverage_map.html
```

## What the station mapping establishes

Four selected registries were checked against the pinned historical transaction files. Exact matching uses the source keys without fuzzy aliases or guessed transformations. Duplicate registry keys are withheld from joins. Proposed registries are excluded.

| Registry | Entries with valid coordinates | Exact historical transaction-key matches |
|---|---:|---:|
| PWD SRG existing stations | 53 | 49 |
| AWS registry 39 | 39 | 0 |
| AWLR registry 44 | 44 | 42 |
| AWLR stations 121 | 121 | Not joined; registry context only |

These are counts **per registry**, not unique physical sensors or current reporting sensors. Names, coordinates and installation history need reconciliation before a candidate is accepted as a measurement source for a locality. Zero exact AWS matches does not prove no data: for example, registry and transaction names use different formats. No fuzzy matching is promoted as verified identity.

Nearest examples, measured from the app's representative locality centres:

| Locality | Candidate | Distance | Historical match |
|---|---|---:|---|
| Tambaram | Tambaram SRG | 1.93 km | 11,688 records, ending 2019-12-30 |
| Chromepet | Tambaram SRG | 2.31 km | Same historical series; not a verified Chromepet proxy |
| Velachery | Velachery Tank registry entry | 0.73 km | No transaction join established |
| Velachery | Veerangal Odai near Puzhuthivakkam MRTS AWLR | 1.53 km | 4,446 records, 2025-04-02 to 2026-02-27 in source `date` |

The map displays 90 registry entries within 15 km of at least one pilot centre; that radius is only a display filter. Distances are haversine distances, not route distances or hydrological connectivity. Water-level date spans inherit the unresolved timestamp issue in the original audit.

## Historical cases and evidence standard

[incidents.json](incidents.json) contains six cases representing **four storm/event groups**:

- Tambaram and Velachery, December 2015: Army operating areas explicitly named in PIB Ministry of Defence releases. Regional rescue totals are not assigned to a locality.
- Chromepet Government Hospital, November 2021: two press reports agree on campus waterlogging but differ over flooded wards and transfers. Both accounts remain recorded; no transfer number is accepted as verified ground truth.
- Tambaram and Velachery, December 2023: published reports name inundated localities; Tambaram has a more specific account covering CTO Colony and Krishna Nagar. City-wide rescued demographics are not assigned to these locations.
- Chromepet Government Hospital, November 2024: two reports support flooding but describe relocation differently. One discusses patients moving after inundation; another quotes the dean on earlier relocation of essential services. This may be compatible, but the timeline is not resolved.

All linked pages were inspected by the assistant on 30 October 2026. This is **source checking**, not independent field verification or human adjudication. Each source has a URL, publisher, publication date, evidence locator, paraphrased support and origin group. No articles, photos or contact information are republished. Sources from the same storm remain in one event group; syndicated copies must not be treated as independent votes.

Every case retains unknown onset/end, null supervised label and `training_eligible=false`. The dataset contains **zero confirmed negative examples**. An absent news article or missing sensor measurement cannot establish a non-flood observation.

## Does the sensor data line up?

The availability check uses the seven calendar days preceding each reported observation day, excluding that day. **That day is not a known flood onset**, so these windows are not permitted predictive features.

Only the Tambaram 2015 case has seven matching readings in the exact locality-named SRG series. The same series ends before 2023. No exact locality-named SRG series is present for Velachery or Chromepet. Nearest-station substitution is intentionally not performed. These findings are in [incident_join_audit.json](generated/incident_join_audit.json).

## Measurement definitions: what remains unresolved

[measurement_contract.json](measurement_contract.json) records field-by-field findings and links. CFM's public interface displays rainfall units, but that does not establish raw-table accumulation/reset intervals. AWLR sensor datum and the one-day timestamp discrepancy remain unresolved. Neither water-level values nor lake levels can be interpreted as street flood depth without a validated datum and ground-elevation relationship.

An official alternative exists on the National Water Data Portal: Tamil Nadu manual daily rainfall is described as daily measurements in millimetres; river levels are described in metres. This step checked those metadata pages only. It did not download their records or establish a CFM station crosswalk. Their definitions must not be copied onto the CFM fields by assumption.

To resolve these blockers, obtain a data dictionary and station crosswalk from the data owner, including measurement interval, timezone, date-assignment convention, missing/sentinel flags, calibration/datum, station relocations and permitted reuse. No request has been sent on the user's behalf.

## Human review and the next modelling gate

Use [human_review_template.csv](generated/human_review_template.csv) to record reviewer, date, onset/end, adjudication and evidence notes. Obtain hospital/municipal/response logs where press accounts disagree. Add documented non-flood periods with explicit observation coverage. A completed review sheet does not automatically make a row eligible; the catalogue's labels need an explicit reviewed revision.

Keep future train/test splits separated by whole storm groups and locations, with buffers for overlapping sensor windows. Do not train a flood classifier on six positive-only source accounts. For GenAI evaluation, these cases already support testing whether the system cites the right scope, preserves conflicts and avoids invented assistance quantities; they do not measure numerical flood prediction accuracy.

## Reproduce and check

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-data.txt
.\.venv\Scripts\python.exe scripts/audit_cfm.py
.\.venv\Scripts\python.exe scripts/build_cfm_evidence.py
.\.venv\Scripts\python.exe -m unittest discover -s tests/data -v
```

The builder is offline after the audit downloads. It records input hashes and generates aggregate coverage, the HTML atlas and join diagnostics. It does not overwrite an existing human-review sheet. Raw datasets remain under ignored `runtime/cfm/`; source reuse terms remain unresolved. The committed outputs include selected station-coordinate facts and aggregate counts, not the full original tables.

Verification: 11 data tests passed. A Chromium smoke check passed locality selection, evidence expansion, station detail display, family filtering and mobile overflow checks; no JavaScript errors. The website/backend was not modified.
