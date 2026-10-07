# Past trends: source and interpretation policy

The top Past trends panel is a manually curated educational collection, reviewed on 7 October 2026. It contains qualitative historical cases, not statistical trends, rainfall thresholds, complete coverage or a prediction model. It works without a provider key. Source records are in `frontend/src/data/pastTrends.ts`; the UI is `frontend/src/LearningPanel.tsx`.

## Historical records

The collection covers Velachery, West Tambaram and Chromepet during Cyclone Michaung in December 2023; a regional December 2015 flood-response account; and Equitas Trust's organisation-reported December 2023 relief work. Each reported step links to its original source. Event/publication dates, geographic scope and missing evidence are visible. See the source URLs and dates in the checked-in data file.

Velachery's drainage account describes runoff and submerged pumping equipment, while aftermath reporting describes interrupted essentials. West Tambaram reporting records NDRF rescue and access difficulties. Chromepet reporting records local road waterlogging but does not establish NGO activity there. The regional accounts must not be treated as locality-specific evidence. Equitas's account is self-reported, not independently audited; its listed relief areas do not establish activity in the three pilot areas. The event date is provided, but its publication date is unknown. Its city-wide rainfall figure is not reused as a local measurement.

Reported observations carry original links. Planning lessons are labelled interpretations. Historical reports do not establish present needs, routes or alerts. No archival source is passed into `/api/recommend` as live evidence. Short paraphrases are used rather than copied articles. Review source reuse permissions before expanding production use.

## Rainfall explanation

1 mm rainfall equals 1 litre per square metre; it is rainfall depth, not standing-water depth. Amount divided by duration gives an average rate. The interactive examples are illustrative arithmetic, never live forecasts. Daily averages can hide short bursts.

[IMD's archived bulletin, 21 August 2025, pages 3–4](https://mausam.imd.gov.in/Forecast/mcmarq/mcmarq_data/HEAVY_RAINFALL_BULLETIN1.pdf) supplies daily terminology: very light 0.1–2.4 mm; light 2.5–15.5; moderate 15.6–64.4; heavy 64.5–115.5; very heavy 115.6–204.4; extremely heavy at least 204.5. Values are reported to 0.1 mm. This is an archived Rajasthan bulletin, not a current Chennai warning. Never apply daily categories directly to an hourly forecast.

Categories are not action thresholds. No universal amount determines safety, flood depth or evacuation. Local access, drainage, earlier rainfall, standing water, official instructions and verified requests matter.

## Maintenance and future data

When adding a case, inspect the original source, retain event/publication dates and geographic scope, cite each reported step and list missing measurements. Do not invent incident counts or causal rainfall thresholds. Qualitative sequences do not prove causation.

A quantitative trend feature needs a longitudinal dataset with locality, event timing, rainfall at matched time scales, inundation observations and response outcomes. Coverage checks and evaluation are needed before risk comparisons are justified.
