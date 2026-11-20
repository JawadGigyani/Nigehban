"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import RiskMap from "@/components/RiskMap";
import { Icon, LevelBadge, LevelStrip, PlaceSearch, dayShort } from "@/components/site/ui";
import { LEVEL_COLORS, LEVEL_ORDER, RAIN_STEPS, type TehsilRisk } from "@/lib/api";
import { S } from "@/lib/copy";
import { countLevels, levelAt, useGeo, useRain, useRanked, useRisk } from "@/lib/hooks";
import { DRIVER_NAMES, LEVEL_NAMES } from "@/lib/i18n";
import { districtName, tehsilName, tehsilPlace } from "@/lib/places";
import { useSite } from "@/lib/site";

function MapShowcase() {
  const { lang, asOf, setPlace } = useSite();
  const s = S[lang];
  const router = useRouter();
  const geo = useGeo();
  const { risk, error } = useRisk(asOf);
  const rain = useRain(asOf);
  const [lead, setLead] = useState(1);
  const [mode, setMode] = useState<"risk" | "rain">("risk");
  const [selected, setSelected] = useState<string | null>(null);
  const ranked = useRanked(risk, lead);
  const counts = countLevels(ranked, lead);
  const sel = ranked.find((r) => r.tehsil_id === selected) ?? ranked[0];
  const day = sel ? levelAt(sel, lead) : undefined;
  const reason = day?.driver_codes.map((c) => DRIVER_NAMES[lang][c]).find(Boolean);
  const wettest = useMemo(() => [...(rain?.tehsils ?? [])].sort((a, b) => b.max_mm - a.max_mm).slice(0, 3), [rain]);
  const nameOf = (id: string) => { const r = risk?.tehsils.find((x) => x.tehsil_id === id); return r ? tehsilName(r, lang) : id; };

  const open = (r: TehsilRisk) => { setPlace(tehsilPlace(r, geo)); router.push("/area"); };

  return (
    <>
      <div className="window">
        <div className="window-bar">
          <div className="seg" role="group" aria-label="Day">
            {(risk?.tehsils[0]?.days ?? []).map((d) => (
              <button key={d.lead_days} className={lead === d.lead_days && mode === "risk" ? "on" : ""}
                onClick={() => { setLead(d.lead_days); setMode("risk"); }}>{dayShort(lang, d.date, d.lead_days)}</button>
            ))}
          </div>
          <div className="seg" role="group" aria-label="Layer" style={{ marginInlineStart: "auto" }}>
            <button className={mode === "risk" ? "on" : ""} onClick={() => setMode("risk")}>{s.risk_layer}</button>
            <button className={mode === "rain" ? "on" : ""} onClick={() => setMode("rain")}>{s.rain_layer}</button>
          </div>
        </div>
        <div className="map-stage">
          {!risk && !error && <div className="map-loading">{s.loading_map}</div>}
          {error && <div className="map-loading">{S[lang].loading_map}</div>}
          <RiskMap geojson={geo} risk={risk?.tehsils ?? []} lead={lead} selected={sel?.tehsil_id ?? null} onSelect={setSelected}
            mode={mode} rain={rain} cooperative flyOnSelect={false} />
          {mode === "risk" && sel && day && (
            <div className="float-card">
              <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start", flexWrap: "nowrap" }}>
                <div>
                  {!selected && <div className="tiny">{s.highest}</div>}
                  <div className="fc-title">{tehsilName(sel, lang)}</div>
                  <div className="fc-sub">{districtName(sel, lang)}</div>
                </div>
                <LevelBadge level={day.level} lang={lang} />
              </div>
              <LevelStrip days={sel.days} lang={lang} focus={lead} />
              {reason && <p className="tiny" style={{ marginTop: 12 }}>{s.why}: <span style={{ color: "var(--ink-body)" }}>{reason}</span></p>}
              <button className="btn sm" style={{ marginTop: 14, width: "100%" }} onClick={() => open(sel)}>{s.open_details}</button>
            </div>
          )}
          {mode === "rain" && (
            <div className="float-card">
              <div className="fc-title">{s.rain_layer}{rain?.date ? <span className="tiny ltr"> · {rain.date}</span> : null}</div>
              <div className="fc-sub">{s.rain_note}</div>
              {rain?.available ? wettest.map((t) => (
                <div key={t.tehsil_id} className="facility" style={{ fontSize: 14 }}>
                  <span>{nameOf(t.tehsil_id)}</span><span className="meta ltr">{t.max_mm.toFixed(0)} mm</span>
                </div>
              )) : <p className="tiny" style={{ marginTop: 10 }}>{rain?.note ?? "…"}</p>}
            </div>
          )}
          <div className="legend">
            {mode === "risk"
              ? LEVEL_ORDER.map((l) => <span key={l}><i className="chip" style={{ background: LEVEL_COLORS[l] }} />{LEVEL_NAMES[lang][l]}</span>)
              : RAIN_STEPS.map((st) => <span key={st.label} className="ltr"><i className="chip" style={{ background: st.color }} />{st.label} mm</span>)}
          </div>
        </div>
      </div>
      <div className="kpi-row">
        {LEVEL_ORDER.slice().reverse().map((l) => (
          <div key={l} className="kpi"><b>{risk ? counts[l] : "–"}</b><span><i className="chip" style={{ background: LEVEL_COLORS[l] }} />{LEVEL_NAMES[lang][l]}</span></div>
        ))}
        <div className="kpi"><b>{risk ? risk.tehsils.length : "–"}</b><span>{s.covered}</span></div>
      </div>
    </>
  );
}

