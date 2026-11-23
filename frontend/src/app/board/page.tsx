"use client";

import { useEffect, useMemo, useState } from "react";

import RiskMap, { type MapMarker } from "@/components/RiskMap";
import { Logo } from "@/components/site/ui";
import { api, ApiError, LEVEL_COLORS, LEVEL_ORDER, RAIN_STEPS, type Advisory, type Level, type ObservedRain, type RiskResponse, type TehsilDetail } from "@/lib/api";

const LEVEL_LABEL: Record<Level, string> = { low: "Low", moderate: "Moderate", high: "High", very_high: "Very high" };
const PRESETS: { label: string; asOf: string | null }[] = [
  { label: "Live", asOf: null },
  { label: "Replay: 14 Aug 2025 (Buner cloudburst eve)", asOf: "2025-08-14T09:00:00+05:00" },
  { label: "Replay: 26 Jun 2025 (Swat River flood eve)", asOf: "2025-06-26T09:00:00+05:00" },
];

function Login({ onToken }: { onToken: (t: string) => void }) {
  const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <div className="login">
      <form className="card" onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setErr(null);
        try {
          const r = await api.login(pw);
          try { sessionStorage.setItem("nigehban:board", r.token); } catch { /* session only */ }
          onToken(r.token);
        } catch (e2) {
          setErr(e2 instanceof ApiError ? e2.message : "Login failed.");
        } finally {
          setBusy(false);
        }
      }}>
        <Logo withUrdu={false} /><h2 style={{ margin: "8px 0 0" }}>Authority board</h2>
        <p className="muted" style={{ margin: 0 }}>PDMA, district administration and Rescue 1122.</p>
        <input type="password" autoComplete="current-password" placeholder="Board password" value={pw} onChange={(e) => setPw(e.target.value)} />
        <button className="btn" disabled={busy || !pw}>{busy ? "Signing in…" : "Sign in"}</button>
        {err && <div className="banner err">{err}</div>}
      </form>
    </div>
  );
}

