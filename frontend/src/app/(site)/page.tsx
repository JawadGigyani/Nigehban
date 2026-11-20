"use client";

import {
  BellRing, CircleCheck, CloudRain, Eye, History, Info, Languages, Map as MapIcon, MapPin, MessageCircle,
  Mountain, Phone, RefreshCw, Siren, TriangleAlert, Wallet, type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import RiskMap from "@/components/RiskMap";
import { Icon, PlaceSearch, dayShort } from "@/components/site/ui";
import { LEVEL_COLORS, LEVEL_ORDER, type Level } from "@/lib/api";
import { ADVICE, S } from "@/lib/copy";
import { levelAt, useGeo, useRanked, useRisk } from "@/lib/hooks";
import { LEVEL_NAMES } from "@/lib/i18n";
import { tehsilName, tehsilPlace } from "@/lib/places";
import { useSite } from "@/lib/site";

const I = { strokeWidth: 1.75, "aria-hidden": true } as const;
const LEVEL_ICON: Record<Level, LucideIcon> = { low: CircleCheck, moderate: Eye, high: TriangleAlert, very_high: Siren };

function Outlook() {
  const { lang, asOf, setPlace } = useSite();
  const s = S[lang];
  const router = useRouter();
  const geo = useGeo();
  const { risk, error } = useRisk(asOf);
  const [lead, setLead] = useState(1);
  const ranked = useRanked(risk, lead);
  const high = ranked.filter((r) => { const l = levelAt(r, lead)?.level; return l === "high" || l === "very_high"; });

  const open = (id: string) => {
    const r = risk?.tehsils.find((x) => x.tehsil_id === id);
    if (r) { setPlace(tehsilPlace(r, geo)); router.push("/area"); }
  };

  return (
    <div className="outlook window">
      <div className="window-bar">
        <span className="ol-title">{s.today_across}</span>
        <div className="seg" role="group" aria-label="Day" style={{ marginInlineStart: "auto" }}>
          {(risk?.tehsils[0]?.days ?? []).map((d) => (
            <button key={d.lead_days} className={lead === d.lead_days ? "on" : ""} aria-pressed={lead === d.lead_days}
              onClick={() => setLead(d.lead_days)}>{dayShort(lang, d.date, d.lead_days)}</button>
          ))}
        </div>
      </div>
      <div className="map-stage" style={{ height: 340 }}>
        {!risk && <div className="map-loading">{error ? S[lang].loading_map : s.loading_map}</div>}
        <RiskMap geojson={geo} risk={risk?.tehsils ?? []} lead={lead} selected={null} onSelect={open} cooperative flyOnSelect={false} />
        <div className="legend">
          {LEVEL_ORDER.map((l) => <span key={l}><i className="chip" style={{ background: LEVEL_COLORS[l] }} />{LEVEL_NAMES[lang][l]}</span>)}
        </div>
      </div>
      <div className="ol-foot">
        {risk && (high.length === 0 ? (
          <p className="ol-sum"><CircleCheck {...I} className="ok" />{s.none_high}</p>
        ) : (
          <p className="ol-sum"><TriangleAlert {...I} className="warn" />
            <span><b className="ltr">{high.length}</b> {s.some_high}{" "}
              {high.slice(0, 4).map((r, i) => (
                <span key={r.tehsil_id}>{i > 0 && ", "}<button className="inline-link" onClick={() => open(r.tehsil_id)}>{tehsilName(r, lang)}</button></span>
              ))}{high.length > 4 ? "…" : ""}
            </span>
          </p>
        ))}
        <Link href="/map" className="btn ghost sm"><MapIcon {...I} />{s.open_map}</Link>
      </div>
    </div>
  );
}

const STEPS: { icon: LucideIcon; t: string; d: string }[] = [
  { icon: CloudRain, t: "step1_t", d: "step1_d" },
  { icon: History, t: "step2_t", d: "step2_d" },
  { icon: Mountain, t: "step3_t", d: "step3_d" },
  { icon: BellRing, t: "step4_t", d: "step4_d" },
];
const TASKS: { href: string; icon: LucideIcon; t: string; d: string }[] = [
  { href: "/area", icon: MapPin, t: "task_area_t", d: "task_area_d" },
  { href: "/map", icon: MapIcon, t: "task_map_t", d: "task_map_d" },
  { href: "/ask", icon: MessageCircle, t: "task_ask_t", d: "task_ask_d" },
  { href: "/alerts", icon: BellRing, t: "task_alerts_t", d: "task_alerts_d" },
];

export default function Home() {
  const { lang, setPlace } = useSite();
  const s = S[lang];
  const router = useRouter();

  return (
    <>
      <section className="hero wrap">
        <div className="hero-copy">
          <h1 className="hero-title reveal">{s.hero_title}</h1>
          <p className="lede reveal" style={{ "--d": "60ms" } as React.CSSProperties}>{s.hero_sub}</p>
          <div className="hero-search reveal" style={{ "--d": "120ms" } as React.CSSProperties}>
            <label className="field-label" htmlFor="hero-search">{s.where_q}</label>
            <PlaceSearch lang={lang} cta={s.check} inputId="hero-search" placeholder={s.hero_ph} onPick={(p) => { setPlace(p); router.push("/area"); }} />
            <div className="hero-alt">
              <span>{s.or}</span>
              <button className="btn outline sm" onClick={() => router.push("/area?locate=1")}>{Icon.locate}{s.use_location}</button>
            </div>
          </div>
          <ul className="facts reveal" style={{ "--d": "180ms" } as React.CSSProperties}>
            <li><Wallet {...I} />{s.fact_free}</li>
            <li><Languages {...I} />{s.fact_lang}</li>
            <li><RefreshCw {...I} />{s.fact_updated}</li>
          </ul>
        </div>
        <div className="hero-side reveal" style={{ "--d": "120ms" } as React.CSSProperties}>
          <Outlook />
        </div>
      </section>

      <section className="section wrap" aria-labelledby="how">
        <div className="section-head reveal"><h2 id="how" className="h-section">{s.how_title}</h2><p>{s.how_sub}</p></div>
        <ol className="steps">
          {STEPS.map((st, i) => (
            <li key={st.t} className="step reveal" style={{ "--d": `${i * 90}ms` } as React.CSSProperties}>
              <span className="step-icon"><st.icon {...I} /></span>
              <span className="step-n">{i + 1}</span>
              <h3>{s[st.t]}</h3>
              <p>{s[st.d]}</p>
            </li>
          ))}
        </ol>
        <p className="note reveal"><Info {...I} />{s.honest}</p>
      </section>

      <section className="section wrap" aria-labelledby="colours">
        <div className="section-head reveal"><h2 id="colours" className="h-section">{s.colours_title}</h2><p>{s.colours_sub}</p></div>
        <div className="levels">
          {LEVEL_ORDER.map((l, i) => {
            const LI = LEVEL_ICON[l];
            return (
              <div key={l} className={`level-card ${l} reveal`} style={{ "--d": `${i * 70}ms` } as React.CSSProperties}>
                <span className="level-top"><LI {...I} /><b>{LEVEL_NAMES[lang][l]}</b></span>
                <p>{ADVICE[lang][l]}</p>
              </div>
            );
          })}
        </div>
      </section>

      <section className="section wrap" aria-labelledby="tasks">
        <div className="section-head reveal"><h2 id="tasks" className="h-section">{s.tasks_title}</h2></div>
        <div className="tasks">
          {TASKS.map((t, i) => (
            <Link key={t.href} href={t.href} className="task reveal" style={{ "--d": `${i * 70}ms` } as React.CSSProperties}>
              <span className="task-icon"><t.icon {...I} /></span>
              <span className="task-t">{s[t.t]}{Icon.arrow}</span>
              <span className="task-d">{s[t.d]}</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="section wrap">
        <div className="danger reveal">
          <span className="danger-icon"><Phone {...I} /></span>
          <div className="danger-copy"><h2>{s.danger_t}</h2><p>{s.danger_d}</p></div>
          <div className="row">
            <a href="tel:1122" className="btn">{Icon.phone}{s.call_1122}</a>
            <a href="tel:1700" className="btn ghost">{s.pdma} <span className="ltr">1700</span></a>
          </div>
        </div>
      </section>
    </>
  );
}