function Bento() {
  const { lang, asOf } = useSite();
  const s = S[lang];
  const { risk } = useRisk(asOf);
  const ranked = useRanked(risk, 1);
  const top = ranked[0];
  const rainCells = [0, 1, 1, 2, 0, 0, 1, 0, 0, 1, 2, 3, 3, 1, 0, 1, 1, 0, 0, 2, 3, 4, 3, 2, 1, 2, 1, 0, 1, 2, 3, 2, 1, 0, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0];
  return (
    <div className="bento">
      <Link href="/area" className="tile wide">
        <div className="art">
          <div className="mini" style={{ maxWidth: 420 }}>
            {top ? (
              <>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <span className="mt">{tehsilName(top, lang)} <span className="tiny">· {districtName(top, lang)}</span></span>
                  <LevelBadge level={top.max_level} lang={lang} />
                </div>
                <LevelStrip days={top.days} lang={lang} focus={1} />
                <ul className="reasons" style={{ marginTop: 12 }}>
                  {(levelAt(top, 1)?.driver_codes ?? []).slice(0, 2).map((c) => <li key={c}>{DRIVER_NAMES[lang][c]}</li>)}
                </ul>
              </>
            ) : <><div className="bar" style={{ width: "50%" }} /><div className="bar" style={{ width: "80%", height: 26 }} /><div className="bar" style={{ width: "40%" }} /></>}
          </div>
        </div>
        <div className="t">{s.b_risk_t}{Icon.arrow}</div>
        <div className="dsc">{s.b_risk_d}</div>
      </Link>
      <Link href="/area" className="tile">
        <div className="art">
          <div className="mini">
            <div className="row" style={{ flexWrap: "nowrap" }}>
              <span style={{ width: 30, height: 30, borderRadius: 9, background: "var(--high-bg)", color: "#9a3412", display: "grid", placeItems: "center", flex: "none" }}>
                <span style={{ width: 16, height: 16, display: "block" }}>{Icon.alert}</span></span>
              <span className="mt">{s.sample_safe}</span>
            </div>
            <div className="callout" style={{ marginTop: 10, background: "var(--black)", color: "#fff" }}>
              <span className="row" style={{ gap: 8 }}><span style={{ width: 16, height: 16, display: "block" }}>{Icon.route}</span>{s.sample_route}</span>
            </div>
          </div>
        </div>
        <div className="t">{s.b_safe_t}{Icon.arrow}</div>
        <div className="dsc">{s.b_safe_d}</div>
      </Link>
      <Link href="/alerts" className="tile">
        <div className="art">
          <div className="mini">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <span className="row" style={{ gap: 8 }}><span style={{ width: 22, height: 22, borderRadius: 6, background: "#0e5e66", display: "inline-block" }} /><b style={{ fontWeight: 500, fontSize: 13 }}>Nigehban</b></span>
              <span className="tiny">09:00</span>
            </div>
            <p style={{ fontFamily: "var(--font-ur)", direction: "rtl", fontSize: 14, lineHeight: 2, marginTop: 6, color: "var(--ink)" }}>{S.ur.sample_alert}</p>
            <div className="row" style={{ gap: 6, marginTop: 4 }}><span className="badge neutral"><span style={{ width: 13, height: 13, display: "block" }}>{Icon.speaker}</span>0:12</span></div>
          </div>
        </div>
        <div className="t">{s.b_alert_t}{Icon.arrow}</div>
        <div className="dsc">{s.b_alert_d}</div>
      </Link>
      <Link href="/ask" className="tile">
        <div className="art" style={{ flexDirection: "column", gap: 8, alignItems: "stretch" }}>
          <div className="bubble me">{s.sample_q}</div>
          <div className="bubble bot" style={{ width: "78%" }}><div className="bar" style={{ width: "92%" }} /><div className="bar" style={{ width: "64%" }} /><div className="bar" style={{ width: "40%", marginBottom: 2 }} /></div>
        </div>
        <div className="t">{s.b_ask_t}{Icon.arrow}</div>
        <div className="dsc">{s.b_ask_d}</div>
      </Link>
      <Link href="/map" className="tile">
        <div className="art">
          <div className="rain-grid ltr" aria-hidden="true">
            {rainCells.map((v, i) => <i key={i} style={{ background: v === 0 ? "#ebe7e0" : RAIN_STEPS[v - 1].color }} />)}
          </div>
        </div>
        <div className="t">{s.b_rain_t}{Icon.arrow}</div>
        <div className="dsc">{s.b_rain_d}</div>
      </Link>
      <Link href="/board" className="tile full">
        <div className="copy">
          <div className="t" style={{ fontSize: 22, letterSpacing: "-0.02em" }}>{s.b_board_t}{Icon.arrow}</div>
          <div className="dsc" style={{ fontSize: 15, marginTop: 6 }}>{s.b_board_d}</div>
        </div>
        <div className="art">
          <div className="mini">
            {(ranked.length ? ranked.slice(0, 3) : []).map((r) => (
              <div key={r.tehsil_id} className="facility" style={{ fontSize: 13.5, padding: "8px 0" }}>
                <span>{tehsilName(r, lang)}</span>
                <span className="mini-strip">{r.days.map((d) => <i key={d.date} style={{ background: LEVEL_COLORS[d.level] }} />)}</span>
              </div>
            ))}
            {!ranked.length && <><div className="bar" /><div className="bar" style={{ width: "70%" }} /><div className="bar" style={{ width: "85%" }} /></>}
          </div>
        </div>
      </Link>
    </div>
  );
}

