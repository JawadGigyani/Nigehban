"use client";

import { useEffect, useMemo, useState } from "react";

import { api, LEVEL_ORDER, type Level, type ObservedRain, type RiskResponse, type TehsilDetail, type TehsilRisk } from "./api";

// Tiny in-memory cache so moving between pages doesn't refetch the same day.
const cache = new Map<string, Promise<unknown>>();
function cached<T>(key: string, fn: () => Promise<T>): Promise<T> {
  if (!cache.has(key)) cache.set(key, fn().catch((e) => { cache.delete(key); throw e; }));
  return cache.get(key) as Promise<T>;
}

export function useGeo() {
  const [geo, setGeo] = useState<GeoJSON.FeatureCollection | null>(null);
  useEffect(() => { cached("geo", api.tehsils).then(setGeo).catch(() => setGeo(null)); }, []);
  return geo;
}

export function useRisk(asOf: string | null) {
  const [risk, setRisk] = useState<RiskResponse | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let live = true;
    setRisk(null); setError(false);
    cached(`risk:${asOf}`, () => api.risk(asOf)).then((r) => live && setRisk(r)).catch(() => live && setError(true));
    return () => { live = false; };
  }, [asOf]);
  return { risk, error };
}

export function useRain(asOf: string | null) {
  const [rain, setRain] = useState<ObservedRain | null>(null);
  useEffect(() => {
    let live = true;
    setRain(null);
    cached(`rain:${asOf}`, () => api.rain(asOf)).then((r) => live && setRain(r)).catch(() => live && setRain(null));
    return () => { live = false; };
  }, [asOf]);
  return rain;
}

export function useTehsil(id: string | null | undefined, asOf: string | null) {
  const [detail, setDetail] = useState<TehsilDetail | null>(null);
  useEffect(() => {
    let live = true;
    setDetail(null);
    if (id) cached(`tehsil:${id}:${asOf}`, () => api.tehsil(id, asOf)).then((d) => live && setDetail(d)).catch(() => live && setDetail(null));
    return () => { live = false; };
  }, [id, asOf]);
  return detail;
}

export const levelAt = (r: TehsilRisk, lead: number) => r.days.find((d) => d.lead_days === lead);

/** Tehsils sorted by level, then probability, for one lead day. */
/** Highest level first, then highest probability, for one lead day. */
export function rankTehsils(rows: TehsilRisk[], lead: number): TehsilRisk[] {
  return [...rows].sort((a, b) => {
    const da = levelAt(a, lead), db = levelAt(b, lead);
    return (LEVEL_ORDER.indexOf(db?.level ?? "low") - LEVEL_ORDER.indexOf(da?.level ?? "low"))
      || ((db?.probability ?? 0) - (da?.probability ?? 0));
  });
}

export function useRanked(risk: RiskResponse | null, lead: number) {
  return useMemo(() => (risk ? rankTehsils(risk.tehsils, lead) : []), [risk, lead]);
}

export function countLevels(rows: TehsilRisk[], lead: number) {
  const c: Record<Level, number> = { low: 0, moderate: 0, high: 0, very_high: 0 };
  rows.forEach((r) => { const d = levelAt(r, lead); if (d) c[d.level] += 1; });
  return c;
}
