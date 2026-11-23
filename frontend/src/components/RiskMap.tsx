"use client";

import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";

import { LEVEL_COLORS, RAIN_STEPS, type Level, type ObservedRain, type TehsilRisk } from "@/lib/api";

export interface MapMarker {
  lon: number;
  lat: number;
  color: string;
  label: string;
}

interface Props {
  geojson: GeoJSON.FeatureCollection | null;
  risk: TehsilRisk[];
  lead: number;
  selected: string | null;
  onSelect: (tehsilId: string) => void;
  markers?: MapMarker[];
  height?: string;
  /** "rain" shows satellite rain already fallen instead of the forecast levels. */
  mode?: "risk" | "rain";
  rain?: ObservedRain | null;
  /** Page-scroll friendly: two fingers / ctrl+scroll to move the map. */
  cooperative?: boolean;
  flyOnSelect?: boolean;
}

const RAIN_COLOR = [
  "step", ["get", "mm"], RAIN_STEPS[0].color,
  ...RAIN_STEPS.slice(1).flatMap((s) => [s.min, s.color]),
] as unknown as maplibregl.ExpressionSpecification;

const STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
      maxzoom: 18,
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm", paint: { "raster-saturation": -0.6, "raster-opacity": 0.85 } }],
};

// MapLibre cancels its own in-flight tile and data work when the map's data is replaced quickly
// (date or day switches). In this version the cancellation can surface as an unhandled
// "AbortError: signal is aborted without reason". It is harmless, so it is swallowed here.
if (typeof window !== "undefined" && !(window as unknown as { __nigehbanAbortGuard?: boolean }).__nigehbanAbortGuard) {
  (window as unknown as { __nigehbanAbortGuard?: boolean }).__nigehbanAbortGuard = true;
  const isAbort = (r: unknown) => !!r && typeof r === "object" && (r as { name?: string }).name === "AbortError";
  window.addEventListener("unhandledrejection", (e) => {
    if (isAbort(e.reason)) { e.preventDefault(); e.stopImmediatePropagation(); }
  }, { capture: true });
  window.addEventListener("error", (e) => {
    if (isAbort(e.error)) { e.preventDefault(); e.stopImmediatePropagation(); }
  }, { capture: true });
}

/** Tehsil choropleth coloured by the model's level for the chosen lead day. */
export default function RiskMap({ geojson, risk, lead, selected, onSelect, markers = [], height = "100%", mode = "risk", rain = null, cooperative = false, flyOnSelect = true }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const ready = useRef(false);
  const markerObjs = useRef<maplibregl.Marker[]>([]);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  useEffect(() => {
    if (!container.current || map.current) return;
    const m = new maplibregl.Map({ container: container.current, style: STYLE, center: [72.4, 35.0], zoom: 7.2, cooperativeGestures: cooperative, attributionControl: { compact: true } });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    // Add layers as soon as the style is parsed; "load" waits for every base-map tile and can stall.
    m.once("style.load", () => {
      ready.current = true;
      m.addSource("tehsils", { type: "geojson", data: { type: "FeatureCollection", features: [] }, promoteId: "tehsil_id" });
      m.addLayer({
        id: "tehsil-fill", type: "fill", source: "tehsils",
        paint: { "fill-color": ["coalesce", ["get", "color"], "#cccccc"], "fill-opacity": 0.62 },
      });
      m.addSource("rain", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      m.addLayer({
        id: "rain-cells", type: "fill", source: "rain",
        layout: { visibility: "none" },
        paint: { "fill-color": RAIN_COLOR, "fill-opacity": 0.75 },
      });
      m.addLayer({
        id: "tehsil-line", type: "line", source: "tehsils",
        paint: {
          "line-color": ["case", ["boolean", ["feature-state", "selected"], false], "#111111", "#ffffff"],
          "line-width": ["case", ["boolean", ["feature-state", "selected"], false], 3, 1],
        },
      });
      m.on("click", "tehsil-fill", (e) => {
        const id = e.features?.[0]?.properties?.tehsil_id;
        if (id) onSelectRef.current(id);
      });
      m.on("mouseenter", "tehsil-fill", () => (m.getCanvas().style.cursor = "pointer"));
      m.on("mouseleave", "tehsil-fill", () => (m.getCanvas().style.cursor = ""));
      m.fire("nigehban:ready");
    });
    map.current = m;
    return () => {
      m.remove();
      map.current = null;
      ready.current = false;
    };
  }, []);

  // Colour tehsils by level for the chosen lead day.
  useEffect(() => {
    const m = map.current;
    if (!m || !geojson) return;
    const apply = () => {
      const byId = new Map(risk.map((r) => [r.tehsil_id, r]));
      const features = geojson.features.map((f) => {
        const r = byId.get(String(f.properties?.tehsil_id));
        const day = r?.days.find((d) => d.lead_days === lead);
        const level: Level | undefined = day?.level;
        return { ...f, properties: { ...f.properties, level: level ?? null, color: level ? LEVEL_COLORS[level] : null } };
      });
      (m.getSource("tehsils") as maplibregl.GeoJSONSource | undefined)?.setData({ type: "FeatureCollection", features });
    };
    if (ready.current) apply();
    else m.once("nigehban:ready", apply);
  }, [geojson, risk, lead]);

  // Observed-rain layer: 0.1° satellite cells; forecast colours fade out while it is shown.
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const apply = () => {
      const half = (rain?.cell_size_deg ?? 0.1) / 2;
      const features: GeoJSON.Feature[] = (rain?.cells ?? []).map((c) => ({
        type: "Feature", properties: { mm: c.mm },
        geometry: { type: "Polygon", coordinates: [[[c.lon - half, c.lat - half], [c.lon + half, c.lat - half],
          [c.lon + half, c.lat + half], [c.lon - half, c.lat + half], [c.lon - half, c.lat - half]]] },
      }));
      (m.getSource("rain") as maplibregl.GeoJSONSource | undefined)?.setData({ type: "FeatureCollection", features });
      m.setLayoutProperty("rain-cells", "visibility", mode === "rain" ? "visible" : "none");
      m.setPaintProperty("tehsil-fill", "fill-opacity", mode === "rain" ? 0.08 : 0.62);
    };
    if (ready.current) apply();
    else m.once("nigehban:ready", apply);
  }, [rain, mode]);

  // Highlight and fly to the selected tehsil.
  useEffect(() => {
    const m = map.current;
    if (!m || !geojson) return;
    const apply = () => {
      geojson.features.forEach((f) => {
        const id = String(f.properties?.tehsil_id);
        m.setFeatureState({ source: "tehsils", id }, { selected: id === selected });
      });
      const f = geojson.features.find((x) => x.properties?.tehsil_id === selected);
      if (f && f.properties && flyOnSelect) m.flyTo({ center: [f.properties.centroid_lon, f.properties.centroid_lat], zoom: 9.2, speed: 1.4 });
    };
    if (ready.current) apply();
    else m.once("nigehban:ready", apply);
  }, [selected, geojson, flyOnSelect]);

  // Point markers (shelters, Rescue 1122, high-exposure villages).
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    markerObjs.current.forEach((mk) => mk.remove());
    markerObjs.current = markers.map((mk) => {
      const el = document.createElement("div");
      el.className = "map-dot";
      el.style.background = mk.color;
      el.title = mk.label;
      return new maplibregl.Marker({ element: el }).setLngLat([mk.lon, mk.lat])
        .setPopup(new maplibregl.Popup({ offset: 8 }).setText(mk.label)).addTo(m);
    });
  }, [markers]);

  return <div ref={container} style={{ width: "100%", height }} className="risk-map" />;
}
