# CrisisLens faculty demo

## Before presenting

1. Configure one real provider key in the backend `.env` (never in frontend code).
2. Follow the README to install dependencies, build the frontend and start FastAPI.
3. Open `http://127.0.0.1:8000`; check **Backend connected** and **Key configured**.
4. Generate one sample assessment before class to confirm key validity, model access,
   network connectivity and quota. Provider generation has not been verified merely
   because the key indicator is green.

## Show the working flow

1. **Load Velachery.** Explain that the report and measurements are synthetic inputs
   used to exercise the pipeline, not a current Chennai incident.
2. **Inspect context.** Expand measurements and provenance. Distinguish sample water
   level from an official flood observation. The incident timestamp is preserved.
3. **Generate.** The browser sends the input to FastAPI, which runs the existing
   CrisisLens pipeline. The model synthesizes the report and context; Pydantic
   validates the output and locality before the frontend displays it.
4. **Explain the result.** Show the situation report, evidence supporting severity,
   affected groups, proposed resources and advisory response actions. Evidence source
   tags are model-generated categories and require human review.
5. **Show missing evidence.** Select Unknown context. The old result is cleared.
   Regenerate and inspect which unavailable measurements the model identifies. Do
   not promise an exact severity change: different evidence can change its judgment.
6. **Try Chromepet or Tambaram.** Generate a different report to demonstrate fresh
   inference. You can edit the text to describe a milder or more severe situation.
7. **Inspect and export.** Expand the exact input snapshot and download the JSON,
   including model identity and generation time.

## Weather demonstration

Use Fetch weather only when current weather is relevant to the report. It replaces
the environmental context with Open-Meteo gridded/modelled weather and displays
its observation time. This is not an official Chennai station observation and
does not establish the truth of a citizen report. Water level remains unknown.

If retrieval fails, the interface reports the failure and retains the prior,
labelled context. Explicitly choose Unknown or Manual if proceeding.

## What to say about the architecture

“CrisisLens is a Generative AI situation-intelligence pipeline. Deterministic code
collects context before generation. A configurable LLM synthesizes the supplied
evidence into a structured advisory assessment. Humans verify evidence and decide
the response.”

The application does not autonomously contact authorities, dispatch resources or
choose tools. It uses pretrained Gemini/OpenAI models rather than a newly trained
disaster-prediction model. Weather values are inference context, not classifier
training features.

## Honest limitations

- Official Chennai flood-monitor and IMD integrations are still pending.
- Locality grounding is currently a minimal static context layer, not a rich RAG database.
- The 24-scenario benchmark is synthetic, not a validation on real Chennai disaster records.
- Schema validation proves structure, not factual correctness or response suitability.
- This demo has no persistent incident history and requires a working provider connection.

## Next implementation stages

1. Run real provider benchmarks and inspect failures; justify model selection using results.
2. Integrate verified local observations with timestamps, freshness and provenance checks.
3. Add curated Chennai source retrieval without autonomous tool selection.
4. Improve grounding evaluation with human review and adversarial/incomplete reports.
5. Add secured deployment and incident history when the core assessment is reliable.
