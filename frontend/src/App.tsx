import { useEffect, useState } from "react";
import {
  Activity,
  ArrowDown,
  ArrowRight,
  Check,
  ChevronDown,
  CircleHelp,
  CloudRain,
  Download,
  FileText,
  Layers3,
  LoaderCircle,
  MapPin,
  Radio,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Thermometer,
  TriangleAlert,
  Wind,
  X,
} from "lucide-react";

type Location = "Tambaram" | "Chromepet" | "Velachery";
type Provider = "gemini" | "openai" | "groq";
type Mode = "sample" | "manual" | "unknown" | "live";
type Environment = {
  rainfall_1h_mm?: number | null;
  rainfall_24h_mm?: number | null;
  temperature_c?: number | null;
  humidity_percent?: number | null;
  wind_speed_kmph?: number | null;
  wind_direction_deg?: number | null;
  water_level_m?: number | null;
  observed_at?: string | null;
  source_name?: string | null;
  source_kind?: "manual_development_input" | "gridded_weather_fallback" | null;
};
type Input = {
  report: string;
  location: Location;
  timestamp: string | null;
  environment: Environment;
  source_label: string;
};
type Scenario = { id: string; input: Input };
type Health = {
  default_provider?: Provider;
  providers: Record<Provider, { configured: boolean; model: string }>;
};
type Assessment = {
  location: Location;
  disaster_type: string;
  severity: "low" | "medium" | "high" | "critical";
  severity_evidence: { statement: string; source: string }[];
  affected_people: string[];
  resources_required: string[];
  recommended_actions: string[];
  missing_information: string[];
  situation_report: string;
};
type Result = {
  input: Input;
  assessment: Assessment;
  metadata: {
    provider: Provider;
    model: string;
    generated_at: string;
    latency_ms: number;
  };
};
type NumericField =
  | "rainfall_1h_mm"
  | "rainfall_24h_mm"
  | "temperature_c"
  | "humidity_percent"
  | "wind_speed_kmph"
  | "wind_direction_deg"
  | "water_level_m";
const fields: {
  key: NumericField;
  label: string;
  unit: string;
  min: number;
  max?: number;
}[] = [
  { key: "rainfall_1h_mm", label: "Rainfall · 1 hour", unit: "mm", min: 0 },
  { key: "rainfall_24h_mm", label: "Rainfall · 24 hours", unit: "mm", min: 0 },
  { key: "temperature_c", label: "Temperature", unit: "°C", min: -20, max: 60 },
  { key: "humidity_percent", label: "Humidity", unit: "%", min: 0, max: 100 },
  { key: "wind_speed_kmph", label: "Wind speed", unit: "km/h", min: 0 },
  {
    key: "wind_direction_deg",
    label: "Wind direction",
    unit: "°",
    min: 0,
    max: 360,
  },
  { key: "water_level_m", label: "Water level", unit: "m", min: 0 },
];
const sourceLabels: Record<string, string> = {
  field_report: "Field report",
  environmental_context: "Environmental context",
  location_context: "Locality context",
};
const locations: Location[] = ["Tambaram", "Chromepet", "Velachery"];
const titles: Record<string, string> = {
  velachery: "Urban flooding",
  chromepet: "Residential waterlogging",
  tambaram: "Wind & infrastructure",
};
const words = (value: string) => value.replaceAll("_", " ");
const formatTime = (value?: string | null) =>
  value
    ? Number.isNaN(Date.parse(value))
      ? value
      : new Date(value).toLocaleString("en-IN", {
          timeZone: "Asia/Kolkata",
          dateStyle: "medium",
          timeStyle: "short",
        }) + " IST"
    : "Not supplied";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 150000);
  try {
    const response = await fetch(path, {
      ...options,
      signal: controller.signal,
    });
    const data = await response.json();
    if (!response.ok)
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : "Input rejected. Check the report, locality and measurement ranges.",
      );
    return data as T;
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError")
      throw new Error(
        "The request timed out. Retry after checking backend connectivity.",
      );
    if (error instanceof TypeError || error instanceof SyntaxError)
      throw new Error(
        "Cannot reach the CrisisLens API. Start the backend and retry.",
      );
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

