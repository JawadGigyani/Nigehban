"use client";

import { useCallback, useEffect, useState } from "react";

import { Icon, LevelBadge, PlaceSearch } from "@/components/site/ui";
import { API_URL, api, ApiError, type InboxAlert } from "@/lib/api";
import { S } from "@/lib/copy";
import { T } from "@/lib/i18n";
import { placeLabel, useSite } from "@/lib/site";

const VAPID = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY || "";

function b64ToUint8(b64: string) {
  const pad = "=".repeat((4 - (b64.length % 4)) % 4);
  const raw = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

export default function AlertsPage() {
  const { lang, deviceId, places, setPlaces, subId, setSubId, resetDevice } = useSite();
  const s = S[lang];
  const t = T[lang];
  const [alerts, setAlerts] = useState<InboxAlert[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [pushOk, setPushOk] = useState(false);
  useEffect(() => setPushOk(!!VAPID && "PushManager" in window), []);

  const refresh = useCallback(() => {
    if (!subId) { setAlerts(null); return; }
    api.inbox(subId).then((r) => setAlerts(r.alerts)).catch((e) => { if (e instanceof ApiError && e.status === 404) setSubId(null); });
  }, [subId, setSubId]);
  useEffect(() => { refresh(); const id = setInterval(refresh, 60_000); return () => clearInterval(id); }, [refresh]);

  const body = (channel: string, address: string) => ({
    channel, address, language: lang,
    tehsil_ids: places.filter((p) => p.type === "tehsil").map((p) => p.id),
    village_ids: places.filter((p) => p.type === "village").map((p) => p.id),
  });
  const subscribe = async () => {
    setBusy(true); setMsg(null);
    try { const sub = await api.subscribe(body("web_inbox", deviceId)); setSubId(sub.id); }
    catch { setMsg({ ok: false, text: t.error }); }
    finally { setBusy(false); }
  };
  const enablePush = async () => {
    try {
      const reg = await navigator.serviceWorker.ready;
      if ((await Notification.requestPermission()) !== "granted") return;
      const push = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToUint8(VAPID) });
      await api.subscribe(body("webpush", JSON.stringify(push.toJSON())));
      setMsg({ ok: true, text: "✓" });
    } catch { setMsg({ ok: false, text: t.error }); }
  };

  return (
    <div className="wrap">
      <div className="page-head">
        <h1>{s.alerts_title}</h1>
        <p>{s.alerts_sub}</p>
      </div>
      <div className="cols">
        <div className="stack">
          <div className="card">
            <h2>{subId ? s.inbox : t.subscribe_title}</h2>
            {!subId && (
              <>
                <span className="tiny">{s.places_label}</span>
                <div className="place-chips">
                  {places.length === 0 && <span className="tiny">—</span>}
                  {places.map((p) => (
                    <span key={p.id} className="place-chip">{placeLabel(p, lang)}
                      <button aria-label={`${s.close} ${p.name}`} onClick={() => setPlaces(places.filter((x) => x.id !== p.id))}>×</button>
                    </span>
                  ))}
                </div>
                <PlaceSearch lang={lang} flat placeholder={s.add_place} onPick={(p) => !places.some((x) => x.id === p.id) && setPlaces([...places, p])} />
                <button className="btn" style={{ marginTop: 14 }} disabled={busy || places.length === 0} onClick={subscribe}>{Icon.bell}{t.subscribe_btn}</button>
              </>
            )}
            {subId && (
              <>
                <p className="tiny">{t.subscribed_for} {places.map((p) => placeLabel(p, lang)).join(" · ")}</p>
                {pushOk && <button className="btn ghost sm" style={{ marginTop: 12 }} onClick={enablePush}>{Icon.bell}{t.push_enable}</button>}
              </>
            )}
            {msg && <p className={`banner ${msg.ok ? "ok" : "err"}`} style={{ marginTop: 12 }}>{msg.text}</p>}
          </div>

          {subId && alerts && alerts.length === 0 && (
            <div className="card empty"><div className="ico">{Icon.bell}</div><h3>{t.no_alerts}</h3><p>{t.subscribe_help}</p></div>
          )}
          {alerts?.map((a) => (
            <div key={a.id} className="alert-card">
              <div className="row" style={{ justifyContent: "space-between" }}>
                <LevelBadge level={a.level} lang={lang} />
                <span className="tiny ltr">{a.valid_date}{a.replay ? " · demo" : ""}</span>
              </div>
              <p>{a.message}</p>
              {a.audio_url && <audio controls preload="none" src={`${API_URL}${a.audio_url}`} style={{ width: "100%", height: 36 }} />}
              <p className="tiny" style={{ margin: "8px 0 0" }}>{t.sources}: {a.citations.map((c) => c.label).filter((v, i, x) => x.indexOf(v) === i).join(" · ")}</p>
            </div>
          ))}
        </div>

        <div className="stack">
          <div className="card">
            <h2>{s.data_title}</h2>
            <p className="muted" style={{ fontSize: 15 }}>{t.my_data_help}</p>
            <div className="row" style={{ marginTop: 14 }}>
              {subId && <button className="btn ghost sm" onClick={async () => { await api.unsubscribe(subId).catch(() => null); setSubId(null); }}>{t.unsubscribe}</button>}
              <button className="btn danger sm" onClick={async () => {
                await api.deleteMyData(deviceId).catch(() => null);
                setSubId(null); resetDevice(); setAlerts(null);
                setMsg({ ok: true, text: t.deleted });
              }}>{t.delete_data}</button>
            </div>
          </div>
          <div className="card">
            <h2>{s.footer_help}</h2>
            <div className="facility"><span>{s.rescue}</span><a className="btn sm ghost ltr" href="tel:1122">1122</a></div>
            <div className="facility"><span>{s.pdma}</span><a className="btn sm ghost ltr" href="tel:1700">1700</a></div>
          </div>
        </div>
      </div>
    </div>
  );
}
