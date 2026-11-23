"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Icon, LevelBadge, PlaceSearch } from "@/components/site/ui";
import { api, ApiError, LEVEL_ORDER, type GeoCheck, type Lang, type Level, type Place, type SafeRoute } from "@/lib/api";
import { ADVICE, S } from "@/lib/copy";
import { useGeo, useRisk, useTehsil } from "@/lib/hooks";
import { DRIVER_NAMES, LEVEL_NAMES, T, dayLabel } from "@/lib/i18n";
import { tehsilPlace } from "@/lib/places";
import { placeLabel, useSite } from "@/lib/site";

function fmtDate(date: string, lang: Lang) {
  return new Date(`${date}T00:00:00`).toLocaleDateString(lang === "ur" ? "ur-PK" : "en-GB", { weekday: "short", day: "numeric", month: "short" });
}

function SafetyCheck({ place, autoLocate, onLocated }: { place: Place | null; autoLocate: boolean; onLocated: (tehsilId: string) => void }) {
  const { lang, asOf } = useSite();
  const t = T[lang];
  const [check, setCheck] = useState<GeoCheck | null>(null);
  const [route, setRoute] = useState<SafeRoute | null>(null);
  const [point, setPoint] = useState<[number, number] | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const started = useRef(false);

  const run = async (lat: number, lon: number, fromGps: boolean) => {
    setBusy(true); setMsg(null); setRoute(null); setPoint([lat, lon]);
    try {
      const r = await api.geoCheck(lat, lon, asOf);
      setCheck(r);
      if (fromGps) onLocated(r.tehsil_id);
    } catch (e) { setCheck(null); setMsg(e instanceof ApiError ? e.message : t.error); }
    finally { setBusy(false); }
  };
  const here = () => {
    if (!("geolocation" in navigator)) { setMsg(t.no_gps); return; }
    setBusy(true);
    navigator.geolocation.getCurrentPosition((p) => run(p.coords.latitude, p.coords.longitude, true),
      () => { setBusy(false); setMsg(t.no_gps); }, { enableHighAccuracy: true, timeout: 15000 });
  };
  useEffect(() => {
    if (autoLocate && !started.current) { started.current = true; here(); }
  }); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { setCheck(null); setRoute(null); }, [place?.id, asOf]);

  const findRoute = async () => {
    if (!point) return;
    setBusy(true); setMsg(null);
    try { setRoute(await api.route(point[0], point[1], "walk")); } catch (e) { setMsg(e instanceof ApiError ? e.message : t.error); }
    finally { setBusy(false); }
  };
  const tone = check?.advice === "move_away" ? "very_high" : check?.advice === "be_ready" ? "high" : check?.advice === "stay_alert" ? "moderate" : "";
  return (
    <div className="card">
      <h2>{t.safety}</h2>
      <p className="muted" style={{ fontSize: 15 }}>{S[lang].b_safe_d}</p>
      <div className="row" style={{ marginTop: 14 }}>
        <button className="btn" onClick={here} disabled={busy}>{Icon.locate}{t.check_here}</button>
        {place?.lat !== undefined && place?.lon !== undefined && (
          <button className="btn ghost" onClick={() => run(place.lat!, place.lon!, false)} disabled={busy}>{t.check_place}</button>
        )}
      </div>
      {busy && <p className="tiny" style={{ marginTop: 12 }}>{t.loading}</p>}
      {check && (
        <div className={`advice ${tone}`}>
          {tone ? Icon.alert : Icon.check}
          <div>
            <b style={{ fontWeight: 500 }}>{check.advice_text[lang]}</b>
            {check.level_today_tomorrow && <div className="tiny" style={{ color: "inherit", opacity: 0.8 }}>{LEVEL_NAMES[lang][check.level_today_tomorrow]}</div>}
          </div>
        </div>
      )}
      {check && check.advice !== "normal" && !route && (
        <button className="btn" style={{ marginTop: 12 }} onClick={findRoute} disabled={busy}>{Icon.route}{t.route}</button>
      )}
      {route && point && (
        <div style={{ marginTop: 12 }}>
          <div className="facility">
            <span>{route.destination.name}{route.destination.kind === "high_ground" ? ` (${t.high_ground})` : ""}</span>
            <span className="meta">{(route.distance_m / 1000).toFixed(1)} {t.km} · {Math.round(route.duration_min)} {t.walk_min}</span>
          </div>
          {route.low_ground_share !== null && route.low_ground_share > 0.2 && <p className="tiny">{t.low_ground_route}</p>}
          <a className="btn outline sm" style={{ marginTop: 8 }} target="_blank" rel="noreferrer"
            href={`https://www.openstreetmap.org/directions?engine=fossgis_osrm_foot&route=${point[0]}%2C${point[1]}%3B${route.destination.lat}%2C${route.destination.lon}`}>
            {t.open_map}
          </a>
        </div>
      )}
      {msg && <p className="banner err" style={{ marginTop: 12 }}>{msg}</p>}
    </div>
  );
}

