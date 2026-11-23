"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import RiskMap, { type MapMarker } from "@/components/RiskMap";
import { Icon, LevelBadge, LevelStrip, dayShort } from "@/components/site/ui";
import { LEVEL_COLORS, LEVEL_ORDER, RAIN_STEPS } from "@/lib/api";
import { S } from "@/lib/copy";
import { countLevels, levelAt, useGeo, useRain, useRanked, useRisk, useTehsil } from "@/lib/hooks";
import { DRIVER_NAMES, LEVEL_NAMES, T } from "@/lib/i18n";
import { districtName, tehsilName, tehsilPlace } from "@/lib/places";
import { useSite } from "@/lib/site";

export default function MapPage() {
  const { lang, asOf, setPlace } = useSite();
  const s = S[lang];
  const t = T[lang];
  const router = useRouter();
  const geo = useGeo();
  const { risk, error } = useRisk(asOf);
  const rain = useRain(asOf);
  const [lead, setLead] = useState(1);
  const [mode, setMode] = useState<"risk" | "rain">("risk");
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const ranked = useRanked(risk, lead);
  const counts = countLevels(ranked, lead);
  const detail = useTehsil(selected, asOf);
  const sel = ranked.find((r) => r.tehsil_id === selected);
  const day = sel ? levelAt(sel, lead) : undefined;
  const rainBy = useMemo(() => new Map((rain?.tehsils ?? []).map((x) => [x.tehsil_id, x])), [rain]);

  const shown = ranked.filter((r) => {
    const q = filter.trim().toLowerCase();
    return !q || r.tehsil.toLowerCase().includes(q) || r.district.toLowerCase().includes(q) || (r.tehsil_ur ?? "").includes(q);
  });
  const markers: MapMarker[] = useMemo(() => (detail ? [
    ...detail.shelters.slice(0, 6).map((f) => ({ lon: f.lon, lat: f.lat, color: f.kind === "high_ground" ? "#1c7ed6" : "#2f9e44", label: f.name })),
    ...detail.rescue_1122.slice(0, 3).map((f) => ({ lon: f.lon, lat: f.lat, color: "#d9662b", label: f.name })),
  ] : []), [detail, t]);

  return (
    <div className="wrap" style={{ maxWidth: 1440 }}>
      <div className="map-layout">
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
            {!risk && <div className="map-loading">{error ? t.error : s.loading_map}</div>}
            <RiskMap geojson={geo} risk={risk?.tehsils ?? []} lead={lead} selected={selected} onSelect={setSelected}
              markers={markers} mode={mode} rain={rain} />
            <div className="legend">
              {mode === "risk"
                ? LEVEL_ORDER.map((l) => <span key={l}><i className="chip" style={{ background: LEVEL_COLORS[l] }} />{LEVEL_NAMES[lang][l]}</span>)
                : <>{<span className="tiny" style={{ width: "100%" }}>{rain?.available ? `${s.rain_note} · ${rain.date}` : rain?.note}</span>}
                    {RAIN_STEPS.map((st) => <span key={st.label} className="ltr"><i className="chip" style={{ background: st.color }} />{st.label} mm</span>)}</>}
            </div>
          </div>
        </div>

        <aside className="panel">
          <section>
            <h1 style={{ fontSize: 24, letterSpacing: "-0.025em" }}>{s.map_title}</h1>
            <p className="tiny" style={{ marginTop: 2 }}>{s.map_sub}</p>
            <div className="counts" style={{ marginTop: 14 }}>
              {LEVEL_ORDER.slice().reverse().map((l) => (
                <div key={l}><b>{risk ? counts[l] : "–"}</b><span><i className="chip" style={{ background: LEVEL_COLORS[l], width: 9, height: 9 }} />{LEVEL_NAMES[lang][l]}</span></div>
              ))}
            </div>
          </section>

          <section>
            {sel && day ? (
              <>
                <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start", flexWrap: "nowrap" }}>
                  <div><h2 style={{ marginBottom: 0 }}>{tehsilName(sel, lang)}</h2><span className="tiny">{districtName(sel, lang)}</span></div>
                  <LevelBadge level={day.level} lang={lang} />
                </div>
                <LevelStrip days={sel.days} lang={lang} focus={lead} />
                {day.driver_codes.length > 0 && (
                  <ul className="reasons" style={{ marginTop: 12 }}>{day.driver_codes.map((c) => DRIVER_NAMES[lang][c]).filter(Boolean).map((r) => <li key={r}>{r}</li>)}</ul>
                )}
                {rain?.available && rainBy.get(sel.tehsil_id) && (
                  <p className="tiny" style={{ marginTop: 10 }}>{s.rain_layer} ({rain.date}): <span className="ltr">{rainBy.get(sel.tehsil_id)!.mean_mm.toFixed(1)} mm · max {rainBy.get(sel.tehsil_id)!.max_mm.toFixed(0)} mm</span></p>
                )}
                {detail && (
                  <>
                    <p className="tiny" style={{ marginTop: 10 }}>{s.exposure}: <b style={{ color: "var(--ink)" }}>{detail.exposure.high}</b> {s.exp_high} · {detail.exposure.medium} {s.exp_medium}</p>
                    {detail.rivers.slice(0, 2).map((r) => (
                      <p key={r.point_id} className="tiny ltr" style={{ marginTop: 4 }}>{s.river_flow} · {r.name}: {r.series.map((x) => x.discharge.toFixed(0)).join(" → ")} m³/s ({s.two_year} {r.q2.toFixed(0)})</p>
                    ))}
                  </>
                )}
                <button className="btn sm" style={{ marginTop: 14 }} onClick={() => { setPlace(tehsilPlace(sel, geo)); router.push("/area"); }}>
                  {s.open_details}{Icon.arrow}
                </button>
              </>
            ) : <p className="tiny">{s.select_hint}</p>}
          </section>

          <section>
            <div className="row" style={{ justifyContent: "space-between", marginBottom: 10 }}>
              <h2 style={{ margin: 0 }}>{s.ranked}</h2>
            </div>
            <div className="search flat" style={{ marginBottom: 8 }}>
              <div className="search-box" style={{ padding: "2px 12px" }}>
                {Icon.search}
                <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder={s.filter} aria-label={s.filter} style={{ fontSize: 14 }} />
              </div>
            </div>
            <div className="rank-list">
              {shown.map((r) => (
                <button key={r.tehsil_id} className={`rank-item ${r.tehsil_id === selected ? "sel" : ""}`} onClick={() => setSelected(r.tehsil_id)}>
                  <span><span className="nm">{tehsilName(r, lang)}</span><br /><span className="ds">{districtName(r, lang)}</span></span>
                  <span className="mini-strip ltr">{r.days.map((d) => <i key={d.date} className={d.lead_days === lead ? "focus" : ""} style={{ background: LEVEL_COLORS[d.level] }} title={LEVEL_NAMES[lang][d.level]} />)}</span>
                </button>
              ))}
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}
