# CrisisLens NGO workflow

This interface uses live upstream retrieval and reports submitted to the running server. It does not populate the production database with example incidents, requests, people counts or plans.

## Start the application on Windows

From the project root, with your virtual environment active:

```powershell
git pull origin main
python -m pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. Keep your existing provider configuration in backend `.env`. Official warnings, weather, reports and manual plans do not require an LLM key. AI recommendations use the configured provider (Groq is supported); no API key is sent to the browser.

To enable coordinator review and approval, set `CRISISLENS_REVIEW_TOKEN` to a private random value in backend `.env` and restart. Enter this token only in the review/approval form. This shared credential is for a trusted local workspace; there are no individually authenticated NGO accounts.

## 1. Find needs

Choose Velachery, Tambaram or Chromepet. Enter actual resources and volunteer availability. Quantities have explicit units: food kits, water litres, medical kits, shelter places and other supply items. Leave unknown quantities blank. **Find relevant needs** scrolls to local reports and filters by the supplied resource types.

- **All open reports:** includes unreviewed and stale reports, labelled accordingly.
- **Reviewed:** recent coordinator-reviewed records with no pending updates.
- **Fits my supplies:** matches explicitly recorded resource categories, not a semantic promise that the NGO can fulfil the request. Text-only needs may require checking All open reports.
- **Resolved / rejected:** retains visible report history from the current seven-day snapshot.

The movable OpenStreetMap map marks representative locality centres, with reviewed-request counts. It does not locate individual streets, predict floods or certify a safe route. Map tiles require internet access.

Weather shows the live retrieved Open-Meteo gridded forecast, its source time and next forecast rain window. News remains secondary context. No retrieved report does not mean no incident.

## 2. Check evidence

Each local report opens its observation, timestamp, reported needs, human checks and update trail. No review is automatically inferred from a submission. **Report an observation** records real observations; avoid private contact details and personal medical information.

Official warnings open separately with issuer, certainty, severity, issue/expiry times, geographic scope and the original CAP document. District warnings do not establish street flooding, stranded people or supplies required.

**Sources & freshness** shows the latest SACHET index fetch, last complete check, checked/failed document counts, failed source links and error categories. A partial check preserves readable successful records with coverage warnings. It does not imply a failed document is irrelevant: an update or cancellation might be missing. Incomplete/stale warning coverage is excluded from AI confirmation; recent reviewed field reports and weather remain independently usable.

## 3. Prepare a plan

Open a report and select **Prepare a plan**, or start a preparedness draft without a report. Enter available supplies, volunteers and notes. **Generate evidence-based steps** requests concise actions from the configured model, using retrieved sources and the selected report if eligible. Open each action's evidence. Editing resources or notes clears the old generation.

**Save draft plan** stores resources, the report revision, notes and the exact generated briefing/source bundle, if one was generated. It does not send messages, reserve stock externally or dispatch people. Manual drafts remain usable when AI is unavailable. Briefings generated for different resources or an older report revision cannot be attached to a new draft.

## 4. Review and approve

Open **My plans** to resume saved drafts, even after reloading or restarting the server. Check the contact/demand, current access and receiving time. To approve, record the coordinator, check note and private token.

The server rejects approval when checks are incomplete; no current reviewed request is attached; the source changed, is over six hours old or has pending updates; or there are no recorded team resources. Preparedness-only drafts cannot be approved as incident responses. Approved plans are immutable; close them and create a fresh draft if circumstances change. A later source change is flagged on saved plans.

**Download briefing** exports a text briefing and the full stored JSON evidence/history. Share the downloaded file through your own channels. The app does not automatically contact anyone. **Close plan** records closure with a coordinator token; it does not resolve the underlying request.

## 5. Update the outcome

From the report, select **Submit an update** and choose Still needed, Partly fulfilled or Resolved. Supply the new observation time, what changed and the remaining needs/quantities. Updates are pending until a coordinator corroborates or rejects them. Pending updates prevent the old report from silently supporting new AI confirmation or plan approval.

An accepted update changes the report and preserves its review history. Rejected updates leave the previous observation and status intact. A resolved update must receive a resolved review outcome. No update is interpreted as proof that aid was actually delivered without human review.

## Persistence and operations

Existing databases are extended with new tables; previous records are not reset. Data remains in ignored `runtime/operations.sqlite3` unless `CRISISLENS_DB_PATH` is set. Reports/updates/plans are shared by users of this one server. No cross-server NGO federation is implemented.

SACHET polling runs in a background thread, with two minutes between completed passes. Initial ingestion can take several minutes; immutable CAP documents are cached. The browser polls operations and plans every 20 seconds, and weather/news every five minutes. Manual Refresh forces context retrieval. Set `CRISISLENS_ALERT_POLLING=0` only to intentionally disable intake.

Before public deployment, individual identities, permissions, submission rate limits, data retention and operational monitoring are required. The current system is an academic/trusted-workspace prototype, not an independently validated emergency service. There are no connected street sensors, shelter-capacity feeds or guaranteed access routes.

## Validation

`python -m pytest -q` uses isolated temporary databases and disables upstream polling. Browser tests use a real FastAPI/SQLite server on port 8011, with explicitly synthetic source/model fixtures defined only in `tests/browser_server.py`. The development test proxy is selected by `CRISISLENS_TEST_API_ORIGIN`; ordinary Vite development still targets port 8000.

```powershell
cd frontend
npm run build
npx playwright install chromium
npm run test:e2e
```

Tests cover report submission/review, incorrect tokens, real persistence, generated evidence attachment, approval, exports, pending updates, resolution, mobile layout, past trends and missing-source states. Passing fixtures do not prove live provider accuracy. Live external retrieval is checked separately.
