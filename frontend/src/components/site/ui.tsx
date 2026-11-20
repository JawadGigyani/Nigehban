"use client";

import { ArrowRight, Bell, Check, Droplets, Info, LocateFixed, MapPin, Menu, Phone, Route, Search, SendHorizontal, TriangleAlert, Volume2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { api, LEVEL_COLORS, type Lang, type Level, type Place, type RiskDay } from "@/lib/api";
import { S } from "@/lib/copy";
import { LEVEL_NAMES, T, dayLabel } from "@/lib/i18n";
import { placeLabel } from "@/lib/site";

const I = { strokeWidth: 1.75, "aria-hidden": true } as const;

export const Icon = {
  search: <Search {...I} />,
  pin: <MapPin {...I} />,
  locate: <LocateFixed {...I} />,
  arrow: <ArrowRight {...I} className="flip-rtl" />,
  menu: <Menu {...I} />,
  close: <X {...I} />,
  phone: <Phone {...I} />,
  check: <Check {...I} />,
  info: <Info {...I} />,
  alert: <TriangleAlert {...I} />,
  bell: <Bell {...I} />,
  send: <SendHorizontal {...I} className="flip-rtl" />,
  speaker: <Volume2 {...I} />,
  route: <Route {...I} />,
  drop: <Droplets {...I} />,
};

/** Mark: a mountain ridge above a wave, inside a ring. */
export function Logo({ withUrdu = true }: { withUrdu?: boolean }) {
  return (
    <span className="logo">
      <svg viewBox="0 0 32 32" aria-hidden="true">
        <circle cx="16" cy="16" r="15" fill="#0e5e66" />
        <path d="M6.5 17.5 12 10l3.2 4.2L18.5 9l7 8.5" fill="none" stroke="#fff" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        <path d="M7 22c1.5-1.3 3-1.3 4.5 0s3 1.3 4.5 0 3-1.3 4.5 0 3 1.3 4.5 0" fill="none" stroke="#9fd6cf" strokeWidth="2" strokeLinecap="round" />
      </svg>
      Nigehban
      {withUrdu && <span className="ur-name">نگہبان</span>}
    </span>
  );
}

export function LevelBadge({ level, lang }: { level: Level; lang: Lang }) {
  return <span className={`badge ${level}`}><i className="chip" style={{ background: LEVEL_COLORS[level], width: 8, height: 8, borderRadius: 4 }} />{LEVEL_NAMES[lang][level]}</span>;
}

export function dayShort(lang: Lang, date: string, lead: number) {
  if (lead <= 1) return dayLabel(lang, lead);
  return new Date(`${date}T00:00:00`).toLocaleDateString(lang === "ur" ? "ur-PK" : "en-GB", { weekday: "short" });
}

/** Four coloured day blocks (today + 3). */
export function LevelStrip({ days, lang, focus }: { days: RiskDay[]; lang: Lang; focus?: number }) {
  return (
    <div className="strip">
      {days.map((d) => (
        <div key={d.date} className={`d ${focus === d.lead_days ? "focus" : ""}`}>
          {dayShort(lang, d.date, d.lead_days)}
          <b style={{ background: LEVEL_COLORS[d.level] }} title={LEVEL_NAMES[lang][d.level]} />
        </div>
      ))}
    </div>
  );
}

/** Village / town / tehsil search with keyboard support. */
export function PlaceSearch({ lang, onPick, flat = false, placeholder, cta, inputId }: {
  lang: Lang; onPick: (p: Place) => void; flat?: boolean; placeholder?: string; cta?: string; inputId?: string;
}) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Place[]>([]);
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (q.trim().length < 2) { setHits([]); return; }
    const id = setTimeout(() => api.search(q.trim()).then((h) => { setHits(h); setActive(0); setOpen(true); }).catch(() => setHits([])), 220);
    return () => clearTimeout(id);
  }, [q]);
  useEffect(() => {
    const h = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const pick = (p: Place) => { onPick(p); setQ(""); setHits([]); setOpen(false); };
  return (
    <div className={`search ${flat ? "flat" : ""}`} ref={box}>
      <form className="search-box" onSubmit={(e) => { e.preventDefault(); if (hits[active]) pick(hits[active]); }}>
        {Icon.search}
        <input id={inputId} value={q} onChange={(e) => setQ(e.target.value)} onFocus={() => hits.length && setOpen(true)}
          placeholder={placeholder ?? T[lang].search_place} aria-label={placeholder ?? T[lang].search_place}
          role="combobox" aria-expanded={open && hits.length > 0} aria-controls="place-results" autoComplete="off"
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, hits.length - 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
            if (e.key === "Escape") setOpen(false);
          }} />
        {cta && <button className="btn" type="submit" onClick={(e) => { if (!hits[active]) { e.preventDefault(); box.current?.querySelector("input")?.focus(); } }}>{cta}</button>}
      </form>
      {open && hits.length > 0 && (
        <div className="results" id="place-results" role="listbox">
          {hits.map((p, i) => (
            <button key={p.id} type="button" role="option" aria-selected={i === active} className={i === active ? "active" : ""}
              onMouseEnter={() => setActive(i)} onClick={() => pick(p)}>
              <span>{placeLabel(p, lang)}</span>
              <span className="kind">{p.type === "tehsil" ? S[lang].kind_tehsil : S[lang].kind_village}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
