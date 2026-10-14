import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { areas, type Area, type Snapshot, availableReport } from "./types";
const points: Record<Area, [number, number]> = {Velachery: [12.9807,80.2189], Tambaram: [12.9300,80.1100], Chromepet: [12.9516,80.1401]};
export default function AreaMap({area, records, onSelect}: {area: Area; records: Partial<Record<Area, Snapshot>>; onSelect: (area: Area) => void}) {
  const ref = useRef<HTMLDivElement>(null), map = useRef<L.Map | null>(null), markers = useRef<L.Marker[]>([]), callback = useRef(onSelect); callback.current = onSelect;
  useEffect(() => {
    if (!ref.current) return;
    const instance = L.map(ref.current, {scrollWheelZoom: false}).fitBounds(L.latLngBounds(Object.values(points)), {padding:[45,45]}); map.current = instance;
    const tiles = L.tileLayer(import.meta.env.VITE_MAP_TILE_URL || "https://tile.openstreetmap.org/{z}/{x}/{y}.png", {maxZoom:19, attribution: import.meta.env.VITE_MAP_ATTRIBUTION || '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(instance);
    const observer = new ResizeObserver(() => instance.invalidateSize()); observer.observe(ref.current);
    tiles.on("tileerror", () => ref.current?.setAttribute("data-tile-error", "true"));
    return () => {observer.disconnect(); instance.remove(); map.current = null;};
  }, []);
  useEffect(() => {
    if (!map.current) return;
    markers.current.forEach(marker => marker.remove());
    markers.current = areas.map(place => {
      const count = records[place]?.reports.filter(r => availableReport(r) && (!!r.needs || !!r.resources?.length)).length;
      const label = count === undefined ? "Status unavailable" : count ? `${count} reviewed request${count === 1 ? "" : "s"}` : "No reviewed requests";
      return L.marker(points[place], {keyboard:true, title:`Select ${place}`, icon:L.divIcon({className:"need-map-pin", html:`<div class="${place === area ? "selected" : ""}"><b>${place}</b><span>${label}</span></div>`, iconSize:[138,48], iconAnchor:[69,48]})}).addTo(map.current!).on("click", () => callback.current(place));
    });
  }, [area, records]);
  useEffect(() => {map.current?.panTo(points[area], {animate: true});}, [area]);
  return <section className="area-map" aria-label="Chennai locality map"><div className="map-canvas" ref={ref}/><div className="map-caption"><span>Chennai pilot · locality centres</span><span>Markers show report counts, not flood risk.</span></div><div className="map-area-tabs">{areas.map(place => <button key={place} aria-pressed={place === area} onClick={() => onSelect(place)}>{place}</button>)}</div></section>;
}
