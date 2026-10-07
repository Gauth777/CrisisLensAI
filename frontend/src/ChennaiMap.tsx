import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import type { OperationsSnapshot } from "./OperationsPanel";
import "leaflet/dist/leaflet.css";
import { CloudRain, ExternalLink, History, LocateFixed, RefreshCw } from "lucide-react";
import { localCases, type PilotArea } from "./data/pastTrends";

export type MapContext = { location: PilotArea; retrieved_at: string; outlook: null | { environment: { temperature_c: number | null; wind_speed_kmph: number | null; observed_at: string }; hours: { time: string; precipitation_mm: number | null; probability_percent: number | null }[]; next_rain: { time: string; precipitation_mm: number | null; probability_percent: number | null } | null; forecast_complete: boolean }; sources: { kind: string; url: string | null }[] };
const points: Record<PilotArea, [number, number]> = { Velachery: [12.9807, 80.2189], Tambaram: [12.9300, 80.1100], Chromepet: [12.9516, 80.1401] };
const areas = Object.keys(points) as PilotArea[];
const stamp = (value?: string) => value ? new Date(value).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) + " IST" : "Not available";
function totalRain(context?: MapContext) {
  const outlook = context?.outlook;
  if (!outlook?.forecast_complete || outlook.hours.length !== 24 || outlook.hours.some(hour => typeof hour.precipitation_mm !== "number" || !Number.isFinite(hour.precipitation_mm))) return null;
  return Math.round(outlook.hours.reduce((sum, hour) => sum + hour.precipitation_mm!, 0) * 10) / 10;
}
export default function ChennaiMap({ operations, area, selectedContext, disabled, onAreaSelect, onHistory }: { operations: OperationsSnapshot | null; area: PilotArea; selectedContext: MapContext | null; disabled: boolean; onAreaSelect: (area: PilotArea) => void; onHistory: () => void }) {
  const containerRef = useRef<HTMLDivElement>(null), mapRef = useRef<L.Map | null>(null), markerRef = useRef<Partial<Record<PilotArea, L.Marker>>>({});
  const selectRef = useRef(onAreaSelect), disabledRef = useRef(disabled);
  selectRef.current = onAreaSelect; disabledRef.current = disabled;
  const [records, setRecords] = useState<Partial<Record<PilotArea, MapContext>>>({}), [layer, setLayer] = useState<"weather" | "history">("weather");
  const [pending, setPending] = useState(false), [refresh, setRefresh] = useState(0), [tilesUnavailable, setTilesUnavailable] = useState(false), [uncoveredPoint, setUncoveredPoint] = useState(false);
  useEffect(() => {
    if (selectedContext?.location === area) setRecords(previous => ({ ...previous, [area]: selectedContext }));
  }, [area, selectedContext]);
  useEffect(() => {
    const controller = new AbortController();
    async function collect(force = false) {
      if (document.visibilityState === "hidden") return;
      setPending(true);
      await Promise.all(areas.map(async location => {
        try {
          const response = await fetch(`/api/context/${location}${force ? "?refresh=true" : ""}`, { signal: controller.signal });
          if (!response.ok) throw new Error("Context unavailable");
          const data: MapContext = await response.json();
          if (data.location !== location) throw new Error("Locality mismatch");
          if (!controller.signal.aborted) setRecords(previous => ({ ...previous, [location]: data }));
        } catch {
          if (!controller.signal.aborted) setRecords(previous => { const next = { ...previous }; delete next[location]; return next; });
        }
      }));
      if (!controller.signal.aborted) setPending(false);
    }
    void collect(refresh > 0);
    const timer = window.setInterval(() => void collect(), 300000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [refresh]);
  useEffect(() => {
    if (!containerRef.current) return;
    const map = L.map(containerRef.current, { scrollWheelZoom: false, zoomControl: true, minZoom: 8, maxZoom: 18 }).setView([13.005, 80.185], 11);
    mapRef.current = map;
    const tileUrl = import.meta.env.VITE_MAP_TILE_URL || "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
    const attribution = import.meta.env.VITE_MAP_ATTRIBUTION || '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
    const tiles = L.tileLayer(tileUrl, { maxZoom: 19, attribution, referrerPolicy: "strict-origin-when-cross-origin" }).addTo(map);
    tiles.on("tileerror", () => setTilesUnavailable(true));
    tiles.on("tileload", () => setTilesUnavailable(false));
    for (const location of areas) {
      const marker = L.marker(points[location], { keyboard: true, title: location, icon: L.divIcon({ className: "pilot-map-marker", html: `<span class="marker-label"><strong>${location}</strong><small>Rain: unknown</small></span>`, iconSize: [122, 48], iconAnchor: [61, 48] }) }).addTo(map);
      marker.on("click", () => { setUncoveredPoint(false); if (!disabledRef.current) selectRef.current(location); });
      markerRef.current[location] = marker;
    }
    map.on("click", () => setUncoveredPoint(true));
    const observer = new ResizeObserver(() => map.invalidateSize()); observer.observe(containerRef.current);
    return () => { observer.disconnect(); map.remove(); mapRef.current = null; markerRef.current = {}; };
  }, []);
  useEffect(() => {
    for (const location of areas) {
      const amount = totalRain(records[location]);
      const label = layer === "history" ? "Past flood · 2023" : amount === null ? "Rain: unknown" : `${amount} mm / 24h`;
      const icon = L.divIcon({ className: "pilot-map-marker", html: `<span class="marker-label ${layer === "history" ? "historical" : "forecast"} ${area === location ? "selected" : ""}"><strong>${location}</strong><small>${label}</small></span>`, iconSize: [122, 48], iconAnchor: location === "Tambaram" ? [61, 0] : [61, 48] });
      markerRef.current[location]?.setIcon(icon);
      markerRef.current[location]?.getElement()?.setAttribute("aria-label", `Map area: ${location}`);
    }
  }, [area, records, layer]);
  useEffect(() => { mapRef.current?.panTo(points[area], { animate: false }); setUncoveredPoint(false); }, [area]);
  const record = records[area], rain = totalRain(record), outlook = record?.outlook;
  const weatherUrl = record?.sources.find(source => source.kind === "weather")?.url;
  return <section className="chennai-map-card" aria-label="Interactive Chennai map"><div className="map-toolbar"><div className="map-layer-buttons"><button aria-pressed={layer === "weather"} onClick={() => setLayer("weather")}><CloudRain size={13}/> Live weather</button><button aria-pressed={layer === "history"} onClick={() => setLayer("history")}><History size={13}/> Past flooding</button></div><button className="map-icon-button" aria-label="Recenter Chennai map" onClick={() => { mapRef.current?.fitBounds(L.latLngBounds(areas.map(location => points[location])).pad(0.35), { animate: false }); setUncoveredPoint(false); }}><LocateFixed size={17}/></button></div><div className="map-legend">{layer === "weather" ? "Weather context · incident risk unverified" : "Historical flood records · not current incidents"}</div><div className="chennai-map-canvas" ref={containerRef} role="region" aria-label="Chennai street map. Drag to pan; use plus and minus to zoom."/>{tilesUnavailable && <p className="map-tile-error" role="status">Map tiles unavailable. Area data remains below.</p>}<div className="map-selection-tabs" aria-label="Map localities">{areas.map(location => <button key={location} disabled={disabled} aria-pressed={area === location} onClick={() => { setUncoveredPoint(false); onAreaSelect(location); }}>{location}</button>)}</div>{uncoveredPoint && <p className="map-coverage-gap" role="status">No incident coverage at this point. Choose a pilot marker.</p>}<div className="map-area-data"><div className="map-data-heading"><strong>{area}</strong><button aria-label="Refresh map data" disabled={pending} onClick={() => setRefresh(value => value + 1)}><RefreshCw size={13} className={pending ? "spin" : ""}/>{pending ? "Updating" : "Refresh"}</button></div>{layer === "weather" ? <><div className="map-weather-values"><div><span>Forecast · next 24h</span><strong>{rain === null ? "Unknown" : `${rain} mm`}</strong></div><div><span>Temperature</span><strong>{outlook?.environment.temperature_c === null || !outlook ? "Unknown" : `${outlook.environment.temperature_c} °C`}</strong></div></div><p className="map-data-time">Modelled · observed {stamp(outlook?.environment.observed_at)}</p>{weatherUrl && <a href={weatherUrl} target="_blank" rel="noopener noreferrer" className="map-source-link">Open weather source <ExternalLink size={12}/></a>}</> : <><p className="map-history-label">Flooding documented · December 2023</p><p className="map-history-title">{localCases[area].title}</p><button className="map-source-link" onClick={onHistory}>Past signals & original sources <ExternalLink size={12}/></button></>}<div className="map-risk-status"><strong>Current incident risk: unverified</strong><span>Rain is context, not flood probability. Check local conditions.</span></div></div><div className="map-official-status" style={{padding:"10px 16px",fontSize:12,borderTop:"1px solid #e1e8e3"}}>{operations?.location === area && !operations.feed.stale ? `${operations.alerts.filter(a => a.state === "active").length} active district warning(s) · see official records below` : "Official warning status: checking or unavailable"}</div><div className="map-footer"><span>3 pilot points · representative locations</span><span>Weather refreshes every 5 min while visible</span><a href="https://www.openstreetmap.org/fixthemap" target="_blank" rel="noopener noreferrer">Map issue?</a></div></section>;
}