function ItemList({
  items,
  numbered = false,
}: {
  items: string[];
  numbered?: boolean;
}) {
  if (!items.length)
    return <p className="muted">None identified from the supplied evidence.</p>;
  return (
    <ul className="item-list">
      {items.map((item, index) => (
        <li key={index}>
          <span className={numbered ? "item-number" : "item-dot"}>
            {numbered ? String(index + 1).padStart(2, "0") : ""}
          </span>
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [provider, setProvider] = useState<Provider>("gemini");
  const [location, setLocation] = useState<Location>("Velachery");
  const [report, setReport] = useState("");
  const [timestamp, setTimestamp] = useState<string | null>(null);
  const [environment, setEnvironment] = useState<Environment>({});
  const [mode, setMode] = useState<Mode>("unknown");
  const [sourceLabel, setSourceLabel] = useState("citizen_or_field_report");
  const [selectedSample, setSelectedSample] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [weatherBusy, setWeatherBusy] = useState(false);
  const [error, setError] = useState("");
  const [connectionError, setConnectionError] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const locked = busy || weatherBusy;
  const configured = health?.providers[provider]?.configured ?? false;

  async function connect() {
    setConnectionError("");
    try {
      const [status, samples] = await Promise.all([
        request<Health>("/api/health"),
        request<Scenario[]>("/api/scenarios"),
      ]);
      setHealth(status);
      if (!health && status.default_provider && status.providers[status.default_provider]) {
        setProvider(status.default_provider);
      }
      setScenarios(samples);
    } catch (e) {
      setHealth(null);
      setConnectionError((e as Error).message);
    }
  }
  useEffect(() => {
    void connect();
  }, []);
  function changed() {
    setResult(null);
    setError("");
  }
  function loadSample(s: Scenario) {
    changed();
    setLocation(s.input.location);
    setReport(s.input.report);
    setTimestamp(s.input.timestamp);
    setEnvironment(s.input.environment);
    setSourceLabel(s.input.source_label);
    setMode("sample");
    setSelectedSample(s.id);
  }
  function changeLocation(next: Location) {
    changed();
    setLocation(next);
    setReport("");
    setTimestamp(null);
    setEnvironment({});
    setMode("unknown");
    setSelectedSample(null);
    setSourceLabel("citizen_or_field_report");
  }
  async function fetchWeather() {
    changed();
    setWeatherBusy(true);
    try {
      const data = await request<Environment>(`/api/weather/${location}`);
      setEnvironment(data);
      setMode("live");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setWeatherBusy(false);
    }
  }
  function changeMode(next: Mode) {
    changed();
    if (next === "unknown") setEnvironment({});
    if (next === "manual")
      setEnvironment({
        ...environment,
        source_name: "Manual development input (unverified)",
        source_kind: "manual_development_input",
      });
    setMode(next);
  }
  async function generate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    changed();
    setBusy(true);
    const input: Input = {
      report: report.trim(),
      location,
      timestamp,
      environment,
      source_label: sourceLabel,
    };
    try {
      setResult(
        await request<Result>("/api/analyse", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ input, provider }),
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function download() {
    if (!result) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(result, null, 2)], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `crisislens-${result.input.location.toLowerCase()}-${Date.now()}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }
  const assessment = result?.assessment;

  return (
    <div className="app-shell">
      <aside className="rail" aria-label="Workspace navigation">
        <a className="brand-symbol" href="#" aria-label="CrisisLens home">
          <Layers3 size={26} />
        </a>
        <div className="rail-active" title="Assessment workspace">
          <Activity size={22} />
        </div>
        <div className="rail-bottom">
          <ShieldCheck size={22} />
          <span>V0.4</span>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <a href="#" className="wordmark">
            CrisisLens<span>AI</span>
          </a>
          <div className="topbar-right">
            <span className="pilot-tag">
              <MapPin size={13} /> CHENNAI PILOT
            </span>
            <span className="connection">
              <i className={health ? "dot connected" : "dot"} />
              {health ? "Backend connected" : "Backend offline"}
            </span>
            <button
              type="button"
              className="icon-button"
              aria-label="Refresh backend status"
              onClick={() => void connect()}
              disabled={locked}
            >
              <RefreshCw size={15} />
            </button>
          </div>
        </header>
        <main>
          <section className="page-heading">
            <div>
              <div className="eyebrow">
                <span /> EVIDENCE-GROUNDED GENERATIVE AI
              </div>
              <h1>Clarity when it matters.</h1>
              <p>
                Turn field reports into structured crisis intelligence for
                Chennai.
              </p>
            </div>
            <div className="human-tag">
              <ShieldCheck size={18} />
              <div>
                Human-led response<small>Advisory intelligence only</small>
              </div>
            </div>
          </section>
          <section className="pipeline-strip" aria-label="Assessment pipeline">
            <div>
              <span className="step-index">01</span>
              <FileText size={16} /> Incident report
            </div>
            <ArrowRight size={14} />
            <div>
              <span className="step-index">02</span>
              <CloudRain size={17} /> Environmental context
            </div>
            <ArrowRight size={14} />
            <div>
              <span className="step-index">03</span>
              <Sparkles size={16} /> GenAI synthesis
            </div>
            <ArrowRight size={14} />
            <div>
              <span className="step-index">04</span>
              <ShieldCheck size={16} /> Validated assessment
            </div>
          </section>
          {connectionError && (
            <div className="alert error" role="alert">
              {connectionError}
              <button type="button" onClick={() => void connect()}>
                Reconnect
              </button>
            </div>
          )}
          <div className="main-grid">
            <section className="panel input-panel">
              <div className="panel-heading">
                <div className="panel-icon">
                  <Radio size={18} />
                </div>
                <div>
                  <h2>Incident workspace</h2>
                  <p>Start with what you know.</p>
                </div>
                <span className="section-number">01</span>
              </div>
              <form onSubmit={generate}>
                <fieldset disabled={locked}>
                  <div className="input-section">
                    <div className="label-row">
                      <label htmlFor="location">Pilot locality</label>
                      <span>Chennai region</span>
                    </div>
                    <div className="select-wrap">
                      <MapPin size={17} />
                      <select
                        id="location"
                        value={location}
                        onChange={(e) =>
                          changeLocation(e.target.value as Location)
                        }
                      >
                        {locations.map((l) => (
                          <option key={l}>{l}</option>
                        ))}
                      </select>
                      <ChevronDown size={15} />
                    </div>
                    <div className="label-row sample-label">
                      <span>Try a sample incident</span>
                      <span>Synthetic</span>
                    </div>
                    <div className="samples">
                      {scenarios.map((s) => (
                        <button
                          type="button"
                          key={s.id}
                          className={
                            selectedSample === s.id
                              ? "sample selected"
                              : "sample"
                          }
                          onClick={() => loadSample(s)}
                        >
                          <span>{s.input.location}</span>
                          <small>{titles[s.id] || "Sample incident"}</small>
                          {selectedSample === s.id && <Check size={13} />}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="input-section">
                    <div className="label-row">
                      <label htmlFor="report">Field report</label>
                      <span>{report.length.toLocaleString()} / 12,000</span>
                    </div>
                    <textarea
                      id="report"
                      value={report}
                      required
                      minLength={5}
                      maxLength={12000}
                      rows={6}
                      placeholder="Describe what happened, where it happened, and who is affected…"
                      onChange={(e) => {
                        changed();
                        setReport(e.target.value);
                        setSelectedSample(null);
                        if (sourceLabel.includes("development"))
                          setSourceLabel(
                            "edited_development_report_not_live_data",
                          );
                      }}
                    />
                    <p className="input-hint">
                      <FileText size={12} /> Specific observations make better
                      evidence.
                    </p>
                    {sourceLabel.includes("development") && (
                      <p className="sample-notice">
                        Development scenario · not a verified incident
                      </p>
                    )}
                  </div>
                  <div className="input-section environment-section">
                    <div className="label-row">
                      <label>Environmental context</label>
                      <span className="context-tag">
                        {mode === "live"
                          ? "Gridded fallback"
                          : mode === "sample"
                            ? "Synthetic sample"
                            : mode === "manual"
                              ? "Manual · unverified"
                              : "Unknown"}
                      </span>
                    </div>
                    <div className="context-buttons">
                      <button
                        type="button"
                        className={mode === "unknown" ? "active" : ""}
                        onClick={() => changeMode("unknown")}
                      >
                        Unknown
                      </button>
                      <button
                        type="button"
                        className={mode === "manual" ? "active" : ""}
                        onClick={() => changeMode("manual")}
                      >
                        Manual input
                      </button>
                      <button
                        type="button"
                        className={mode === "live" ? "active" : ""}
                        onClick={() => void fetchWeather()}
                      >
                        {weatherBusy ? (
                          <LoaderCircle size={13} className="spin" />
                        ) : (
                          <RefreshCw size={12} />
                        )}{" "}
                        Fetch weather
                      </button>
                    </div>
                    <div className="weather-summary">
                      <div>
                        <CloudRain size={18} />
                        <span>
                          24h rainfall
                          <strong>
                            {environment.rainfall_24h_mm ?? "—"}{" "}
                            <small>mm</small>
                          </strong>
                        </span>
                      </div>
                      <div>
                        <Wind size={18} />
                        <span>
                          Wind speed
                          <strong>
                            {environment.wind_speed_kmph ?? "—"}{" "}
                            <small>km/h</small>
                          </strong>
                        </span>
                      </div>
                      <div>
                        <Thermometer size={18} />
                        <span>
                          Temperature
                          <strong>
                            {environment.temperature_c ?? "—"} <small>°C</small>
                          </strong>
                        </span>
                      </div>
                    </div>
                    <details className="measurements" open={mode === "manual"}>
                      <summary>
                        Measurements & provenance <ChevronDown size={14} />
                      </summary>
                      <div className="measurement-grid">
                        {fields.map((f) => (
                          <label key={f.key}>
                            {f.label}
                            <div className="number-wrap">
                              <input
                                aria-label={f.label}
                                type="number"
                                step="any"
                                min={f.min}
                                max={f.max}
                                readOnly={mode !== "manual"}
                                value={environment[f.key] ?? ""}
                                placeholder="Unknown"
                                onChange={(e) => {
                                  changed();
                                  setEnvironment({
                                    ...environment,
                                    [f.key]:
                                      e.target.value === ""
                                        ? null
                                        : Number(e.target.value),
                                  });
                                }}
                              />
                              <span>{f.unit}</span>
                            </div>
                          </label>
                        ))}
                      </div>
                      {mode === "manual" && (
                        <label className="timestamp-label">
                          Observation time (include timezone)
                          <input
                            value={environment.observed_at ?? ""}
                            placeholder="2026-10-06T09:00:00+05:30"
                            onChange={(e) => {
                              changed();
                              setEnvironment({
                                ...environment,
                                observed_at: e.target.value || null,
                              });
                            }}
                          />
                        </label>
                      )}
                      <dl className="provenance">
                        <dt>Source</dt>
                        <dd>
                          {environment.source_name ||
                            "No environmental source supplied"}
                        </dd>
                        <dt>Observed</dt>
                        <dd>{formatTime(environment.observed_at)}</dd>
                        <dt>Incident time</dt>
                        <dd>{formatTime(timestamp)}</dd>
                      </dl>
                    </details>
                    <p className="source-note">
                      {mode === "live"
                        ? "Open-Meteo modelled weather, not an official station observation. Local water level is unknown. Confirm that current weather is relevant to your report."
                        : mode === "sample"
                          ? "Measurements are synthetic development inputs, not Chennai weather records."
                          : mode === "manual"
                            ? "Entered values are unverified context. Leave unavailable measurements blank."
                            : "Unavailable measurements remain unknown; they are never filled with assumed values."}
                    </p>
                  </div>
                  <div className="input-section model-section">
                    <label htmlFor="provider">Generation model</label>
                    <div className="select-wrap">
                      <Sparkles size={15} />
                      <select
                        id="provider"
                        value={provider}
                        onChange={(e) => {
                          changed();
                          setProvider(e.target.value as Provider);
                        }}
                      >
                        <option value="gemini">Gemini</option>
                        <option value="openai">OpenAI</option>
                        <option value="groq">Groq · free tier</option>
                      </select>
                      <ChevronDown size={15} />
                    </div>
                    <p className="model-note">
                      {health?.providers[provider]?.model ||
                        "Waiting for backend"}{" "}
                      ·{" "}
                      {configured
                        ? "Key configured"
                        : "API key needed on backend"}
                    </p>
                  </div>
                  <div className="generate-area">
                    <button
                      className="generate-button"
                      type="submit"
                      disabled={!configured || report.trim().length < 5}
                    >
                      {busy ? (
                        <>
                          <LoaderCircle size={18} className="spin" /> Generating
                          assessment…
                        </>
                      ) : (
                        <>
                          <Sparkles size={17} /> Generate assessment{" "}
                          <ArrowRight size={17} />
                        </>
                      )}
                    </button>
                    <p>Grounded in your input. Reviewed by you.</p>
                  </div>
                </fieldset>
              </form>
            </section>
            <section
              className="results-column"
              aria-label="Generated assessment"
              aria-busy={busy}
            >
              <div className="results-title">
                <div>
                  <span className="eyebrow">ASSESSMENT OUTPUT</span>
                  <h2>Situation intelligence</h2>
                </div>
                {result && (
                  <button
                    className="export-button"
                    type="button"
                    onClick={download}
                  >
                    <Download size={14} /> Export JSON
                  </button>
                )}
              </div>
              {error && (
                <div className="alert error" role="alert">
                  <TriangleAlert size={18} />
                  <span>{error}</span>
                  <button
                    type="button"
                    aria-label="Dismiss error"
                    onClick={() => setError("")}
                  >
                    <X size={16} />
                  </button>
                </div>
              )}
              {!assessment ? (
                <div className="panel empty-state">
                  <div
                    className={
                      busy
                        ? "signal-illustration generating"
                        : "signal-illustration"
                    }
                  >
                    <div className="orbit orbit-one" />
                    <div className="orbit orbit-two" />
                    <div className="orbit orbit-three" />
                    <span className="signal-dot signal-a" />
                    <span className="signal-dot signal-b" />
                    <span className="signal-dot signal-c" />
                    <div className="signal-core">
                      {busy ? (
                        <LoaderCircle size={34} className="spin" />
                      ) : (
                        <Layers3 size={34} />
                      )}
                    </div>
                  </div>
                  <span className="empty-kicker">
                    {busy
                      ? "GENERATION IN PROGRESS"
                      : "FROM SIGNAL TO UNDERSTANDING"}
                  </span>
                  <h3>
                    {busy
                      ? "Connecting the evidence."
                      : "Every clear response starts\nwith a clear picture."}
                  </h3>
                  <p>
                    {busy
                      ? "The model is assessing your report and supplied context. The response will appear only after structure and locality validation."
                      : "Add a field report and environmental context. CrisisLens will build a structured assessment with supporting evidence and explicit unknowns."}
                  </p>
                  <div className="empty-features">
                    <span>
                      <ShieldCheck size={15} /> Evidence-linked severity
                    </span>
                    <span>
                      <CircleHelp size={15} /> Explicit missing information
                    </span>
                    <span>
                      <FileText size={15} /> Structured situation report
                    </span>
                  </div>
                  <div className="empty-bottom">
                    <ArrowDown size={14} /> Human judgment stays at the centre.
                  </div>
                </div>
              ) : (
                <div className="assessment-content">
                  <div className="assessment-provenance" role="note">
                    <TriangleAlert size={18} />
                    <div>
                      <strong>
                        {result!.input.source_label === "development_example_not_live_data" || result!.input.environment.source_name === "Synthetic development scenario"
                          ? "Synthetic demonstration — not a live incident"
                          : "Assessment of a supplied report — verification required"}
                      </strong>
                      <p>
                        {result!.input.source_label === "development_example_not_live_data"
                          ? "The incident report is fictional. This assessment does not establish that flooding or rainfall is happening in this locality. "
                          : "The report contains supplied claims; generation does not independently confirm the incident. "}
                        {result!.input.environment.source_name === "Synthetic development scenario"
                          ? "Weather values are synthetic demonstration inputs."
                          : result!.input.environment.source_kind === "gridded_weather_fallback"
                            ? "Weather is modelled context from Open-Meteo, not an official local observation or confirmation of this report."
                            : result!.input.environment.source_kind === "manual_development_input"
                              ? "Manually entered environmental values are unverified."
                              : "Confirm environmental observations and their relevance to the incident."}
                      </p>
                      <p>Report time: {formatTime(result!.input.timestamp)} · Context time: {formatTime(result!.input.environment.observed_at)}</p>
                    </div>
                  </div>
                  <article
                    className={`panel assessment-overview severity-${assessment.severity}`}
                  >
                    <div className="overview-top">
                      <span className="location-label">
                        <MapPin size={13} /> {assessment.location}
                      </span>
                      <span className="severity-badge">
                        <i />
                        {assessment.severity} severity
                      </span>
                    </div>
                    <h3>{words(assessment.disaster_type)}</h3>
                    <p>{assessment.situation_report}</p>
                    <div className="generation-meta">
                      <span>
                        <Sparkles size={12} /> {result!.metadata.model}
                      </span>
                      <span>
                        {(result!.metadata.latency_ms / 1000).toFixed(1)}s
                        generation
                      </span>
                      <span>Generated {formatTime(result!.metadata.generated_at)}</span>
                    </div>
                  </article>
                  <article className="panel evidence-panel">
                    <div className="card-heading">
                      <ShieldCheck size={18} />
                      <h3>Why this severity?</h3>
                      <span>
                        {assessment.severity_evidence.length} evidence items
                      </span>
                    </div>
                    {assessment.severity_evidence.map((e, i) => (
                      <div className="evidence-item" key={i}>
                        <span className="evidence-index">
                          {String(i + 1).padStart(2, "0")}
                        </span>
                        <div>
                          <p>{e.statement}</p>
                          <span className="evidence-source">
                            {sourceLabels[e.source] || words(e.source)}
                          </span>
                        </div>
                      </div>
                    ))}
                    <p className="evidence-footnote">
                      Model-generated explanations cite supplied source
                      categories; factual grounding still requires human review.
                    </p>
                  </article>
                  <div className="result-pair">
                    <article className="panel result-card">
                      <h3>Affected groups</h3>
                      <ItemList items={assessment.affected_people} />
                    </article>
                    <article className="panel result-card">
                      <h3>Resources to consider</h3>
                      <ItemList items={assessment.resources_required} />
                    </article>
                  </div>
                  <article className="panel result-card">
                    <div className="card-heading">
                      <Activity size={17} />
                      <h3>Recommended response</h3>
                      <span>For human review</span>
                    </div>
                    <ItemList items={assessment.recommended_actions} numbered />
                  </article>
                  <article className="panel result-card unknowns">
                    <div className="card-heading">
                      <CircleHelp size={18} />
                      <h3>What we still need to know</h3>
                    </div>
                    <ItemList items={assessment.missing_information} />
                  </article>
                  <details className="panel input-snapshot">
                    <summary>
                      <FileText size={15} /> Inspect the exact assessment input{" "}
                      <ChevronDown size={15} />
                    </summary>
                    <pre>{JSON.stringify(result!.input, null, 2)}</pre>
                  </details>
                  <p className="advisory-note">
                    <ShieldCheck size={14} /> Advisory output. No responders
                    have been contacted and no resources dispatched.
                  </p>
                </div>
              )}
            </section>
          </div>
          <footer>
            <span>
              CrisisLens AI <i /> Chennai pilot · V0.4
            </span>
            <span>Tambaram / Chromepet / Velachery</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
