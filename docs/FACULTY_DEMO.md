# CrisisLens faculty demo

## Prepare before class

1. Pull main, install dependencies, build the frontend and restart FastAPI (README commands).
2. Keep your existing Groq key in backend `.env`: `CRISISLENS_PROVIDER=groq` and `GROQ_MODEL=openai/gpt-oss-120b`. Keys never belong in frontend code.
3. Open http://127.0.0.1:8000. The Chennai pilot menu shows provider configuration; a configured key does not prove quota or connectivity.
4. Generate a real recommendation before class. Weather and publisher feeds also need internet access. Source failures are displayed, with no invented replacements.
5. If generation fails, run `python -m crisislens.doctor --provider groq --env-file-only` and share only its safe output. The doctor exercises the legacy assessment pipeline; also test the new recommendation flow in the browser.

## Present the new NGO workflow

1. **Choose an area.** Velachery, Tambaram and Chromepet are the current pilot. Explain that the hero map is an illustration, not a live incident map.
2. **Inspect local context.** Show modelled temperature, wind and the next forecast rain window. Forecast rainfall covers the hour preceding its timestamp. Missing forecast values stay unknown. Open the weather source to see its values, time and original API URL.
3. **Inspect reports.** Recent matching publisher-feed reports include publication times and original links. Distinguish locality mentions from Chennai-wide context. An unavailable feed or no matching report does not prove that an incident is false.
4. **Ask a useful question.** Click Plan supplies: “Our NGO has 50 food kits and 6 volunteers available for Velachery. What needs can be established, and what should we prepare before deciding where to help?” Click Get recommendations.
5. **Explore the answer.** Open Why this recommendation, then Evidence. Sources shown belong to that specific recommendation. An uncited preparedness suggestion has no supporting source attached. The Unknowns tab lists checks needed before action.
6. **Inspect claims and people.** Click a claim, an affected group or a suggested supply. User reports remain unverified; weather alone cannot establish flooding, stranded residents, supply demand or safe roads. “Not enough evidence” is a legitimate result, not a declaration that the report is false.
7. **Save the briefing.** Download JSON containing the question, recommendation, source records and generation metadata. Editing the question clears the previous answer.
8. **Optional synthetic demonstration.** Try a hypothetical scenario. Its answer excludes live weather and news and is labelled synthetic. The home context cards remain separate live context; do not present the hypothetical incident as current news.

## Explain the architecture

“CrisisLens helps NGOs ask a question and inspect recommendations alongside their sources. Deterministic code retrieves weather and publisher-feed context before the model runs. The model produces structured recommendations. The backend validates the schema, locality and citation IDs, and prevents weather or an unverified user report from independently supporting operational incident claims. Humans review the sources and decide what to do.”

The recommendation route is `/api/recommend`; context is `/api/context/{location}`. The previous `/api/analyse` assessment route and synthetic benchmark remain available. Providers share one interface and can accept either output schema. Groq hosts the GPT-OSS model using a Groq key; it does not use OpenAI API credits.

## Describe limitations honestly

- Weather is a gridded model product, not a street-level flood sensor. No official local water-level, road-access or shelter-capacity integration is connected.
- News covers bounded excerpts from two Chennai publisher feeds, filtered to hazard-related reports from the past seven days. It is limited coverage, not a complete or independently verified emergency feed. The publication date may differ from the event date.
- Context is cached for five minutes; Refresh context requests a fresh retrieval. Each briefing retains the exact records supplied during its generation.
- Citation validation proves that a referenced record exists, not that the model's interpretation is correct. Supported/contradicted labels remain source-linked interpretations for review.
- Suggestions are not confirmed supply requests. No dispatch, authority contact, route guarantee, automated decision or persistent incident history is provided.
- This is a localhost academic pilot, not a validated operational emergency service. Publisher reuse/licensing and official source access must be resolved before production use. Indian Express RSS terms specify personal, non-commercial use: https://indianexpress.com/rss/.
- Browser tests use labelled fixtures; passing tests does not prove live provider or publisher availability. The existing benchmark is synthetic, not real-disaster accuracy validation.

## Next implementation stages

1. Add timestamped official alerts, local observations and verified NGO field reports, with source access and reuse permission.
2. Evaluate claim support and recommendation usefulness against human-reviewed real cases; measure unsupported claims, freshness and locality relevance.
3. Expand area search, show geographic coverage and deduplicate event reports once reliable sources are available.
4. Add verified needs, shelter capacity and resource matching; retain human approval before dispatch.
5. Add access control, history, rate limits and operational monitoring for deployment.
