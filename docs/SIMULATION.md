# CrisisLens Field Lab (V0.8)

Purpose: practise deciding where an NGO can help, what evidence supports the decision, and when a changing situation requires a new plan.

Open **Try a simulation** in the live header, or go to `http://127.0.0.1:8000/#simulation`. Choose a story. No model key, live source feed or map tile download is needed by the simulation. The backend must be running.

## Six fictional stories

| Scenario | Area | Decision to practise |
|---|---|---|
| Rain is not a rescue call | Chromepet | A 4 mm/hour forecast and an uncorroborated message do not establish assistance demand. The message is rejected after a scripted site check. |
| From report to response | Velachery | Review a water request, prepare a plan, then reassess when access changes and another simulated team supplies part of the need. |
| Every decision matters | Tambaram | Keep a trained rescue request visible while planning NGO supply support within the team's capability. |
| Three areas. One team. | All three | Compare water, food and medical-kit requests. Resolving the primary request does not resolve the other areas. |

All observations, quantities, weather, checks and outcomes are fictional. They do not describe current or historical conditions. The schematic is a locality illustration, not a route or flood-risk map.

Two additional exercises are **The stories don’t agree** (conflicting access and quantities) and **Help needed. How much?** (corroborated need with missing quantities). See [the evaluator walkthrough](INTELLIGENCE_VALIDATION.md).

## Five-minute demonstration

1. Choose **From report to response**. Explain the purpose and simulation banner. The initial forecast does not create a local request.
2. Select **Next event**. Open **Why? Check the evidence** on the unreviewed report. You can save a draft, but approval is blocked.
3. Select **Next event** again. A scripted coordinator check now corroborates the training request. Compare 120 litres requested with the editable starting inventory of 80 litres. The difference is not a delivery or allocation.
4. Open the evidence panel and save a fresh practice draft. Under **Your practice plans**, open it, tick the three training checks and choose **Approve practice response**. Record the practice decision. The same server-side plan rules used in live mode apply, but no live coordinator token is required in this isolated training workspace.
5. Select **Next event**. An access update is pending review. The existing plan is flagged as changed; an old draft cannot be approved. Open the report to show the update trail.
6. Advance to **Recheck**. Scripted checks accept changed access and partial fulfilment. The remaining water request becomes 80 litres. Create a fresh draft from the updated request if desired.
7. Advance to **Outcome**. Show the recorded plans and remaining requests. The scripted resolution is not attributed to the user's practice plan. Export a briefing with an explicit SIMULATION label.
8. Reset to repeat or return to the live workspace. Live requests and plans remain unchanged.

The three-area story leaves Tambaram and Chromepet open at the end. The low-rain story rejects the unsupported message; preparedness drafts remain ineligible for incident-response approval.

## What is real, what is scripted

- Real application behaviour: SQLite persistence, report revisions, review history, pending updates, draft saving, approval checks, stale-plan detection, downloads, reset and session resume.
- Scripted: weather, field observations, coordinator checks, partial fulfilment, outcome events, and example briefing text. No model calls occur in Field Lab. Live mode still uses the configured provider for AI recommendations.
- Decisions: the user changes inventory, chooses a request, records checks and saves/approves practice plans. Multiple plans do not reserve or deduct shared stock; the UI states this limitation.
- Motion: animated cards, event transitions, evidence drawers, schematic markers and supply bars. Events advance manually. Reduced-motion preferences disable animations.

## Isolation and persistence

The new routes are under `/api/simulations`. Each UUID session owns a separate SQLite file under ignored `runtime/simulations/`, configurable with `CRISISLENS_SIM_DB_DIR`. Sessions never use `api.operations()` or a live report/briefing. Cross-session and live report IDs cannot be attached to a simulation plan.

The browser remembers the session ID, so refreshing resumes its reports, stage and plans. Unsaved inventory edits are not persisted. A session expires after four hours, before the normal six-hour freshness limit. Old UUID-named files older than a day are cleaned when a new session starts. Reset deletes only that session's reports, reviews, updates, plans and briefings. Separate users should start separate scenarios; sharing a session URL/id shares its practice state. This remains a trusted-workspace prototype, not a public multi-tenant service.

## Tests

`python -m pytest -q` checks scenario progression, report/plan guards, reset, concurrent revision checks, session boundaries and live-data isolation. Browser tests in `frontend/tests/simulation.spec.ts` cover waterlogging, rain without demand, multi-area mobile use, persistence, approval, source changes, reset and labelled exports. The urgent standalone story also uses the same tested primary-report update sequence as the waterlogging story.
