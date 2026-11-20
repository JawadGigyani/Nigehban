"use client";

// Shared website state: language, replay date, chosen place, alert subscription, device id.
// Kept in localStorage so it survives page changes and reloads (falls back to memory).

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import type { Lang, Place } from "./api";
import { isRtl } from "./i18n";

export const REPLAYS: { asOf: string; key: "replay_buner" | "replay_swat" }[] = [
  { asOf: "2025-08-14T09:00:00+05:00", key: "replay_buner" },
  { asOf: "2025-06-26T09:00:00+05:00", key: "replay_swat" },
];

export function load<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(`nigehban:${key}`);
    return v === null ? fallback : (JSON.parse(v) as T);
  } catch {
    return fallback;
  }
}
export function save(key: string, value: unknown) {
  try {
    localStorage.setItem(`nigehban:${key}`, JSON.stringify(value));
  } catch {
    /* private mode: settings last for this visit only */
  }
}
function randomId() {
  const a = new Uint8Array(16);
  crypto.getRandomValues(a);
  return "dev-" + Array.from(a, (b) => b.toString(16).padStart(2, "0")).join("");
}

interface SiteState {
  ready: boolean;
  lang: Lang;
  setLang: (l: Lang) => void;
  asOf: string | null;
  setAsOf: (v: string | null) => void;
  place: Place | null;
  setPlace: (p: Place | null) => void;
  places: Place[];
  setPlaces: (p: Place[]) => void;
  subId: string | null;
  setSubId: (v: string | null) => void;
  deviceId: string;
  resetDevice: () => void;
}

const Ctx = createContext<SiteState | null>(null);

export function SiteProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [lang, setLangS] = useState<Lang>("en");
  const [asOf, setAsOfS] = useState<string | null>(null);
  const [place, setPlaceS] = useState<Place | null>(null);
  const [places, setPlacesS] = useState<Place[]>([]);
  const [subId, setSubIdS] = useState<string | null>(null);
  const [deviceId, setDeviceId] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlLang = params.get("lang");
    const stored = load<Lang>("lang", "en");
    setLangS(urlLang === "ur" || urlLang === "en" ? urlLang : stored === "ur" ? "ur" : "en"); // English or Urdu only
    setAsOfS(load<string | null>("asOf", null));
    setPlaceS(load<Place | null>("place", null));
    setPlacesS(load<Place[]>("places", []));
    setSubIdS(load<string | null>("sub", null));
    let id = load<string>("device", "");
    if (!id) { id = randomId(); save("device", id); }
    setDeviceId(id);
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => null);
    setReady(true);
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang === "en" ? "en" : "ur";
    document.documentElement.dir = isRtl(lang) ? "rtl" : "ltr";
    document.body.classList.toggle("ur", lang === "ur");
  }, [lang]);

  const setLang = useCallback((l: Lang) => { setLangS(l); save("lang", l); }, []);
  const setAsOf = useCallback((v: string | null) => { setAsOfS(v); save("asOf", v); }, []);
  const setPlace = useCallback((p: Place | null) => { setPlaceS(p); save("place", p); }, []);
  const setPlaces = useCallback((p: Place[]) => { setPlacesS(p); save("places", p); }, []);
  const setSubId = useCallback((v: string | null) => { setSubIdS(v); save("sub", v); }, []);
  const resetDevice = useCallback(() => {
    const id = randomId();
    save("device", id); setDeviceId(id); setPlacesS([]); save("places", []);
  }, []);

  const value = useMemo(() => ({ ready, lang, setLang, asOf, setAsOf, place, setPlace, places, setPlaces, subId, setSubId, deviceId, resetDevice }),
    [ready, lang, setLang, asOf, setAsOf, place, setPlace, places, setPlaces, subId, setSubId, deviceId, resetDevice]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSite(): SiteState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useSite outside SiteProvider");
  return v;
}

export function placeLabel(p: Place, lang: Lang) {
  if (lang === "ur" && p.label_ur) return p.label_ur;
  return p.type === "village" && p.tehsil ? `${p.name}, ${p.tehsil}` : p.name;
}
