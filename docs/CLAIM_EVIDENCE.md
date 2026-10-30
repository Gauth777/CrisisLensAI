# Claim evidence and action briefs

CrisisLensAI now makes three fixed model calls: propose claims, separately review their meaning against the complete source bundle, then draft an action brief. The application replaces generated action wording and the summary with controlled templates. It does not run autonomous agents or dispatch resources.

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

Provider or schema failures do not produce a fabricated fallback brief. Three sequential calls can take longer than the previous single-call flow; the frontend allows up to 300 seconds.

## Evaluate with the configured Groq key

From the repository root, with the backend environment configured:

```powershell
python evaluate_evidence.py --case chromepet-2021
```

This makes up to four real model calls: one unaided answer and the three-stage evidence pipeline. It writes `runtime/evidence-comparison.json` and a blank `.review.csv`. Use `--case all` for all six cases (up to 24 calls). There is no synthetic fallback, and failures are recorded without raw credential-bearing errors.

Have a reviewer inspect the original linked sources and record unsupported claims, missed conflicts, wrong time/location and unsupported actions for each variant. Latency is measured automatically; factual accuracy remains unset until adjudication. This is a small historical comparison, not a representative disaster-response benchmark or proof of operational readiness.

## Automated validation

`tests/test_evidence.py` exercises citation integrity, stale and wrong-scope evidence, source eligibility, conflicts, duplicates and action gates. Browser coverage exercises claim expansion, historical separation, mobile layout and the approval/export workflow with a scripted provider. Scripted checks establish software behavior, not live model accuracy.

## Adversarial hardening

Known historical case conflicts force a comparison status and retain the related source records even if both model passes omit the disagreement. This is a conservative case-level hold, not a determination that every detail conflicts. The semantic reviewer must cover every claim exactly once; missing coverage, invalid schema or unknown source IDs fail closed. It cannot promote stale or otherwise ineligible evidence. A negative review withholds support and explains why.

Operational action titles, explanations and briefing summaries use application-controlled wording for check, readiness and bounded-proposal review. A model-supplied intent label cannot expose arbitrary dispatch instructions or quantities in these fields. Claim and evidence explanations remain model-interpreted content. The separate review uses the same configured model, so errors may be correlated; it is not independent corroboration. Scripted adversarial tests validate enforcement, not the probability of the live model detecting unsupported claims.

## Public brief wording (v3)

All generated next-check instructions, passage reasons and claim explanations are replaced with application-controlled wording, including historical checks. Historical conflict badges explicitly say “Sources disagree · past incident”. Missing-information output is cleared in the assessed brief; the category-specific next checks provide the follow-up instead.

A claim headline must match a complete sentence in a cited source and occur in its attached passage, allowing only whitespace and case normalization. Otherwise its public headline becomes a review prompt, its evidence links lose confirmation eligibility, and it cannot remain supported even if both model passes agree. This intentionally sacrifices some paraphrasing coverage. Sentence splitting is conservative and can withhold valid abbreviations or complicated sentences. Exact extraction does not prove a source true, detect all misleading quotations or establish semantic relevance. The UI labels these headlines as source sentences and passages as quotations rather than application instructions.

People cards use a small controlled group vocabulary, match whole phrases in eligible current sources and use a fixed description identifying a source mention. They do not infer affected counts or assistance needs. Unlisted groups may be omitted; the full source remains available. Free-form model explanations are not displayed in these cards.

Regression tests include two agreeing but wrong model passes, negation stripped from a sentence, historical dispatch instructions, poisoned explanations throughout the public brief and an instruction disguised as a group name. These are enforcement tests; live model quality and source accuracy remain unmeasured.
