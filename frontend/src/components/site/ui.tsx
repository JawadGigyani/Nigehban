"use client";

import { useEffect, useRef, useState } from "react";

import { api, LEVEL_COLORS, type Lang, type Level, type Place, type RiskDay } from "@/lib/api";
import { S } from "@/lib/copy";
import { LEVEL_NAMES, T, dayLabel } from "@/lib/i18n";
import { placeLabel } from "@/lib/site";

const P = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

export const Icon = {
  search: <svg viewBox="0 0 24 24" {...P}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>,
  pin: <svg viewBox="0 0 24 24" {...P}><path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z" /><circle cx="12" cy="9.5" r="2.5" /></svg>,
  locate: <svg viewBox="0 0 24 24" {...P}><circle cx="12" cy="12" r="7" /><circle cx="12" cy="12" r="2.5" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></svg>,
  arrow: <svg viewBox="0 0 24 24" {...P}><path d="M5 12h14M13 6l6 6-6 6" /></svg>,
  menu: <svg viewBox="0 0 24 24" {...P}><path d="M4 7h16M4 12h16M4 17h16" /></svg>,
  close: <svg viewBox="0 0 24 24" {...P}><path d="M6 6l12 12M18 6 6 18" /></svg>,
  phone: <svg viewBox="0 0 24 24" {...P}><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2" /></svg>,
  check: <svg viewBox="0 0 24 24" {...P}><path d="m5 12.5 4.5 4.5L19 7.5" /></svg>,
  info: <svg viewBox="0 0 24 24" {...P}><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></svg>,
  alert: <svg viewBox="0 0 24 24" {...P}><path d="M12 3 2 20h20L12 3z" /><path d="M12 10v4M12 17h.01" /></svg>,
  bell: <svg viewBox="0 0 24 24" {...P}><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0" /></svg>,
  send: <svg viewBox="0 0 24 24" {...P}><path d="M5 12h13M12 5l7 7-7 7" /></svg>,
  speaker: <svg viewBox="0 0 24 24" {...P}><path d="M4 9v6h4l5 4V5L8 9H4z" /><path d="M16.5 8.5a5 5 0 0 1 0 7" /></svg>,
  route: <svg viewBox="0 0 24 24" {...P}><circle cx="6" cy="18" r="2.5" /><circle cx="18" cy="6" r="2.5" /><path d="M8.5 18H15a3 3 0 0 0 0-6H9a3 3 0 0 1 0-6h6.5" /></svg>,
  drop: <svg viewBox="0 0 24 24" {...P}><path d="M12 3c-3 4.5-6 7.7-6 11a6 6 0 0 0 12 0c0-3.3-3-6.5-6-11z" /></svg>,
};

/** A number that counts up from 0 the first time it is shown (instant with reduced motion). */
export function CountUp({ value, ms = 900 }: { value: number; ms?: number }) {
  const [shown, setShown] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    let raf = 0;
    const el = ref.current;
    const run = () => {
      const t0 = performance.now();
      const tick = (t: number) => {
        const p = Math.min(1, (t - t0) / ms);
        setShown(Math.round(value * (1 - Math.pow(1 - p, 3))));
        if (p < 1) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    };
    if (!el || !("IntersectionObserver" in window)) { run(); return; }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { io.disconnect(); run(); } });
    io.observe(el);
    return () => { io.disconnect(); cancelAnimationFrame(raf); };
  }, [value, ms]);
  return <span ref={ref} className="tabular">{shown}</span>;
}

/** Mark: a mountain ridge above a wave, inside a ring. */
export function Logo({ withUrdu = true }: { withUrdu?: boolean }) {
  return (
    <span className="logo">
      <svg viewBox="0 0 32 32" aria-hidden="true">
        <circle cx="16" cy="16" r="15" fill="#0e5e66" />
        <path d="M6.5 17.5 12 10l3.2 4.2L18.5 9l7 8.5" fill="none" stroke="#fff" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        <path className="logo-wave" d="M7 22c1.5-1.3 3-1.3 4.5 0s3 1.3 4.5 0 3-1.3 4.5 0 3 1.3 4.5 0" fill="none" stroke="#9fd6cf" strokeWidth="2" strokeLinecap="round" />
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
export function PlaceSearch({ lang, onPick, flat = false, placeholder, cta }: {
  lang: Lang; onPick: (p: Place) => void; flat?: boolean; placeholder?: string; cta?: string;
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
        <input value={q} onChange={(e) => setQ(e.target.value)} onFocus={() => hits.length && setOpen(true)}
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
