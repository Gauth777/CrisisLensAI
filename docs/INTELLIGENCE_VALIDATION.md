# Intelligence validation and evaluator walkthrough

## What changed

The live report form records access (unknown/passable/blocked) and demand (unknown/needed/not needed). These are reported observations, not automatic certification. Existing reports default to unknown.

Recent open reports at the same normalized landmark and locality are compared for access, demand and overlapping resource quantities. Opposing known fields or different quantities produce an explicit conflict. Reports are not averaged, summed or silently overridden. The UI links the conflicting record. Both records remain visible; a coordinator must investigate and reject an incorrect record or accept reviewed corrections. Different landmarks are not assumed to represent the same incident.

Conflict detection is deliberately limited to structured fields and matching landmark text. It does not establish that differently worded free-text reports agree, identify every duplicate, or detect every semantic contradiction. Both observation times remain available to the reviewer.

Conflict-bearing field reports are excluded from model-confirming evidence. The selected report's issues go into the prompt. When a selected report has a structured conflict, the output is replaced with a resolve-the-conflict recommendation and operational claims are downgraded to insufficient evidence. A conflict, recorded blocked access or explicit no-demand status prevents plan approval. Existing plans are flagged for rechecking.

## Resource reliability

The quantity panel is calculated outside the LLM for one selected report:

`proposed upper bound = min(recorded requested quantity, available quantity)`

It preserves the resource's canonical unit, displays unmet demand, and does not estimate people served, convert packs into litres or combine multiple sites. Stale, unreviewed, pending-update, conflicting, blocked-access or explicit no-demand reports withhold numeric proposals. Missing requested quantities remain missing. The same quantity panel appears in saved plans and AI briefings.

These are per-request upper bounds, not allocations or automatic dispatch. Multiple plans do not reserve inventory. Human contact, access and receiving-time checks remain necessary. Whether a resource is actually appropriate on the ground requires external corroboration and human judgement.

## Measurements you can reproduce

Open **Our evidence** on the homepage. `/api/evaluation` executes the production recommendation guards and quantity checker against ten synthetic checks, with six three-stage scenarios using deliberately overconfident scripted model outputs and four deterministic resource checks. It shows each expectation and result, with local processing latency. There is no provider/network latency in this run.

```powershell
python evaluate_intelligence.py
```

The report is written to ignored `runtime/intelligence-evaluation.json`, with an accompanying `.review.csv` containing blank human-scoring columns. It includes the fixture sources, raw output, validated output, per-case latency, six constrained claim-status outcomes from the current evidence pipeline and four rule outcomes. Cases are author-labelled synthetic scenarios; neither this suite nor passing unit tests establish real-world model accuracy.

To evaluate the configured provider against the same evidence challenge:

```powershell
python evaluate_intelligence.py --provider groq --output runtime/groq-evaluation.json
```

This makes up to eighteen actual model calls using the backend key. It records request failures as failed cases, all three raw stage outputs and post-validation claim-status matches, per-call latency including validation, and the full outputs for review. It does not use Field Lab's scripted briefings. `human_factual_accuracy` stays null until a separate review is performed. The application does not expose raw benchmark files publicly.

## Human scoring protocol before claiming accuracy

Use two reviewers, neither of whom should treat source-category validity as proof of truth. Score each generated claim and action against the frozen source bundle, then reconcile disagreements. Keep the first-pass independent scores.

| Dimension | Record | Metric |
|---|---|---|
| Claim faithfulness | Supported, contradicted or not established by the cited passage | Supported factual assertions / all factual assertions; report denominator |
| Citation relevance | Does each citation actually support that particular claim? | Supporting citation links / all citation links |
| Uncertainty handling | Did the answer preserve the scenario's conflict or missing fact? | Correct uncertainty outcomes / applicable cases |
| Resource suitability | Is the item appropriate, and is any quantity supported with the right unit? | Suitable supported suggestions / all suggestions; report unsafe suggestions separately |
| Coverage | Did it omit a critical supported need or conflict? | Expected critical points included / expected critical points |
| Reliability and latency | Failures, schema rejection, raw and validated outputs | Completion rate, median and p95 latency across repeated runs |

Freeze an unseen evaluation set before changing prompts based on results. Include explicit counterevidence, mismatched dates/places, duplicate reports, unknown quantities, rescue outside NGO capability, and genuine corroborated requests. A small synthetic suite is a regression check, not a representative sample of disasters. No composite confidence score substitutes for the evidence.

## Faculty demo

1. Start **The stories don’t agree** in Field Lab. Advance twice. Compare two same-site records: passable vs blocked access; 120 vs 200 litres. Both have scripted checks but remain conflicting.
2. Save a practice draft. Show **Proposal withheld** and the source-change flag. Approval cannot bypass the structured conflict merely by ticking checkboxes.
3. Advance through the follow-up: a scripted investigation rejects the incorrect report, preserves its history and records the primary site's updated request. Show that remaining quantities are recalculated.
4. Start **Help needed. How much?**. Review the request: a corroborated need still has no quantity. No numeric supply count is invented.
5. Open **Our evidence** in live mode. Show the measured synthetic checks and explicitly explain the difference from live-model and human factual evaluation.

Live reports, scenario data and benchmark fixtures remain separate. The system remains non-agentic: deterministic retrieval and checks, optional model synthesis, and human decisions.

## Request-specific recommendations

Resource checks now carry the selected report ID and field-source ID. A response proposal requires a supported current needs claim citing that exact field source, no unresolved operational checks, and a bounded proposal. A supported news story or another report cannot substitute for the selected request. Provisional quantities remain visible when access or demand is unknown, with explicit missing-check warnings beside them; the action brief requests those checks instead of proposing a response. Blocked access, no demand, conflicts and missing quantities each select specific application-controlled next steps. This does not reserve stock or replace coordinator approval.

The public evidence panel uses `evidence-challenge-v2`: six scenarios call the current `evidence_brief` pipeline (assessment, semantic review and action brief), followed by four deterministic quantity rules. Raw stage outputs are retained for review, not reduced to a misleading first-pass accuracy score. These ten checks are a limited regression suite, not the entire test suite or live-model accuracy.
