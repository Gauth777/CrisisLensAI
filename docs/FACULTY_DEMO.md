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

## Troubleshooting generation

For new Gemini projects set `GEMINI_MODEL=gemini-3.5-flash-lite` in `.env`.
Gemini 2.5 access is restricted to previous users according to Google's model
documentation; it is not a reliable default for a newly created key/project.
Changing `.env.example` or pulling new code does **not** overwrite your local `.env`.
Restart the backend after editing it. Existing shell environment variables take
precedence over `.env`; verify the model shown in the workspace after restart.

The UI now distinguishes authentication, permission, model access, quota,
billing, request rejection, timeout and connectivity failures. The backend logs
`CrisisLens failure: provider=... category=... upstream_status=...` without the
key, report, provider response body or raw traceback. Share that safe line when
asking for help. An HTTP 429 can mean a rate limit or exhausted/unavailable model
quota, not necessarily a bad key.

References: https://ai.google.dev/gemini-api/docs/deprecations and
https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite.

For OpenAI, a 429 is not always temporary throttling. The safe diagnostic now
includes a documented `provider_code` when available. `insufficient_quota`,
`credit_balance_exhausted` and organization/project spend or usage limit codes
require reviewing the API account's credits or limits. `rate_limit_exceeded`
and `slow_down` indicate throttling. ChatGPT subscriptions are billed separately
and do not provide the API credit balance used by this application.

Check the organization/project associated with your key in API Billing and
Limits: https://platform.openai.com/account/billing/overview and
https://platform.openai.com/settings/organization/limits.
Reference: https://developers.openai.com/api/docs/guides/error-codes.

## Next implementation stages

1. Run real provider benchmarks and inspect failures; justify model selection using results.
2. Integrate verified local observations with timestamps, freshness and provenance checks.
3. Add curated Chennai source retrieval without autonomous tool selection.
4. Improve grounding evaluation with human review and adversarial/incomplete reports.
5. Add secured deployment and incident history when the core assessment is reliable.
