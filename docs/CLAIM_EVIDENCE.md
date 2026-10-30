# Claim evidence and action briefs

CrisisLensAI now makes two fixed model calls: first assess individual claims against supplied source records, then prepare actions linked to those claims. It does not run autonomous agents or dispatch resources.

## User flow

1. Generate an assistance brief for an area or reviewed request.
2. Read up to four short claims. Open **Why this assessment?** for the passage, publisher, date, locality and explanation.
3. Where accounts disagree, see both passages and a specific next check. Missing coverage does not mean a report is false.
4. Read **Your next steps**. Each action links to its claims and sources. Historical comparisons remain in a separate expandable section.
5. A coordinator reviews the plan before approval. Existing source-revision and resource checks still apply.

The interface replaces generic uncertainty banners with specific evidence and follow-up work. It does not hide disagreements or turn source reputation into a truth score.

## What is checked

- Every cited source must exist in the supplied bundle; every passage must be an exact substring of its source record. Invented citations or passages fail closed.
- Current evidence must match locality, source category and observation age. Policy windows are two hours for weather, six hours for field reports, and 24 hours for news and official alerts. Official alerts also require an unexpired validity period. These are application policies, not validated hazard thresholds.
- Forecasts and official warnings cannot establish an actual local incident or assistance need. Unreviewed field reports remain leads. Historical records cannot establish current conditions.
- Repeated URLs or identical source text are marked as duplicates rather than independent corroboration. This does not detect all syndicated reporting.
- Existing structured field-report conflicts remain unresolved even if generated prose sounds certain.
- Response actions require supported current claims, a needs claim, a bounded resource proposal and no current claim conflict. Other cases lead to checks instead of allocation. Quantities come from existing deterministic request/stock bounds, not generated supply lists.

The model still interprets whether a passage supports or contradicts a claim. Exact matching is not semantic truth verification. A source-backed report describes what a source reports, not guaranteed ground truth. No calibrated accuracy percentage is displayed.

## Source coverage

Retrieval remains the existing fixed weather/news/official-warning collection and reviewed operational records. This change does not add unrestricted web search. Historical evidence uses the six curated cases in `research/cfm/incidents.json`; passages are explicitly labeled curated notes, not quotations from full articles. Those cases still require human adjudication and are not training labels.

Provider or schema failures do not produce a fabricated fallback brief. Two sequential calls can take longer than the previous single-call flow; the frontend allows up to 210 seconds.

## Evaluate with the configured Groq key

From the repository root, with the backend environment configured:

```powershell
python evaluate_evidence.py --case chromepet-2021
```

This makes up to three real model calls: one unaided answer and the two-stage evidence pipeline. It writes `runtime/evidence-comparison.json` and a blank `.review.csv`. Use `--case all` for all six cases (up to 18 calls). There is no synthetic fallback, and failures are recorded without raw credential-bearing errors.

Have a reviewer inspect the original linked sources and record unsupported claims, missed conflicts, wrong time/location and unsupported actions for each variant. Latency is measured automatically; factual accuracy remains unset until adjudication. This is a small historical comparison, not a representative disaster-response benchmark or proof of operational readiness.

## Automated validation

`tests/test_evidence.py` exercises citation integrity, stale and wrong-scope evidence, source eligibility, conflicts, duplicates and action gates. Browser coverage exercises claim expansion, historical separation, mobile layout and the approval/export workflow with a scripted provider. Scripted checks establish software behavior, not live model accuracy.