export default function Home() {
  const { lang, asOf, setPlace } = useSite();
  const s = S[lang];
  const router = useRouter();
  const { risk } = useRisk(asOf);
  const [updated, setUpdated] = useState<string | null>(null);
  useEffect(() => {
    if (!risk) return;
    setUpdated(new Date(risk.generated_at).toLocaleString(lang === "ur" ? "ur-PK" : "en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }));
  }, [risk, lang]);

  return (
    <>
      <section className="hero wrap">
        <span className="eyebrow"><span className="dot" />{s.hero_eyebrow}{updated && !asOf ? ` · ${s.updated} ${updated}` : ""}</span>
        <h1 className="display">{s.hero_title}</h1>
        <p className="lede">{s.hero_sub}</p>
        <div className="hero-search">
          <PlaceSearch lang={lang} cta={s.check} onPick={(p) => { setPlace(p); router.push("/area"); }} />
          <div className="hero-alt">
            <span>{s.or}</span>
            <button onClick={() => router.push("/area?locate=1")}>{Icon.locate}{s.use_location}</button>
          </div>
        </div>
      </section>

      <section className="wrap" style={{ paddingTop: 20 }} aria-label={s.outlook}>
        <MapShowcase />
      </section>

      <section className="section wrap">
        <div className="section-head"><h2 className="h-section">{s.bento_title}</h2></div>
        <Bento />
      </section>

      <section className="section wrap">
        <div className="section-head"><h2 className="h-section">{s.how_title}</h2><p>{s.how_sub}</p></div>
        <div className="how">
          {[1, 2, 3, 4].map((n) => (
            <div key={n} className="how-step">
              <span className="n">0{n}</span>
              <h3>{s[`how${n}_t`]}</h3>
              <p>{s[`how${n}_d`]}</p>
            </div>
          ))}
        </div>
        <div className="stat-card">
          <div className="big">{lang === "en" ? s.stat_value : <span>{s.stat_value}</span>}</div>
          <div><p>{s.stat_label}</p><p className="tiny" style={{ marginTop: 6 }}>{s.stat_note}</p></div>
        </div>
      </section>

      <section className="section wrap">
        <div className="safety-band">
          <div>
            <h2 className="h-section">{s.safety_title}</h2>
            <div className="row" style={{ marginTop: 22 }}>
              <a href="tel:1122" className="btn">{Icon.phone}{s.call_1122}</a>
              <Link href="/safety" className="btn ghost">{s.read_guide}</Link>
            </div>
          </div>
          <ol>
            {["s1", "s2", "s3"].map((k, i) => <li key={k}><span className="k">{i + 1}</span><span>{s[k]}</span></li>)}
          </ol>
        </div>
      </section>
    </>
  );
}
