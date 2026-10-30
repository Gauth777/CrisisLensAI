import {CheckCircle2, ArrowUpRight, Clock3, GitCompareArrows, SearchCheck} from 'lucide-react';
import {SourceCard} from './Shared';
import {stamp, type Briefing} from './types';
import './evidence.css';

export function EvidenceTrail({briefing}:{briefing:Briefing}) {
 const assessment=briefing.evidence_assessment;
 if(!assessment)return null;
 const current=assessment.claims.filter(c=>c.timeframe==='current');
 const historical=assessment.claims.filter(c=>c.timeframe==='historical');
 const cards=(claims:typeof current)=>claims.map(c=><article key={c.id} className={`claim-card claim-${c.status}`}>
  <div className="claim-heading"><span className="claim-label">{c.status==='supported'?<CheckCircle2 size={15}/>:c.status==='conflicting'?<GitCompareArrows size={15}/>:<SearchCheck size={15}/>} {c.label}</span><span className="claim-id">{c.id}</span></div>
  <h4>{c.statement}</h4><p>{c.explanation}</p>
  <div className="claim-publishers">{[...new Set(c.evidence.map(e=>briefing.context.sources.find(s=>s.id===e.source_id)?.publisher).filter(Boolean))].map(p=><span key={p}>{p}</span>)}</div>
  <details className="claim-proof"><summary>Why this assessment? <ArrowUpRight size={15}/></summary>
   {c.evidence.length?c.evidence.map((e,i)=>{const s=briefing.context.sources.find(s=>s.id===e.source_id);return <div className="evidence-passage" key={`${e.source_id}-${i}`}>
    <span className="badge">{e.duplicate?'Repeated source':!e.eligible?'Context only':e.direction==='supports'?'Supports this detail':e.direction==='contradicts'?'Opposes this detail':'Context only'}</span>
    <p className="passage-label">{s?.kind==='historical'?'Curated note from historical source':'Passage from the supplied source record'}</p><blockquote>{e.passage}</blockquote><p><b>Why it matters:</b> {e.reason}</p>
    {e.context_reason&&<p className="evidence-context">{e.context_reason}</p>}{s&&<><small><Clock3 size={12}/> {stamp(s.published_at)} · {s.scope.replaceAll('_',' ')}</small><details><summary>Open source record</summary><SourceCard source={s}/></details></>}
   </div>}):<p>No supplied source addresses this detail yet.</p>}
  </details>
  {(c.status==='check_needed'||c.status==='conflicting')&&<div className="claim-next"><b>Next check</b><span>{c.next_check}</span></div>}
 </article>);
 return <section className="evidence-trail" aria-label="Claim-by-claim evidence"><div className="evidence-intro"><span className="kicker">THE EVIDENCE BEHIND YOUR BRIEF</span><h3>Know what each source supports.</h3><p>Open a claim to see the passage, its date and why it applies.</p></div>{cards(current)}{historical.length>0&&<details className="historical-evidence"><summary>Past incidents · {historical.length} comparisons</summary><p>Historical context, separate from today's conditions.</p>{cards(historical)}</details>}<details className="evidence-method"><summary>How these checks work</summary><p>Checks cover source references, matching passages, locality, source type, observation age and duplicate records. The model interprets the passages; these checks do not establish ground truth.</p><p>No votes or confidence percentages. Missing coverage is a specific follow-up, not evidence that a report is false.</p></details></section>;
}
