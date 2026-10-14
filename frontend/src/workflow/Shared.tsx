import { useEffect, useRef, type ReactNode } from "react";
import { X, ExternalLink } from "lucide-react";
import { resourceNames, units, stamp, type Source, type Resource, type ResourceKind, type Briefing } from "./types";
export function Drawer({title, children, onClose}: {title: string; children: ReactNode; onClose: () => void}) {
  const ref = useRef<HTMLElement>(null), close = useRef(onClose); close.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement, overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden"; ref.current?.focus();
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") close.current();
      if (e.key !== "Tab") return;
      const nodes = Array.from(ref.current?.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input:not(:disabled),textarea,select,summary,[tabindex="0"]') || []).filter(el => el.getClientRects().length);
      if (!nodes.length) {e.preventDefault(); return;}
      if (e.shiftKey && (document.activeElement === nodes[0] || document.activeElement === ref.current)) {e.preventDefault(); nodes[nodes.length-1].focus();}
      else if (!e.shiftKey && document.activeElement === nodes[nodes.length-1]) {e.preventDefault(); nodes[0].focus();}
    };
    document.addEventListener("keydown",handler);
    return () => {document.body.style.overflow=overflow; document.removeEventListener("keydown",handler); previous?.focus();};
  }, []);
  return <><button className="flow-backdrop" aria-label="Close panel" onClick={onClose}/><aside className="flow-drawer" ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title}><div className="flow-drawer-heading"><span className="kicker">CRISISLENS / RESPONSE WORKSPACE</span><button className="icon-button" aria-label="Close drawer" onClick={onClose}><X size={22}/></button></div><h2>{title}</h2>{children}</aside></>;
}
export function Resources({value, onChange}: {value: Resource[]; onChange: (value: Resource[]) => void}) {
  return <div className="resource-fields">{(Object.keys(resourceNames) as ResourceKind[]).map(kind => <label key={kind}>{resourceNames[kind]} <small>{units[kind]}</small><input type="number" min="0" max="1000000" step="any" aria-label={`${resourceNames[kind]} quantity`} value={value.find(r => r.kind === kind)?.quantity ?? ""} onChange={e => { const quantity=Number(e.target.value); onChange([...value.filter(r => r.kind !== kind), ...(quantity > 0 && Number.isFinite(quantity) ? [{kind,quantity}] : [])].sort((a,b)=>a.kind.localeCompare(b.kind))); }}/></label>)}</div>;
}
export function SourceCard({source}: {source: Source}) {
  return <article className="flow-source"><span className="badge">{source.kind.replaceAll("_"," ")}</span><h4>{source.title}</h4><p>{source.excerpt}</p><small>{source.publisher} · {source.scope.replaceAll("_"," ")}</small><dl><dt>Published / observed</dt><dd>{stamp(source.published_at)}</dd><dt>Retrieved</dt><dd>{stamp(source.retrieved_at)}</dd>{source.expires_at && <><dt>Expires</dt><dd>{stamp(source.expires_at)}</dd></>}</dl><p className="muted">{source.limitation}</p>{source.url && <a href={source.url} target="_blank" rel="noopener noreferrer">Open original source <ExternalLink size={13}/></a>}</article>;
}
export function BriefingView({briefing}: {briefing: Briefing}) {
  const answer=briefing.recommendation;
  return <div className="briefing"><span className="kicker">AI PROPOSAL · HUMAN REVIEW REQUIRED</span><h3>{answer.headline}</h3><p>{answer.answer}</p>{answer.recommendations.map((item,i)=><article className="action-row" key={i}><span className="action-index">{i+1}</span><div><h4>{item.title}</h4><p><b>Why:</b> {item.explanation}</p><details><summary>Why? Check the evidence</summary>{item.source_ids.length ? briefing.context.sources.filter(s=>item.source_ids.includes(s.id)).map(s=><SourceCard key={s.id} source={s}/>) : <p>Preparedness suggestion; no supporting record attached.</p>}</details></div></article>)}{!!answer.affected_groups.length && <details><summary>People mentioned in the evidence</summary>{answer.affected_groups.map((g,i)=><div key={i}><h4>{g.title}</h4><p>{g.explanation}</p>{briefing.context.sources.filter(s=>g.source_ids.includes(s.id)).map(s=><SourceCard key={s.id} source={s}/>)}</div>)}</details>}{!!answer.missing_information.length && <div className="notice amber"><b>Still needs checking</b><ul>{answer.missing_information.map(item=><li key={item}>{item}</li>)}</ul></div>}<small>Generated {stamp(briefing.metadata.generated_at)} · interpretation, not independent verification.</small></div>;
}
