# CrisisLens environmental data strategy

CrisisLens separates **data acquisition** from **Generative AI reasoning**. Weather and flood measurements are supplied to the LLM as grounding context at inference time; they are not treated as labels for a conventional ML classifier.

## Source precedence

### 1. Chennai Flood Monitor / RTFF & SDSS

Preferred Chennai-specific source for the final prototype.

The public Chennai Flood Monitor describes an operational network containing Automatic Rain Gauges, Automatic Weather Stations, and Automatic Water Level Recorders. Its AWS layer includes variables relevant to CrisisLens such as temperature, relative humidity, wind speed and wind direction.

**Planned use:** official/local rainfall, AWS observations and water-level context where machine-readable access can be integrated reliably.

**Current status:** public dashboard identified; stable machine-readable endpoint still needs verification before it is wired into production code.

### 2. India Meteorological Department AWS/ARG

IMD publishes API documentation for AWS/ARG observations. The documented API supports station-level and state-level weather observations, including temperature, relative humidity, wind direction and wind speed.

The IMD documentation also states that API consumers must provide a public IP for whitelisting.

**Planned use:** official observation fallback/validation once project hosting has a stable public IP.

### 3. Open-Meteo

Used only as a development fallback so the pipeline can already be exercised with live numerical weather context.

The public forecast endpoint supports coordinate-based JSON weather data including precipitation, temperature, relative humidity, wind speed and wind direction.

**Important:** this is gridded/modelled weather context, not a Chennai government station observation. CrisisLens carries source provenance into the prompt so the LLM does not silently treat it as official station data.

## Pilot locality coordinates

Representative coordinates are used only to query gridded weather for the locality:

- Tambaram: 12.9300, 80.1100
- Chromepet: 12.9516, 80.1401
- Velachery: 12.9807, 80.2189

These coordinates are not incident coordinates and should not be presented as such.

## Water level

Open-Meteo weather data does not provide the Chennai local flood/water-level measurement needed by CrisisLens. Therefore water_level_m remains null unless an official/local source supplies it.

This is deliberate: **missing evidence is preferable to fabricated evidence.**

## Production principle

Final source order:

1. official Chennai local observation,
2. official IMD observation,
3. gridded weather fallback,
4. otherwise UNKNOWN.

The LLM never selects or calls these sources itself. A deterministic application layer acquires the context first and then passes it to the model. This preserves the non-agentic architecture required by the project.
