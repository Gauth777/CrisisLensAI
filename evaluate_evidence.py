"""Compare unaided Groq output with the three-stage evidence pipeline on historical cases.

Real provider calls; no synthetic fallback. Results require human factual review.
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import time
from datetime import datetime,timezone
from pathlib import Path
from crisislens.config import build_provider,load_environment
from crisislens.evidence import evidence_brief,historical_sources
from crisislens.recommendations import RecommendationQuestion,RecommendationOutput,recommendation_schema
from crisislens.provider_failures import classify_provider_failure

ROOT=Path(__file__).resolve().parent


def run(provider,case):
    question=RecommendationQuestion(location=case['area'],question=(
        f"Review historical reporting about {case['site']} on {case['observed_on']}. "
        'Explain what is established about flooding, which details disagree and what an NGO should check. '
        'This is a retrospective evidence exercise, not a current request for dispatch.'))
    sources=[s for s in historical_sources(case['area']) if s['case_id']==case['id']]
    context={'location':case['area'],'sources':sources,'source_status':[{'name':'Historical case catalogue','status':'available'}],
             'coverage_note':'Historical source notes; no current observations or verified supply requests.',
             'evidence_issues':{'status':'hold_for_check','conflicts':[]}}
    results=[]
    for variant in ('unaided','evidence_pipeline'):
        started=time.perf_counter()
        row={'variant':variant,'status':'failed'}
        try:
            if variant=='unaided':
                raw=provider.generate_json(system_prompt=(
                    'Provide a concise NGO assistance brief for this historical question. You have no retrieval tools or supplied sources. '
                    'Do not invent citations or treat missing information as false. Use empty source_ids and claim_ids. '
                    'Return the requested JSON schema; distinguish historical events from current conditions.'),
                    user_prompt=question.question,output_schema=recommendation_schema())
                row['output']=RecommendationOutput.model_validate(raw).model_dump()
            else:
                answer,assessment=evidence_brief(provider,question,context)
                row.update(output=answer.model_dump(),evidence_assessment=assessment)
            row['status']='completed'
        except Exception as exc:
            failure=classify_provider_failure(exc,'groq')
            row['error_category']=failure.category
            # Do not write raw provider errors, credentials or stack traces into reports.
        row['latency_ms']=round((time.perf_counter()-started)*1000,2)
        results.append(row)
    return {'id':case['id'],'event_group':case['event_group'],'question':question.model_dump(),
        'source_notes':sources,'known_review_gaps':case['unknowns'],'recorded_disagreements':case['conflicts'],
        'results':results}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',default='chromepet-2021',help='Case ID, or all (up to 24 model calls)')
    parser.add_argument('--output',type=Path,default=ROOT/'runtime/evidence-comparison.json')
    args=parser.parse_args()
    load_environment()
    if not os.getenv('GROQ_API_KEY','').strip():
        parser.error('Configure GROQ_API_KEY in the backend environment; do not paste it into a command.')
    cases=json.loads((ROOT/'research/cfm/incidents.json').read_text())['incidents']
    cases=[c for c in cases if args.case=='all' or c['id']==args.case]
    if not cases:parser.error('Unknown case ID')
    provider=build_provider('groq')
    report={'run_at':datetime.now(timezone.utc).isoformat(),'model':provider.model,
        'comparison':'Same model: unaided generation versus source-backed three-stage pipeline',
        'factual_accuracy':None,'notes':['Not a statistically representative benchmark; six cases in four event groups.',
         'Source notes are assistant-curated and not independently adjudicated ground truth.',
         'Only unaided output is raw; pipeline output includes deterministic gates.',
         'No automatic truth score. Review unsupported claims, conflicts, scope and actions using the source records.'],
        'cases':[]}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    for case in cases:
        report['cases'].append(run(provider,case))
        args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
        print(case['id'],[(r['variant'],r['status']) for r in report['cases'][-1]['results']])
    review=args.output.with_suffix('.review.csv')
    with review.open('w',newline='',encoding='utf-8') as f:
        fields=['case_id','variant','reviewer','review_date','unsupported_claims','missed_conflicts','wrong_time_or_location','unsupported_actions','notes']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for c in report['cases']:
            for r in c['results']:writer.writerow({'case_id':c['id'],'variant':r['variant']})
    print('Saved comparison and blank review sheet:',args.output,review)
    if any(r['status']!='completed' for c in report['cases'] for r in c['results']):raise SystemExit(1)

if __name__=='__main__':main()