export default function BoardPage() {
  const [token, setToken] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);
  const [geo, setGeo] = useState<GeoJSON.FeatureCollection | null>(null);
  const [risk, setRisk] = useState<RiskResponse | null>(null);
  const [preset, setPreset] = useState(0);
  const [customDate, setCustomDate] = useState("");
  const [lead, setLead] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<TehsilDetail | null>(null);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<Advisory | null>(null);
  const [drafting, setDrafting] = useState(false);
  const [mapMode, setMapMode] = useState<"risk" | "rain">("risk");
  const [rain, setRain] = useState<ObservedRain | null>(null);

  useEffect(() => {
    document.documentElement.lang = "en";
    document.documentElement.dir = "ltr";
    document.body.classList.remove("ur");
    try { setToken(sessionStorage.getItem("nigehban:board")); } catch { /* none */ }
    setChecked(true);
  }, []);

  const asOf = customDate ? `${customDate}T09:00:00+05:00` : PRESETS[preset].asOf;

  useEffect(() => {
    if (!token) return;
    api.tehsils().then(setGeo).catch(() => setError("Could not load tehsil boundaries."));
  }, [token]);

  useEffect(() => {
    if (!token) return;
    // Only the answer for the date on screen counts: an older, slower answer is ignored.
    let live = true;
    setLoading(true);
    setError(null);
    setRisk(null);
    api.risk(asOf).then((r) => { if (live) { setRisk(r); setLoading(false); } })
      .catch((e) => { if (live) { setError(e instanceof ApiError ? e.message : "Could not load risk."); setLoading(false); } });
    api.alerts(token, asOf !== null).then((a) => { if (live) setAlerts(a); }).catch((e) => {
      if (e instanceof ApiError && e.status === 401) { setToken(null); try { sessionStorage.removeItem("nigehban:board"); } catch { /* */ } }
    });
    return () => { live = false; };
  }, [token, asOf]);

  useEffect(() => {
    if (!token) return;
    let live = true;
    setRain(null);
    api.rain(asOf).then((r) => { if (live) setRain(r); }).catch(() => { if (live) setRain(null); });
    return () => { live = false; };
  }, [token, asOf]);

  const rainBy = useMemo(() => new Map((rain?.tehsils ?? []).map((t) => [t.tehsil_id, t])), [rain]);
  const wettest = useMemo(() => [...(rain?.tehsils ?? [])].sort((a, b) => b.max_mm - a.max_mm).slice(0, 5), [rain]);
  const rainDay = rain?.date ? new Date(`${rain.date}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" }) : null;

  useEffect(() => {
    let live = true;
    setDetail(null);
    if (selected) api.tehsil(selected, asOf).then((d) => { if (live) setDetail(d); }).catch(() => { if (live) setDetail(null); });
    return () => { live = false; };
  }, [selected, asOf]);

  const rows = useMemo(() => {
    if (!risk) return [];
    return [...risk.tehsils].sort((a, b) => {
      const da = a.days.find((d) => d.lead_days === lead);
      const db = b.days.find((d) => d.lead_days === lead);
      return (LEVEL_ORDER.indexOf(db?.level ?? "low") - LEVEL_ORDER.indexOf(da?.level ?? "low"))
        || ((db?.probability ?? 0) - (da?.probability ?? 0));
    });
  }, [risk, lead]);

  const counts = useMemo(() => {
    const c: Record<Level, number> = { low: 0, moderate: 0, high: 0, very_high: 0 };
    rows.forEach((r) => { const d = r.days.find((x) => x.lead_days === lead); if (d) c[d.level] += 1; });
    return c;
  }, [rows, lead]);

  const markers: MapMarker[] = useMemo(() => {
    if (!detail) return [];
    return [
      ...detail.shelters.map((f) => ({ lon: f.lon, lat: f.lat, color: f.kind === "high_ground" ? "#1c7ed6" : "#2f9e44",
        label: `${f.kind === "high_ground" ? "Higher ground" : "Shelter"}: ${f.name}` })),
      ...detail.rescue_1122.map((f) => ({ lon: f.lon, lat: f.lat, color: "#f03e3e", label: f.subtype ? `${f.name} (${f.subtype})` : f.name })),
      ...detail.high_villages.slice(0, 10).map((v) => ({ lon: v.lon, lat: v.lat, color: "#7048e8", label: `High exposure: ${v.name}` })),
    ];
  }, [detail]);

  const makeDraft = async (ids: string[]) => {
    if (!token || ids.length === 0) return;
    setDrafting(true);
    setError(null);
    try {
      setDraft(await api.advisory(token, ids.slice(0, 12), asOf));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not draft the advisory.");
    } finally {
      setDrafting(false);
    }
  };
  const highIds = rows.filter((r) => { const d = r.days.find((x) => x.lead_days === lead); return d && (d.level === "high" || d.level === "very_high"); }).map((r) => r.tehsil_id);

  if (!checked) return null;
  if (!token) return <Login onToken={setToken} />;

  const sel = rows.find((r) => r.tehsil_id === selected);
  const issue = risk ? new Date(risk.issue_date) : null;
  const dayName = (l: number) => (issue ? new Date(issue.getTime() + l * 86400000).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" }) : `+${l}`);

  return (
    <div className="board">
      <div className="board-top">
        <h1><Logo withUrdu={false} /><span className="tiny" style={{ fontWeight: 400 }}>Authority board</span></h1>
        <select value={customDate ? -1 : preset} onChange={(e) => { setCustomDate(""); setPreset(Number(e.target.value)); }}>
          {PRESETS.map((p, i) => <option key={p.label} value={i}>{p.label}</option>)}
          {customDate && <option value={-1}>Replay: {customDate}</option>}
        </select>
        <label className="row" style={{ gap: 6 }}>
          <span style={{ fontSize: 13 }}>or date</span>
          <input type="date" min="2024-03-01" value={customDate} onChange={(e) => setCustomDate(e.target.value)} />
        </label>
        <div className="seg" role="group" aria-label="Day">
          {[0, 1, 2, 3].map((l) => <button key={l} className={lead === l ? "on" : ""} onClick={() => setLead(l)}>{dayName(l)}</button>)}
        </div>
        {risk?.replay && <span className="pill" style={{ background: "#fff3d6", color: "#6a4b00" }}>REPLAY · forecasts as issued {risk.issue_date}</span>}
        <button className="btn ghost" style={{ marginLeft: "auto", padding: "6px 12px" }}
          onClick={() => { try { sessionStorage.removeItem("nigehban:board"); } catch { /* */ } setToken(null); }}>Sign out</button>
      </div>
      <div className="board-main">
        <div className="board-map">
          {loading && <div className="loading-overlay">Computing risk for all tehsils…</div>}
          <RiskMap geojson={geo} risk={risk?.tehsils ?? []} lead={lead} selected={selected} onSelect={setSelected} markers={markers}
            mode={mapMode} rain={rain} />
          <div className="map-mode seg" role="group" aria-label="Map layer">
            <button className={mapMode === "risk" ? "on" : ""} onClick={() => setMapMode("risk")}>Forecast risk</button>
            <button className={mapMode === "rain" ? "on" : ""} onClick={() => setMapMode("rain")}
              title="Rain that has already fallen, from NASA satellites. Not a forecast.">Satellite rain{rainDay ? ` (${rainDay})` : ""}</button>
          </div>
          {mapMode === "risk" ? (
            <div className="legend">
              {LEVEL_ORDER.map((l) => <span key={l}><i className="chip" style={{ background: LEVEL_COLORS[l] }} />{LEVEL_LABEL[l]}</span>)}
            </div>
          ) : (
            <div className="legend">
              <span>{rain?.available ? `Rain fallen, mm (UTC day ${rainDay})` : (rain?.note ?? "Loading satellite rain…")}</span>
              {rain?.available && RAIN_STEPS.map((st) => <span key={st.label}><i className="chip" style={{ background: st.color }} />{st.label}</span>)}
            </div>
          )}
        </div>
        <aside className="board-side">
          {error && <section><div className="banner err">{error}</div></section>}
          <section>
            <div className="kpis">
              {LEVEL_ORDER.slice().reverse().map((l) => (
                <div key={l} className="kpi" style={{ borderTop: `4px solid ${LEVEL_COLORS[l]}` }}><b>{counts[l]}</b>{LEVEL_LABEL[l]}</div>
              ))}
            </div>
            <p className="tiny" style={{ marginBottom: 8 }}>Tehsils by level for {dayName(lead)}. Levels come from the risk model and fixed thresholds only.</p>
            <button className="btn" disabled={drafting || highIds.length === 0} onClick={() => makeDraft(highIds)}>
              {drafting ? "Drafting…" : `Draft advisory for high-risk tehsils (${Math.min(highIds.length, 12)})`}
            </button>
          </section>
          {sel && (
            <section>
              <h2>{sel.tehsil} <span className="muted">· {sel.district}</span></h2>
              <div className="row" style={{ marginBottom: 8 }}>
                {sel.days.map((d) => (
                  <span key={d.date} className="pill" style={{ background: LEVEL_COLORS[d.level], color: d.level === "moderate" ? "#3a2a00" : "#fff" }}>
                    {dayName(d.lead_days)}: {LEVEL_LABEL[d.level]}{d.glofas_flag ? " · river" : ""}
                  </span>
                ))}
              </div>
              <p className="muted" style={{ margin: "4px 0" }}>Why: {sel.days.find((d) => d.lead_days === lead)?.drivers.join("; ") || "—"}</p>
              {rain?.available && (
                <p className="tiny" style={{ margin: "2px 0 6px" }}>
                  Satellite rain already fallen ({rainDay}): <b>{(rainBy.get(sel.tehsil_id)?.mean_mm ?? 0).toFixed(1)} mm</b> average,
                  {" "}{(rainBy.get(sel.tehsil_id)?.max_mm ?? 0).toFixed(1)} mm in the wettest part. Observed, not a forecast.
                </p>
              )}
              {detail ? (
                <>
                  <p className="muted" style={{ margin: "4px 0" }}>
                    Villages: <b>{detail.exposure.high}</b> high, {detail.exposure.medium} medium, {detail.exposure.low} low exposure (of {detail.exposure.villages}).
                  </p>
                  <p className="tiny" style={{ margin: "2px 0 6px" }}>High exposure: {detail.high_villages.slice(0, 8).map((v) => v.name).join(", ") || "none"}</p>
                  <b style={{ fontSize: 13 }}>Shelters and higher ground</b>
                  {detail.shelters.map((f) => (
                    <div key={f.id} className="facility"><span>{f.name || f.subtype} <span className="pill">{f.kind === "high_ground" ? "higher ground" : f.subtype}</span></span><span className="tiny">{f.km} km</span></div>
                  ))}
                  <b style={{ fontSize: 13 }}>Rescue 1122</b>
                  {detail.rescue_1122_control_room && (
                    <p className="tiny" style={{ margin: "2px 0" }}>District control room ({detail.rescue_1122_control_room.district}): <b>{detail.rescue_1122_control_room.control_room}</b> · office {detail.rescue_1122_control_room.district_office} · official directory</p>
                  )}
                  {detail.rescue_1122.map((f) => (
                    <div key={f.id} className="facility"><span>{f.name}</span><span className="tiny">{f.km} km{f.subtype ? ` · ${f.subtype}` : ""}</span></div>
                  ))}
                  {detail.rivers.map((r) => (
                    <p key={r.point_id} className="tiny">{r.name}: {r.series.map((s) => `${s.discharge.toFixed(0)}`).join(" → ")} m³/s (2-yr flow {r.q2.toFixed(0)})</p>
                  ))}
                  <p className="tiny">{detail.note}</p>
                  <button className="btn ghost" disabled={drafting} onClick={() => makeDraft([sel.tehsil_id])}>{drafting ? "Drafting…" : "Draft advisory for this tehsil"}</button>
                </>
              ) : <p className="muted">Loading details…</p>}
            </section>
          )}
          {mapMode === "rain" && rain?.available && (
            <section>
              <h2>Wettest tehsils by satellite ({rainDay})</h2>
              {wettest.map((t) => {
                const r = rows.find((x) => x.tehsil_id === t.tehsil_id);
                return (
                  <div key={t.tehsil_id} className="facility" style={{ cursor: "pointer" }} onClick={() => setSelected(t.tehsil_id)}>
                    <span>{r?.tehsil ?? t.tehsil_id} <span className="tiny">{r?.district}</span></span>
                    <span className="tiny">{t.max_mm.toFixed(0)} mm peak · {t.mean_mm.toFixed(0)} mm avg</span>
                  </div>
                );
              })}
              <p className="tiny">{rain.note} Observed rain only; it is not used by the forecast model.</p>
            </section>
          )}
          <section>
            <h2>Tehsils ranked ({dayName(lead)})</h2>
            <table className="rank">
              <thead><tr><th>Tehsil</th><th>Next 4 days</th><th>Main reason</th></tr></thead>
              <tbody>
                {rows.map((r) => {
                  const d = r.days.find((x) => x.lead_days === lead);
                  return (
                    <tr key={r.tehsil_id} className={r.tehsil_id === selected ? "sel" : ""} onClick={() => setSelected(r.tehsil_id)}>
                      <td><b>{r.tehsil}</b><br /><span className="tiny">{r.district}</span></td>
                      <td style={{ whiteSpace: "nowrap" }}>{r.days.map((x) => <i key={x.date} className="chip" title={`${dayName(x.lead_days)}: ${LEVEL_LABEL[x.level]}`} style={{ background: LEVEL_COLORS[x.level], outline: x.lead_days === lead ? "2px solid #111" : "none" }} />)}</td>
                      <td className="tiny">{d?.drivers[0] ?? ""}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>
          <section>
            <h2>Alerts sent ({risk?.replay ? "replay" : "live"})</h2>
            {alerts.length === 0 && <p className="muted">No alerts yet for this mode.</p>}
            {alerts.slice(0, 20).map((a) => (
              <div key={a.id} className="facility">
                <span><i className="chip" style={{ background: LEVEL_COLORS[a.level as Level] }} />{a.tehsil_id.split("__")[1].replace(/_/g, " ")} · {a.valid_date}</span>
                <span className="tiny">lead {a.lead_days}d · sent to {a.sent_to}</span>
              </div>
            ))}
          </section>
        </aside>
      </div>
      {draft && (
        <div className="modal" role="dialog" aria-modal="true" onClick={() => setDraft(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <b>Advisory draft {draft.checked ? "(actions checked against the evidence)" : "(template actions)"}</b>
              <div className="row">
                <button className="btn ghost" onClick={() => navigator.clipboard?.writeText(draft.markdown)}>Copy text</button>
                <button className="btn ghost" onClick={() => window.print()}>Print</button>
                <button className="btn" onClick={() => setDraft(null)}>Close</button>
              </div>
            </div>
            <article className="advisory">
              <h2>{draft.title}</h2>
              <p><b>Date:</b> {draft.date} · <b>Area:</b> {draft.area.join(", ")}</p>
              <h3>Risk (Nigehban risk model)</h3>
              <table className="rank">
                <thead><tr><th>Tehsil</th>{draft.risk[0]?.days.map((d) => <th key={d.date}>{d.date.slice(5)}</th>)}</tr></thead>
                <tbody>{draft.risk.map((r) => (
                  <tr key={r.tehsil_id}><td>{r.tehsil}</td>{r.days.map((d) => (
                    <td key={d.date}><i className="chip" style={{ background: LEVEL_COLORS[d.level] }} />{LEVEL_LABEL[d.level]}{d.river_flag ? " (river)" : ""}</td>))}</tr>
                ))}</tbody>
              </table>
              <h3>Recommended actions</h3>
              <ol>{draft.actions.map((a, i) => <li key={i}>{a.text}</li>)}</ol>
              <h3>Message for the public</h3>
              <p>{draft.public_message_en}</p>
              <p className="ur" dir="rtl">{draft.public_message_ur}</p>
              <h3>Sources</h3>
              <ul>{draft.sources.map((x) => <li key={x}>{x}</li>)}</ul>
              <p className="draft-footer">{draft.footer}</p>
            </article>
          </div>
        </div>
      )}
    </div>
  );
}
