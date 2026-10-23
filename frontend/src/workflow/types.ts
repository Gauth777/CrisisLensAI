export type ResourceCheck = {status:string;rows:{kind:string;unit:string;requested:number;available:number;suggested_max:number|null;uncovered:number|null}[];conflicts:{report_id:string;reasons:string[]}[];missing_checks:string[];note:string};
export type Area = "Velachery" | "Tambaram" | "Chromepet";
export const areas: Area[] = ["Velachery", "Tambaram", "Chromepet"];
export type ResourceKind = "food" | "water" | "medical" | "shelter" | "other";
export const resourceNames: Record<ResourceKind, string> = { food: "Food kits", water: "Drinking water", medical: "Medical kits", shelter: "Shelter places", other: "Other supplies" };
export const units: Record<ResourceKind, string> = { food: "kits", water: "litres", medical: "kits", shelter: "places", other: "items" };
export type Resource = {kind: ResourceKind; quantity: number};
export type Audit = {reviewer: string; method: string; note: string; reviewed_at: string; status: string; update_id?: string};
export type Update = {id: string; outcome: string; observed_at: string; note: string; needs: string; resources: Resource[]; submitted_at: string; status: string};
export type Report = {access_status?:string;demand_status?:string;conflicts?:{report_id:string;reasons:string[]}[];missing_checks?:string[];id: string; location: Area; landmark: string; observed_at: string; submitted_at: string; description: string; needs: string; resources?: Resource[]; status: string; revision: number; stale: boolean; pending_updates?: number; updates?: Update[]; review_history: Audit[]; last_review?: Audit};
export type AlertRecord = {id: string; event: string; headline: string; instruction: string; area: string; sender: string; severity: string; certainty: string; sent_at: string; received_at: string; last_seen_at?: string; expires_at: string | null; state: string; url: string; record_current?: boolean; coverage_incomplete?: boolean};
export type Feed = {stale: boolean; status?: string; error?: string; checking?: boolean; last_success?: string; last_feed_success?: string; last_attempt?: string; entries?: number; checked_entries?: number; failed_entries?: number; failures?: {url: string; reason: string; attempted_at: string}[]; coverage: string};
export type Snapshot = {location: Area; retrieved_at: string; feed: Feed; alerts: AlertRecord[]; reports: Report[]; review_enabled: boolean};
export type Source = {id: string; kind: string; title: string; publisher: string; url: string | null; published_at: string | null; retrieved_at: string; excerpt: string; scope: string; limitation: string; expires_at?: string};
export type Context = {location: Area; retrieved_at: string; outlook: null | {environment: {temperature_c: number | null; observed_at: string}; next_rain: {time: string; precipitation_mm: number | null; probability_percent: number | null} | null; hours: {time: string; precipitation_mm: number | null; probability_percent: number | null}[]; forecast_complete: boolean}; sources: Source[]; source_status: {name: string; status: string}[]; coverage_note: string};
export type Cited = {title: string; explanation: string; source_ids: string[]};
export type Briefing = {resource_check?:ResourceCheck;validation?:{uncertain_claims:number;claim_count:number};briefing_id: string; recommendation: {claims?:{statement:string;status:string;explanation:string;source_ids:string[]}[];headline: string; answer: string; recommendations: Cited[]; affected_groups: Cited[]; supplies: Cited[]; missing_information: string[]}; context: Context; metadata: {generated_at: string; model: string}};
export type Plan = {resource_check?:ResourceCheck;id: string; location: Area; report_id: string | null; report_snapshot: Report | null; briefing: Briefing | null; revision: number; volunteers: number; resources: Resource[]; notes: string; status: string; created_at: string; updated_at: string; contact_checked: boolean; access_checked: boolean; receiving_time_checked: boolean; source_changed?: boolean; history: {at: string; action: string; actor?: string; note: string}[]};
export type Health = {default_provider: string; providers: Record<string, {configured: boolean; model: string}>};
export const stamp = (value?: string | null) => value ? new Date(value).toLocaleString("en-IN", {timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "numeric", minute: "2-digit"}) + " IST" : "Not yet received";
export const nowIST = () => new Date(Date.now() + 330 * 60000).toISOString().slice(0, 23);
export const reportLabel = (r: Report) => r.conflicts?.length ? "Conflicting reports" : r.pending_updates ? "Update awaiting review" : r.stale ? "Needs a fresh check" : r.status === "reviewed" ? "Coordinator-reviewed" : r.status === "unreviewed" ? "Unreviewed" : r.status === "resolved" ? "Resolved" : "Rejected";
export const availableReport = (r: Report) => r.status === "reviewed" && !r.stale && !r.pending_updates && !r.conflicts?.length && r.demand_status!=="not_needed" && r.access_status!=="blocked";
export async function api<T>(path: string, body?: unknown, token?: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {signal, ...(body === undefined ? {} : {method: "POST", headers: {"Content-Type": "application/json", ...(token ? {"X-Review-Token": token} : {})}, body: JSON.stringify(body)})});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Check the entered values and observation time.");
  return data;
}
export function download(name: string, text: string, type = "text/plain") {
  const url = URL.createObjectURL(new Blob([text], {type})); const anchor = document.createElement("a");
  anchor.href = url; anchor.download = name; anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
