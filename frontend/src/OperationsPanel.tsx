import { useEffect, useState, type FormEvent } from "react";
import { AlertTriangle, ArrowUpRight, Check, Plus, Radio, Send } from "lucide-react";
import type { PilotArea } from "./data/pastTrends";
import "./operations.css";

type Alert = { id: string; event: string; headline: string; instruction: string; area: string; sender: string; severity: string; certainty: string; sent_at: string; received_at: string; expires_at: string | null; state: string; url: string };
type Audit = { reviewer: string; method: string; note: string; reviewed_at: string; status: string };
type Report = { id: string; location: PilotArea; landmark: string; observed_at: string; description: string; needs: string; status: string; revision: number; stale: boolean; review_history?: Audit[] };
export type OperationsSnapshot = { location: PilotArea; retrieved_at: string; feed: { stale: boolean; error?: string; last_success?: string; last_attempt?: string; coverage: string }; alerts: Alert[]; reports: Report[]; review_enabled: boolean };
const stamp = (value?: string | null) => value ? new Date(value).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) + " IST" : "Not received";
const nowIST = () => new Date(Date.now() + 330 * 60000).toISOString().slice(0, 16);
async function send(path: string, body: unknown, token?: string) {
  const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json", ...(token ? { "X-Review-Token": token } : {}) }, body: JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Check the report fields and observation time.");
  return data;
}
function ReviewForm({ report, done }: { report: Report; done: () => void }) {
  const [error, setError] = useState(""), [busy, setBusy] = useState(false);
  async function review(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setBusy(true);
    const form = event.currentTarget, data = new FormData(form);
    try {
      await send(`/api/reports/${report.id}/review`, { revision: report.revision, status: data.get("status"), reviewer: data.get("reviewer"), method: data.get("method"), note: data.get("note") }, String(data.get("token")));
      form.reset(); done();
    } catch (e) { setError(e instanceof Error ? e.message : "Review could not be saved."); }
    finally { setBusy(false); }
  }
  return <details className="ops-review"><summary>Coordinator review</summary><form onSubmit={review}>
    <p>Record the check you actually performed. This saves an audit entry.</p>
    <label>Coordinator token<input name="token" type="password" autoComplete="off" required maxLength={256}/></label>
    <label>Reviewer name or ID<input name="reviewer" required minLength={2} maxLength={80}/></label>
    <div className="ops-fields"><label>Checked through<select name="method"><option value="on_site">On-site observation</option><option value="phone">Phone contact</option><option value="official_reference">Official reference</option></select></label>
    <label>Review outcome<select name="status"><option value="reviewed">Reviewed — report corroborated</option><option value="rejected">Rejected — not corroborated</option><option value="resolved">Resolved — need ended</option></select></label></div>
    <label>What did you check?<textarea name="note" required minLength={20} maxLength={1000} placeholder="Evidence, check time and source reference. Avoid private contact details."/></label>
    {error && <p role="alert" className="ops-error">{error}</p>}<button className="ops-button" disabled={busy}><Check size={15}/>{busy ? "Saving…" : "Save review"}</button>
  </form></details>;
}
export default function OperationsPanel({ area, onSnapshot }: { area: PilotArea; onSnapshot: (data: OperationsSnapshot | null) => void }) {
  const [data, setData] = useState<OperationsSnapshot | null>(null), [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0), [reporting, setReporting] = useState(false), [busy, setBusy] = useState(false), [message, setMessage] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    setData(null); onSnapshot(null);
    async function load() {
      try {
        const response = await fetch(`/api/operations/${area}`, { signal: controller.signal });
        if (!response.ok) throw new Error();
        const snapshot: OperationsSnapshot = await response.json();
        if (snapshot.location !== area || !Array.isArray(snapshot.alerts)) throw new Error();
        if (!controller.signal.aborted) { setData(snapshot); onSnapshot(snapshot); setError(""); }
      } catch { if (!controller.signal.aborted) { setError("Connection lost. Current warnings and reports cannot be checked."); onSnapshot(null); } }
    }
    void load();
    const timer = window.setInterval(() => void load(), 20000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [area, refresh, onSnapshot]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setMessage("");
    const form = event.currentTarget, fields = new FormData(form);
    try {
      await send("/api/reports", { location: area, landmark: fields.get("landmark"), observed_at: new Date(String(fields.get("observed_at")) + ":00+05:30").toISOString(), description: fields.get("description"), needs: fields.get("needs") });
      form.reset(); setReporting(false); setMessage("Report saved as unreviewed. A coordinator must check it."); setRefresh(value => value + 1);
    } catch (e) { setMessage(e instanceof Error ? e.message : "Report could not be saved."); }
    finally { setBusy(false); }
  }
  const stale = !!error || !data || data.feed.stale;
  return <section className="operations-panel" aria-label="Official alerts and field reports">
    <div className="ops-heading"><div><span className="eyebrow"><Radio size={13}/> DIRECT FROM THE SOURCE</span><h2>On the ground in {area}.</h2></div><button className="ops-button" onClick={() => setReporting(value => !value)} aria-expanded={reporting}><Plus size={16}/>{reporting ? "Close report form" : "Add field report"}</button></div>
    <div className={`ops-health ${stale ? "is-stale" : ""}`}><span><i/>{error ? "Connection unavailable" : !data ? "Checking official alerts…" : data.feed.stale ? "Official feed not current" : "Official feed checked"}</span><small>Last complete check: {stamp(data?.feed.last_success)} · intake every 2 min</small></div>
    {(error || data?.feed.error) && <p className="ops-error" role="status">{error || data?.feed.error}</p>}
    {message && <p className="ops-message" role="status">{message}</p>}
    {reporting && <form className="ops-report-form" onSubmit={submit}><h3>What did you observe?</h3><p>Saved for {area}. Use actual observations; avoid names and phone numbers.</p>
      <div className="ops-fields"><label>Street or landmark<input name="landmark" required minLength={3} maxLength={160} placeholder="Exact place within the selected area"/></label><label>Observed at (IST)<input name="observed_at" type="datetime-local" required defaultValue={nowIST()}/></label></div>
      <label>What is happening?<textarea name="description" required minLength={15} maxLength={2000} placeholder="Describe what you saw, including access and people affected if known."/></label>
      <label>Assistance requested (optional)<input name="needs" maxLength={500} placeholder="Only requests actually received"/></label>
      <button className="ops-button" disabled={busy}><Send size={15}/>{busy ? "Saving…" : "Submit unreviewed report"}</button></form>}
    <div className="ops-grid"><div><h3><AlertTriangle size={16}/> Official warnings <span>{data?.alerts.length ?? "—"}</span></h3>
      {data?.alerts.length ? data.alerts.map(alert => <article className="ops-alert" key={alert.id}>
        <div className="ops-tags"><span>{stale ? "May be outdated" : alert.state === "active" ? "Official warning" : alert.state === "scheduled" ? "Upcoming warning" : "Expiry unknown"}</span><span>District scope</span></div>
        <h4>{alert.event || "Official warning"}</h4><p>{alert.sender} · {alert.severity} · {alert.certainty}</p>
        <p className="ops-expiry">Issued {stamp(alert.sent_at)} · Ends {stamp(alert.expires_at)}</p>
        <details><summary>Why? Read the official warning <ArrowUpRight size={13}/></summary><p>{alert.headline}</p><p><b>Official instruction:</b> {alert.instruction || "No instruction supplied."}</p><p><b>Area:</b> {alert.area}</p><p>First received {stamp(alert.received_at)}</p><a href={alert.url} target="_blank" rel="noopener noreferrer">Open original CAP record ↗</a></details>
        <small>A district warning does not confirm flooding at this street.</small>
      </article>) : <p className="ops-empty">{stale ? "No current official warning information available." : "No unexpired district match in the monitored feed."}<strong>This is not an all-clear.</strong></p>}
    </div><div><h3><Radio size={16}/> Field reports <span>{data?.reports.length ?? "—"}</span></h3>
      {data?.reports.length ? data.reports.map(report => <article className="ops-field" key={report.id}>
        <div className="ops-tags"><span>{report.status === "reviewed" ? "Human-reviewed" : report.status === "unreviewed" ? "Unreviewed" : report.status}</span>{(report.stale || !!error) && <span>{error ? "Status may be outdated" : "Observation over 6 hours old"}</span>}</div>
        <h4>{report.landmark}</h4><p className="ops-expiry">Observed {stamp(report.observed_at)}</p><p>{report.description}</p>{report.needs && <p><b>Requested:</b> {report.needs}</p>}
        {!!report.review_history?.length && <details><summary>Why this status? Review trail</summary>{report.review_history.map((review, index) => <div className="ops-audit" key={index}><b>{review.status} · {review.method.replaceAll("_", " ")}</b><p>{review.note}</p><small>{review.reviewer} · {stamp(review.reviewed_at)}</small></div>)}<p>A recorded human check is not independent certification.</p></details>}
        {data.review_enabled && <ReviewForm key={report.id + report.revision} report={report} done={() => setRefresh(value => value + 1)}/>}
      </article>) : <p className="ops-empty">No reports received here in the last seven days.<strong>Share an observation to start a local check.</strong></p>}
      {data && !data.review_enabled && <small className="ops-review-disabled">Coordinator review has not been enabled on this server.</small>}
    </div></div>
    <details className="ops-coverage"><summary>What is monitored?</summary><p>{data?.feed.coverage || "SACHET official warnings and reports submitted to this CrisisLens server."}</p><p>Warnings appear without AI. Only recent coordinator-reviewed reports and current official warnings enter the AI evidence bundle. News provides secondary context. No street sensors are connected.</p></details>
  </section>;
}
