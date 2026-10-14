# CrisisLens faculty demonstration

For a reliable fictional walkthrough, start with **Try a simulation** and follow [the five-minute Field Lab demonstration](SIMULATION.md). It uses isolated training records and needs no AI key. Do not submit made-up demonstrations into the live report database.

For the separate live-source demonstration, follow [the current NGO workflow](NGO_WORKFLOW.md):

1. Open the home page. Choose an area and actual available resources. Explain that the map marks locality centres, not individual incidents or flood probabilities.
2. Show the live weather source time and source-health panel. Open an actual retrieved CAP warning if available. If none matches, say so; do not present a historical warning as current.
3. Open an actual local report and inspect its observation, time, needs and review trail. If no genuine report exists, explain that this source requires reporting participants. Use Field Lab for fictional examples; do not corroborate fictional data as real evidence.
4. Prepare a plan from an eligible real report, or use a preparedness draft. Show resources, concise generated steps and exact supporting records. If generation is unavailable, save a manual draft.
5. Open My plans, reload the page and reopen the persisted draft. Show the checks needed for approval and that approval requires the coordinator token and a current reviewed request. Preparedness drafts cannot be approved as incident responses.
6. Download the briefing. Explain that the server stores the exact evidence bundle; exporting or approving a plan does not dispatch anyone.
7. Demonstrate a pending report update and review history. Explain that reported resolution does not overwrite the original request until a coordinator checks it.
8. Open Past trends and Rain guide. Historical context and daily rainfall categories are not current incident evidence or evacuation thresholds.

Architecture: React/TypeScript + Leaflet → FastAPI → bounded deterministic source retrieval and SQLite records → interchangeable LLM provider for structured recommendations → schema/citation/type checks → human decisions. The model does not choose tools, fetch its own URLs, contact authorities or dispatch resources; the workflow remains non-agentic.

Be accurate about validation: offline backend tests check state transitions and evidence eligibility; browser tests exercise real persistence using synthetic sources/models in an isolated test server. Live source connectivity is a separate check. Citation validation does not prove semantic correctness, and human-reviewed reports are not independent certification.

Next work: individual NGO identities/permissions, real reporting partners, authorized local sensor/road/shelter feeds, measured source latency, and evaluation of claims against independently reviewed incidents. Public deployment also requires abuse controls, retention/privacy policies and source-reuse review.
