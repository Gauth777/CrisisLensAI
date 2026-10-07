# CrisisLens faculty demo

## Prepare before class

1. Pull main, install dependencies, build the frontend and restart FastAPI (README commands).
2. Keep your existing Groq key in backend `.env`: `CRISISLENS_PROVIDER=groq` and `GROQ_MODEL=openai/gpt-oss-120b`. Keys never belong in frontend code.
3. Open http://127.0.0.1:8000. The Chennai pilot menu shows provider configuration; a configured key does not prove quota or connectivity.
4. Generate a real recommendation before class. Weather and publisher feeds also need internet access. Source failures are displayed, with no invented replacements.
5. If generation fails, run `python -m crisislens.doctor --provider groq --env-file-only` and share only its safe output. The doctor exercises the legacy assessment pipeline; also test the new recommendation flow in the browser.

## Demonstrate direct alerts and reports first

1. Select a pilot area on the map and open **On the ground**. Alerts load without clicking Get recommendations and without a model key. First intake may take a minute or more while CAP documents download; failures stay visible. Show source, issue time, expiry, district scope and **Why? Read the official warning**.
2. If no warning matches, explain the coverage gap; do not manufacture a warning. A district forecast warning is not evidence of flooded streets. News is secondary context.
3. To demonstrate the report workflow, explicitly tell faculty the example is fictional. Submit a report beginning **DEMO ONLY — fictional observation**, with a current time and a landmark, and show its **Unreviewed** label. Do not present a demo as a real disaster.
4. Optional coordinator review: set a private `CRISISLENS_REVIEW_TOKEN` in backend `.env` before startup. A real report must be checked through actual on-site observation, a contact or an official reference before marking it reviewed. Record the check method and note. For the fictional demo, demonstrate **Rejected — not corroborated**, with a note explaining that it was synthetic, rather than falsely corroborating it.
5. Show the review trail and explain that recent reviewed reports may enter AI recommendations, while unreviewed, old, rejected or resolved reports cannot. The shared token is a demo access mechanism, not verified individual identity.

## Present the new NGO workflow

1. **Choose an area.** Velachery, Tambaram and Chromepet are the current pilot. Drag the Chennai map, zoom, and select a pilot marker. Live weather shows modelled conditions; Past flooding shows documented historical cases. Current incident risk remains unverified. These markers are representative points, not street-level incident coordinates.
2. **Open Past trends.** Explore a locality-specific 2023 case and regional relief accounts, then switch to Rain guide. Compare 4 mm over 24 hours with 4 mm in one hour. IMD daily rainfall categories describe amounts, not deployment or evacuation thresholds. Explain that the history is manually curated, not a statistical trend database. Close the panel with Escape.
3. **Inspect local context.** Show modelled temperature, wind and the next forecast rain window. Forecast rainfall covers the hour preceding its timestamp. Missing forecast values stay unknown. Open the weather source to see its values, time and original API URL.
4. **Inspect reports.** Recent matching publisher-feed reports include publication times and original links. Distinguish locality mentions from Chennai-wide context. An unavailable feed or no matching report does not prove that an incident is false.
5. **Ask a useful question.** Click Plan supplies: “Our NGO has 50 food kits and 6 volunteers available for Velachery. What needs can be established, and what should we prepare before deciding where to help?” Click Get recommendations.
6. **Explore the answer.** Open Why this recommendation, then Evidence. Sources shown belong to that specific recommendation. An uncited preparedness suggestion has no supporting source attached. The Unknowns tab lists checks needed before action.
7. **Inspect claims and people.** Click a claim, an affected group or a suggested supply. User reports remain unverified; weather alone cannot establish flooding, stranded residents, supply demand or safe roads. “Not enough evidence” is a legitimate result, not a declaration that the report is false.
8. **Save the briefing.** Download JSON containing the question, recommendation, source records and generation metadata. Editing the question clears the previous answer.
9. **Optional synthetic demonstration.** Try a hypothetical scenario. Its answer excludes live weather and news and is labelled synthetic. The home context cards remain separate live context; do not present the hypothetical incident as current news.

## Explain the architecture

“CrisisLens helps NGOs ask a question and inspect recommendations alongside their sources. A background deterministic worker ingests SACHET warnings independently of the model; volunteers submit timestamped observations and coordinators record checks. Deterministic code combines current official warnings, recent reviewed field reports, weather and secondary publisher context before the model runs. The model produces structured recommendations. The backend validates the schema, locality and citation IDs, and prevents weather or an unverified user report from independently supporting operational incident claims. Humans review the sources and decide what to do.”

The recommendation route is `/api/recommend`; context is `/api/context/{location}`. The previous `/api/analyse` assessment route and synthetic benchmark remain available. Providers share one interface and can accept either output schema. Groq hosts the GPT-OSS model using a Groq key; it does not use OpenAI API credits.

## Describe limitations honestly

- Weather is a gridded model product, not a street-level flood sensor. No official local water-level, road-access or shelter-capacity integration is connected.
- News covers bounded excerpts from two Chennai publisher feeds, filtered to hazard-related reports from the past seven days. It is limited coverage, not a complete or independently verified emergency feed. The publication date may differ from the event date.
- Context is cached for five minutes; Refresh context requests a fresh retrieval. Each briefing retains the exact records supplied during its generation.
- Citation validation proves that a referenced record exists, not that the model's interpretation is correct. Supported/contradicted labels remain source-linked interpretations for review.
- Suggestions are not confirmed supply requests. No dispatch, authority contact, route guarantee, automated decision is provided. Local report and review history persists in SQLite.
- This is a localhost academic pilot, not a validated operational emergency service. Publisher reuse/licensing and official source access must be resolved before production use. Indian Express RSS terms specify personal, non-commercial use: https://indianexpress.com/rss/.
- Browser tests use labelled fixtures; passing tests does not prove live provider or publisher availability. The existing benchmark is synthetic, not real-disaster accuracy validation.

## Next implementation stages

1. Connect authorized rain-gauge, water-level, road-access and shelter feeds; validate measured ingestion latency and coverage. Expand beyond the current SACHET district-warning and local field-report intake.
2. Evaluate claim support and recommendation usefulness against human-reviewed real cases; measure unsupported claims, freshness and locality relevance.
3. Expand area search, show geographic coverage and deduplicate event reports once reliable sources are available.
4. Add verified needs, shelter capacity and resource matching; retain human approval before dispatch.
5. Replace the demo shared review token with individual NGO accounts and roles; add submission rate limits, retention rules and operational monitoring.
