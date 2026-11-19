"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  API_URL,
  api,
  ApiError,
  type GeoCheck,
  type SafeRoute,
  type ChatResult,
  type InboxAlert,
  type Lang,
  type Place,
  type RiskResponse,
  type TehsilDetail,
} from "@/lib/api";
import { DRIVER_NAMES, LEVEL_NAMES, T, dayLabel, isRtl } from "@/lib/i18n";

type Tab = "risk" | "alerts" | "ask" | "me";
const DEMO_AS_OF = "2025-08-14T09:00:00+05:00"; // the day before the Buner cloudburst
const VAPID = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY || "";

// ---- small helpers ---------------------------------------------------------------------------

function load<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(`nigehban:${key}`);
    return v === null ? fallback : (JSON.parse(v) as T);
  } catch {
    return fallback;
  }
}
function save(key: string, value: unknown) {
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
function placeLabel(p: Place, lang: Lang) {
  if (lang === "ur" && p.label_ur) return p.label_ur;
  return p.type === "village" && p.tehsil ? `${p.name} (${p.tehsil})` : p.name;
}
function b64ToUint8(b64: string) {
  const pad = "=".repeat((4 - (b64.length % 4)) % 4);
  const raw = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

const ICONS: Record<Tab, React.ReactElement> = {
  risk: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 3c-3 4.5-6 7.7-6 11a6 6 0 0 0 12 0c0-3.3-3-6.5-6-11z" /></svg>,
  alerts: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0" /></svg>,
  ask: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" /></svg>,
  me: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></svg>,
};

// ---- place search ----------------------------------------------------------------------------

function PlaceSearch({ lang, onPick }: { lang: Lang; onPick: (p: Place) => void }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Place[]>([]);
  useEffect(() => {
    if (q.trim().length < 2) {
      setHits([]);
      return;
    }
    const id = setTimeout(() => api.search(q.trim()).then(setHits).catch(() => setHits([])), 250);
    return () => clearTimeout(id);
  }, [q]);
  return (
    <div className="search">
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={T[lang].search_place} aria-label={T[lang].search_place} />
      {hits.length > 0 && (
        <div className="results">
          {hits.map((p) => (
            <button key={p.id} onClick={() => { onPick(p); setQ(""); setHits([]); }}>
              {placeLabel(p, lang)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---- tabs ------------------------------------------------------------------------------------

function RiskTab({ lang, place, setPlace, asOf }: { lang: Lang; place: Place | null; setPlace: (p: Place) => void; asOf: string | null }) {
  const t = T[lang];
  const [risk, setRisk] = useState<RiskResponse | null>(null);
  const [detail, setDetail] = useState<TehsilDetail | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    setRisk(null);
    setError(false);
    api.risk(asOf).then(setRisk).catch(() => setError(true));
  }, [asOf]);
  useEffect(() => {
    setDetail(null);
    if (place) api.tehsil(place.tehsil_id, asOf).then(setDetail).catch(() => setDetail(null));
  }, [place, asOf]);

  const row = risk?.tehsils.find((r) => r.tehsil_id === place?.tehsil_id);
  return (
    <>
      <PlaceSearch lang={lang} onPick={setPlace} />
      {!place && <div className="card"><p className="muted">{t.choose_place}</p></div>}
      {error && <div className="banner err">{t.error}</div>}
      {place && !risk && !error && <div className="card muted">{t.loading}</div>}
      {place && row && (
        <div className="card">
          <h2>{placeLabel(place, lang)}</h2>
          <div className="days">
            {row.days.map((d) => (
              <div key={d.date} className={`day lvl-${d.level}`}>
                <span className="when">{dayLabel(lang, d.lead_days)}</span>
                <span className="lvl">{LEVEL_NAMES[lang][d.level]}</span>
                <span className="date">{new Date(d.date).toLocaleDateString(lang === "ur" ? "ur-PK" : "en-GB", { day: "numeric", month: "short" })}</span>
              </div>
            ))}
          </div>
          {(() => {
            const top = [...row.days].sort((a, b) => b.probability - a.probability)[0];
            const reasons = top.driver_codes.map((c) => DRIVER_NAMES[lang][c]).filter(Boolean);
            return (
              <>
                {reasons.length > 0 && (
                  <>
                    <p className="muted" style={{ margin: "10px 0 0" }}>{t.reasons}:</p>
                    <ul className="reasons">{reasons.map((r) => <li key={r}>{r}</li>)}</ul>
                  </>
                )}
                {row.days.some((d) => d.glofas_flag) && <p className="muted">⚠ {t.river_flag}</p>}
              </>
            );
          })()}
        </div>
      )}
      {place && detail && (
        <div className="card">
          <h2>{t.shelters}</h2>
          {detail.shelters.slice(0, 3).map((f) => (
            <div key={f.id} className="facility">
              <span>{f.name || t.unnamed_shelter}{f.kind === "high_ground" ? ` (${t.high_ground})` : ""} <span className="pill">{t.unverified}</span></span>
              <span className="tiny">{f.km} {t.km}</span>
            </div>
          ))}
          {detail.rescue_1122.slice(0, 1).map((f) => (
            <div key={f.id} className="facility">
              <span>{t.rescue}: {f.name.replace("Rescue 1122 ", "")} <span className="pill">{t.unverified}</span></span>
              <span className="tiny">{f.km} {t.km}</span>
            </div>
          ))}
          <p className="muted" style={{ marginBottom: 0 }}>☎ {t.call_1122}</p>
        </div>
      )}
      <SafetyCard lang={lang} place={place} asOf={asOf} />
      <p className="tiny">{t.disclaimer}</p>
    </>
  );
}


function SafetyCard({ lang, place, asOf }: { lang: Lang; place: Place | null; asOf: string | null }) {
  const t = T[lang];
  const [check, setCheck] = useState<GeoCheck | null>(null);
  const [route, setRoute] = useState<SafeRoute | null>(null);
  const [point, setPoint] = useState<[number, number] | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const run = async (lat: number, lon: number) => {
    setBusy(true); setMsg(null); setRoute(null); setPoint([lat, lon]);
    try { setCheck(await api.geoCheck(lat, lon, asOf)); } catch (e) { setMsg(e instanceof ApiError ? e.message : t.error); }
    finally { setBusy(false); }
  };
  const here = () => {
    if (!("geolocation" in navigator)) { setMsg(t.no_gps); return; }
    navigator.geolocation.getCurrentPosition((p) => run(p.coords.latitude, p.coords.longitude), () => setMsg(t.no_gps),
      { enableHighAccuracy: true, timeout: 15000 });
  };
  const findRoute = async () => {
    if (!point) return;
    setBusy(true); setMsg(null);
    try { setRoute(await api.route(point[0], point[1], "walk")); } catch (e) { setMsg(e instanceof ApiError ? e.message : t.error); }
    finally { setBusy(false); }
  };
  const tone = check?.advice === "move_away" ? "lvl-very_high" : check?.advice === "be_ready" ? "lvl-high" : "";
  return (
    <div className="card">
      <h2>{t.safety}</h2>
      <div className="row">
        <button className="btn" onClick={here} disabled={busy}>{t.check_here}</button>
        {place?.lat !== undefined && place?.lon !== undefined && (
          <button className="btn secondary" onClick={() => run(place.lat!, place.lon!)} disabled={busy}>{t.check_place}</button>
        )}
      </div>
      {busy && <p className="muted">{t.loading}</p>}
      {check && (
        <div className={`banner ${tone}`} style={{ marginTop: 10, color: tone ? "#fff" : undefined, background: tone ? undefined : "var(--surface-2)" }}>
          <b>{check.advice_text[lang]}</b>
          {check.level_today_tomorrow && <div className="tiny" style={{ color: "inherit" }}>{LEVEL_NAMES[lang][check.level_today_tomorrow]}</div>}
        </div>
      )}
      {check && check.advice !== "normal" && !route && (
        <button className="btn" style={{ marginTop: 10 }} onClick={findRoute} disabled={busy}>{t.route}</button>
      )}
      {route && point && (
        <div style={{ marginTop: 10 }}>
          <div className="facility">
            <span>{route.destination.name || (route.destination.kind === "high_ground" ? t.high_ground : t.unnamed_shelter)} <span className="pill">{t.unverified}</span></span>
            <span className="tiny">{(route.distance_m / 1000).toFixed(1)} {t.km} · {Math.round(route.duration_min)} {t.walk_min}</span>
          </div>
          {route.low_ground_share !== null && route.low_ground_share > 0.2 && <p className="muted">{t.low_ground_route}</p>}
          <a className="btn secondary" style={{ display: "inline-block", textDecoration: "none", marginTop: 6 }} target="_blank" rel="noreferrer"
            href={`https://www.openstreetmap.org/directions?engine=fossgis_osrm_foot&route=${point[0]}%2C${point[1]}%3B${route.destination.lat}%2C${route.destination.lon}`}>
            {t.open_map}
          </a>
        </div>
      )}
      {msg && <p className="muted">{msg}</p>}
    </div>
  );
}

function AlertsTab({ lang, deviceId, places, setPlaces, subId, setSubId }: {
  lang: Lang; deviceId: string; places: Place[]; setPlaces: (p: Place[]) => void; subId: string | null; setSubId: (id: string | null) => void;
}) {
  const t = T[lang];
  const [alerts, setAlerts] = useState<InboxAlert[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const refresh = useCallback(() => {
    if (!subId) return;
    api.inbox(subId).then((r) => setAlerts(r.alerts)).catch((e) => {
      if (e instanceof ApiError && e.status === 404) setSubId(null);
    });
  }, [subId, setSubId]);
  useEffect(() => { refresh(); const id = setInterval(refresh, 60_000); return () => clearInterval(id); }, [refresh]);

  const subscribe = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const body = {
        channel: "web_inbox", address: deviceId, language: lang,
        tehsil_ids: places.filter((p) => p.type === "tehsil").map((p) => p.id),
        village_ids: places.filter((p) => p.type === "village").map((p) => p.id),
      };
      const sub = await api.subscribe(body);
      setSubId(sub.id);
    } catch {
      setMsg(t.error);
    } finally {
      setBusy(false);
    }
  };

  const enablePush = async () => {
    try {
      const reg = await navigator.serviceWorker.ready;
      if ((await Notification.requestPermission()) !== "granted") return;
      const push = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToUint8(VAPID) });
      await api.subscribe({
        channel: "webpush", address: JSON.stringify(push.toJSON()), language: lang,
        tehsil_ids: places.filter((p) => p.type === "tehsil").map((p) => p.id),
        village_ids: places.filter((p) => p.type === "village").map((p) => p.id),
      });
      setMsg("✓");
    } catch {
      setMsg(t.error);
    }
  };

  return (
    <>
      <div className="card">
        <h2>{t.subscribe_title}</h2>
        <p className="muted">{subId ? t.subscribed_for : t.subscribe_help}</p>
        <div className="row" style={{ marginBottom: 10 }}>
          {places.map((p) => (
            <span key={p.id} className="pill">
              {placeLabel(p, lang)}{" "}
              {!subId && <button aria-label="remove" style={{ border: 0, background: "none", cursor: "pointer" }} onClick={() => setPlaces(places.filter((x) => x.id !== p.id))}>×</button>}
            </span>
          ))}
        </div>
        {!subId && (
          <>
            <PlaceSearch lang={lang} onPick={(p) => !places.some((x) => x.id === p.id) && setPlaces([...places, p])} />
            <div className="row" style={{ marginTop: 10 }}>
              <button className="btn" disabled={busy || places.length === 0} onClick={subscribe}>{t.subscribe_btn}</button>
            </div>
          </>
        )}
        {subId && VAPID && typeof window !== "undefined" && "PushManager" in window && (
          <button className="btn secondary" onClick={enablePush}>{t.push_enable}</button>
        )}
        {msg && <p className="muted">{msg}</p>}
      </div>
      {subId && alerts && alerts.length === 0 && <div className="card muted">{t.no_alerts}</div>}
      {alerts?.map((a) => (
        <div key={a.id} className={`card alert-item lvl-b-${a.level}`}>
          <div className="row">
            <span className={`pill lvl-${a.level}`} style={{ color: "#fff" }}>{LEVEL_NAMES[lang][a.level]}</span>
            <span className="tiny">{a.valid_date}{a.replay ? " · demo" : ""}</span>
          </div>
          <p>{a.message}</p>
          {a.audio_url && <audio controls preload="none" src={`${API_URL}${a.audio_url}`} style={{ width: "100%" }} />}
          <p className="tiny">{T[lang].sources}: {a.citations.map((c) => c.label).filter((v, i, s) => s.indexOf(v) === i).join(" · ")}</p>
        </div>
      ))}
    </>
  );
}

function ListenButton({ text, label }: { text: string; label: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (url) return <audio controls autoPlay src={url} style={{ width: "100%", marginTop: 6 }} />;
  return (
    <button className="btn secondary" style={{ padding: "4px 10px", marginTop: 6 }} disabled={busy}
      onClick={async () => { setBusy(true); try { const r = await api.tts(text); setUrl(`${API_URL}${r.audio_url}`); } catch { /* voice optional */ } finally { setBusy(false); } }}>
      🔊 {label}
    </button>
  );
}

function AskTab({ lang, place, asOf }: { lang: Lang; place: Place | null; asOf: string | null }) {
  const t = T[lang];
  const [voice, setVoice] = useState(false);
  useEffect(() => { api.config().then((c) => setVoice(c.voice)).catch(() => setVoice(false)); }, []);
  const [items, setItems] = useState<{ role: "user" | "bot"; text: string; result?: ChatResult }[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const session = useRef<string | undefined>(undefined);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [items]);

  const send = async () => {
    const message = text.trim();
    if (!message || busy) return;
    setText("");
    setItems((x) => [...x, { role: "user", text: message }]);
    setBusy(true);
    try {
      const r = await api.chat({ message, session_id: session.current, language: lang, tehsil_id: place?.tehsil_id, as_of: asOf });
      session.current = r.session_id;
      setItems((x) => [...x, { role: "bot", text: r.answer, result: r }]);
    } catch {
      setItems((x) => [...x, { role: "bot", text: t.error }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="chat">
        {items.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.text}
            {m.result && m.result.actions.length > 0 && (
              <ul className="reasons">{m.result.actions.map((a, j) => <li key={j}>{a.text}</li>)}</ul>
            )}
            {m.result && voice && lang === "ur" && <ListenButton text={m.text} label={t.listen} />}
            {m.result && (
              <div className="tiny" style={{ marginTop: 6 }}>
                {m.result.checked ? "✓ " + t.checked : t.not_checked}
                {m.result.citations.length > 0 && (
                  <> · {t.sources}: {m.result.citations.map((c) => c.label).filter((v, k, s) => s.indexOf(v) === k).slice(0, 3).join(" · ")}</>
                )}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="msg bot muted">…</div>}
        <div ref={end} />
      </div>
      <div className="chat-input">
        <textarea rows={2} value={text} placeholder={t.ask_placeholder} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
        <button className="btn" onClick={send} disabled={busy || !text.trim()}>{t.send}</button>
      </div>
    </>
  );
}

function MeTab({ lang, setLang, asOf, setAsOf, subId, setSubId, deviceId, resetDevice }: {
  lang: Lang; setLang: (l: Lang) => void; asOf: string | null; setAsOf: (v: string | null) => void;
  subId: string | null; setSubId: (v: string | null) => void; deviceId: string; resetDevice: () => void;
}) {
  const t = T[lang];
  const [msg, setMsg] = useState<string | null>(null);
  const [installEvt, setInstallEvt] = useState<any>(null);
  useEffect(() => {
    const h = (e: Event) => { e.preventDefault(); setInstallEvt(e); };
    window.addEventListener("beforeinstallprompt", h);
    return () => window.removeEventListener("beforeinstallprompt", h);
  }, []);
  return (
    <>
      <div className="card">
        <h2>{t.language}</h2>
        <div className="row">
          {(["ur", "en", "ur_roman"] as Lang[]).map((l) => (
            <button key={l} className={`btn ${lang === l ? "" : "secondary"}`} onClick={() => setLang(l)}>
              {l === "ur" ? "اردو" : l === "en" ? "English" : "Roman Urdu"}
            </button>
          ))}
        </div>
      </div>
      <div className="card">
        <h2>{t.demo}</h2>
        <div className="row">
          <button className={`btn ${asOf ? "secondary" : ""}`} onClick={() => setAsOf(null)}>{t.live}</button>
          <button className={`btn ${asOf ? "" : "secondary"}`} onClick={() => setAsOf(DEMO_AS_OF)}>14 Aug 2025 (Buner)</button>
        </div>
      </div>
      <div className="card">
        <h2>{t.my_data}</h2>
        <p className="muted">{t.my_data_help}</p>
        <div className="row">
          {subId && (
            <button className="btn secondary" onClick={async () => { await api.unsubscribe(subId).catch(() => null); setSubId(null); }}>
              {t.unsubscribe}
            </button>
          )}
          <button className="btn danger" onClick={async () => {
            await api.deleteMyData(deviceId).catch(() => null);
            setSubId(null);
            resetDevice();
            setMsg(t.deleted);
          }}>{t.delete_data}</button>
        </div>
        {msg && <p className="muted">{msg}</p>}
      </div>
      {installEvt && <button className="btn" onClick={() => installEvt.prompt()}>{t.install}</button>}
    </>
  );
}

// ---- app shell ---------------------------------------------------------------------------------

export default function CitizenApp() {
  const [hydrated, setHydrated] = useState(false);
  const [lang, setLangState] = useState<Lang>("ur");
  const [tab, setTab] = useState<Tab>("risk");
  const [place, setPlaceState] = useState<Place | null>(null);
  const [places, setPlacesState] = useState<Place[]>([]);
  const [subId, setSubIdState] = useState<string | null>(null);
  const [asOf, setAsOfState] = useState<string | null>(null);
  const [deviceId, setDeviceId] = useState("");

  useEffect(() => {
    setLangState(load<Lang>("lang", "ur"));
    setPlaceState(load<Place | null>("place", null));
    setPlacesState(load<Place[]>("places", []));
    setSubIdState(load<string | null>("sub", null));
    setAsOfState(load<string | null>("asOf", null));
    let id = load<string>("device", "");
    if (!id) { id = randomId(); save("device", id); }
    setDeviceId(id);
    const q = new URLSearchParams(window.location.search).get("tab");
    if (q === "alerts" || q === "ask" || q === "me") setTab(q);
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => null);
    setHydrated(true);
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang === "en" ? "en" : "ur";
    document.documentElement.dir = isRtl(lang) ? "rtl" : "ltr";
  }, [lang]);

  const setLang = (l: Lang) => { setLangState(l); save("lang", l); };
  const setPlace = (p: Place) => { setPlaceState(p); save("place", p); };
  const setPlaces = (p: Place[]) => { setPlacesState(p); save("places", p); };
  const setSubId = (v: string | null) => { setSubIdState(v); save("sub", v); };
  const setAsOf = (v: string | null) => { setAsOfState(v); save("asOf", v); };
  const resetDevice = () => {
    const id = randomId();
    save("device", id); setDeviceId(id); setPlaces([]);
  };

  // Subscribed places double as the default place on the Risk tab.
  const effectivePlace = useMemo(() => place ?? places[0] ?? null, [place, places]);
  const t = T[lang];
  if (!hydrated) return <div className="app" />;

  return (
    <div className={`app ${lang === "ur" ? "ur" : ""}`}>
      <header className="app-header">
        <div>
          <h1>{t.app}</h1>
          <p className="tagline">{t.tagline}</p>
        </div>
        <div className="lang-switch" role="group" aria-label={t.language}>
          <button className={`ur-btn ${lang === "ur" ? "on" : ""}`} onClick={() => setLang("ur")}>اردو</button>
          <button className={lang === "en" ? "on" : ""} onClick={() => setLang("en")}>EN</button>
          <button className={lang === "ur_roman" ? "on" : ""} onClick={() => setLang("ur_roman")}>Roman</button>
        </div>
      </header>
      <main className="content">
        {asOf && <div className="banner demo">{t.replay_note} ({asOf.slice(0, 10)})</div>}
        {tab === "risk" && <RiskTab lang={lang} place={effectivePlace} setPlace={setPlace} asOf={asOf} />}
        {tab === "alerts" && <AlertsTab lang={lang} deviceId={deviceId} places={places} setPlaces={setPlaces} subId={subId} setSubId={setSubId} />}
        {tab === "ask" && <AskTab lang={lang} place={effectivePlace} asOf={asOf} />}
        {tab === "me" && <MeTab lang={lang} setLang={setLang} asOf={asOf} setAsOf={setAsOf} subId={subId} setSubId={setSubId} deviceId={deviceId} resetDevice={resetDevice} />}
      </main>
      <nav className="tabbar">
        <div className="tabbar-inner">
          {(["risk", "alerts", "ask", "me"] as Tab[]).map((k) => (
            <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)} aria-current={tab === k}>
              {ICONS[k]}
              <span>{t[`tab_${k}`]}</span>
            </button>
          ))}
        </div>
      </nav>
    </div>
  );
}