export default function AreaPage() {
  const { lang, asOf, place, setPlace, places, setPlaces } = useSite();
  const s = S[lang];
  const t = T[lang];
  const geo = useGeo();
  const { risk, error } = useRisk(asOf);
  const detail = useTehsil(place?.tehsil_id, asOf);
  const [autoLocate, setAutoLocate] = useState(false);
  useEffect(() => { setAutoLocate(new URLSearchParams(window.location.search).get("locate") === "1"); }, []);

  const row = risk?.tehsils.find((r) => r.tehsil_id === place?.tehsil_id);
  const near = row?.days.filter((d) => d.lead_days <= 1) ?? [];
  const worst: Level | undefined = near.length ? near.map((d) => d.level).sort((a, b) => LEVEL_ORDER.indexOf(b) - LEVEL_ORDER.indexOf(a))[0] : undefined;
  const top = row ? [...row.days].sort((a, b) => b.probability - a.probability)[0] : undefined;
  const reasons = top?.driver_codes.map((c) => DRIVER_NAMES[lang][c]).filter(Boolean) ?? [];
  const subscribed = !!place && places.some((p) => p.id === place.id);

  const onLocated = (tehsilId: string) => {
    const r = risk?.tehsils.find((x) => x.tehsil_id === tehsilId);
    if (r && place?.tehsil_id !== tehsilId) setPlace(tehsilPlace(r, geo));
  };

  return (
    <div className="wrap">
      <div className="page-head">
        <h1>{place ? placeLabel(place, lang) : s.area_title}</h1>
        <p>{place && row ? `${lang === "ur" && row.district_ur ? row.district_ur : row.district} · ${s.area_sub}` : s.area_sub}</p>
        <div style={{ maxWidth: 520, marginTop: 20 }}>
          <PlaceSearch lang={lang} flat placeholder={place ? s.change_place : undefined} onPick={setPlace} />
        </div>
      </div>

      {error && <div className="banner err">{t.error}</div>}

      <div className="cols">
        <div className="stack">
          {!place && (
            <div className="card empty">
              <div className="ico">{Icon.pin}</div>
              <h3>{s.area_empty_t}</h3>
              <p>{s.area_empty_d}</p>
            </div>
          )}
          {place && !row && !error && <div className="card"><div className="bar" style={{ width: "40%" }} /><div className="bar" style={{ height: 90, marginTop: 14 }} /></div>}
          {place && row && (
            <div className="card">
              <div className="row" style={{ justifyContent: "space-between" }}>
                <h2 style={{ margin: 0 }}>{s.outlook}</h2>
                {worst && <LevelBadge level={worst} lang={lang} />}
              </div>
              <div className="days" style={{ marginTop: 14 }}>
                {row.days.map((d) => (
                  <div key={d.date} className={`day ${d.level}`}>
                    <span className="when">{dayLabel(lang, d.lead_days)}</span>
                    <span className="date">{fmtDate(d.date, lang)}</span>
                    <span className="lvl">{LEVEL_NAMES[lang][d.level]}</span>
                  </div>
                ))}
              </div>
              {worst && (
                <div className={`advice ${worst === "low" ? "" : worst}`}>
                  {worst === "low" ? Icon.info : Icon.alert}
                  <div><b style={{ fontWeight: 500 }}>{s.what_to_do}</b><div>{ADVICE[lang][worst]}</div></div>
                </div>
              )}
              {reasons.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <span className="tiny">{t.reasons}</span>
                  <ul className="reasons">{reasons.map((r) => <li key={r}>{r}</li>)}</ul>
                </div>
              )}
              {row.days.some((d) => d.glofas_flag) && <p className="banner" style={{ background: "var(--brand-soft)", color: "var(--brand)", marginTop: 14 }}>{t.river_flag}</p>}
              <div className="callout">
                <span>{subscribed ? `${t.subscribed_for} ${placeLabel(place, lang)}` : t.subscribe_help}</span>
                {subscribed
                  ? <Link href="/alerts" className="btn sm ghost">{s.inbox}</Link>
                  : <Link href="/alerts" className="btn sm" onClick={() => setPlaces([...places, place])}>{Icon.bell}{s.get_alerts}</Link>}
              </div>
            </div>
          )}
          {place && detail && (
            <div className="card">
              <h2>{s.exposure}</h2>
              <p style={{ fontSize: 15 }}>
                <b style={{ fontWeight: 500, color: "var(--ink)" }}>{detail.exposure.high}</b> {s.exp_high} · {detail.exposure.medium} {s.exp_medium} · <span className="tiny">{detail.exposure.villages} {s.exp_of}</span>
              </p>
              {detail.high_villages.length > 0 && (
                <ul className="reasons" style={{ marginTop: 10 }}>{detail.high_villages.slice(0, 10).map((v) => <li key={v.id}>{v.name}</li>)}</ul>
              )}
            </div>
          )}
        </div>

        <div className="stack">
          <SafetyCheck place={place} autoLocate={autoLocate} onLocated={onLocated} />
          {place && detail && (
            <div className="card">
              <h2>{t.shelters}</h2>
              {detail.shelters.slice(0, 4).map((f) => (
                <div key={f.id} className="facility">
                  <span>{f.name}{f.kind === "high_ground" ? ` (${t.high_ground})` : ""}</span>
                  <span className="meta">{f.km} {t.km}</span>
                </div>
              ))}
              <h2 style={{ marginTop: 18 }}>{t.rescue}</h2>
              {detail.rescue_1122.slice(0, 2).map((f) => (
                <div key={f.id} className="facility">
                  <span>{f.name.replace(/^Rescue 1122\s*/, "") || `${t.rescue} · ${f.subtype || ""}`.replace(/ · $/, "")}</span>
                  <span className="meta">{f.km} {t.km}</span>
                </div>
              ))}
              {detail.rescue_1122_control_room && (
                <div className="callout">
                  <span>{s.control_room} · {detail.rescue_1122_control_room.district}</span>
                  <a className="btn sm ghost ltr" href={`tel:${detail.rescue_1122_control_room.control_room.replace(/[^0-9+]/g, "")}`}>{detail.rescue_1122_control_room.control_room}</a>
                </div>
              )}
              <a href="tel:1122" className="btn" style={{ marginTop: 14, width: "100%" }}>{Icon.phone}{S[lang].call_1122}</a>
            </div>
          )}
          <p className="tiny">{t.disclaimer}</p>
        </div>
      </div>
    </div>
  );
}
