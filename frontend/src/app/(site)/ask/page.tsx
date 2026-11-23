"use client";

import { useEffect, useRef, useState } from "react";

import { Icon } from "@/components/site/ui";
import { API_URL, api, type ChatResult } from "@/lib/api";
import { S } from "@/lib/copy";
import { T } from "@/lib/i18n";
import { placeLabel, useSite } from "@/lib/site";

function Listen({ text, label }: { text: string; label: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (url) return <audio controls autoPlay src={url} style={{ width: "100%", marginTop: 10, height: 36 }} />;
  return (
    <button className="btn ghost sm" style={{ marginTop: 10 }} disabled={busy}
      onClick={async () => { setBusy(true); try { const r = await api.tts(text); setUrl(`${API_URL}${r.audio_url}`); } catch { /* voice optional */ } finally { setBusy(false); } }}>
      {Icon.speaker}{label}
    </button>
  );
}

type Item = { role: "user" | "bot"; text: string; result?: ChatResult };

export default function AskPage() {
  const { lang, asOf, place } = useSite();
  const s = S[lang];
  const t = T[lang];
  const [voice, setVoice] = useState(false);
  const [items, setItems] = useState<Item[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const session = useRef<string | undefined>(undefined);
  const end = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { api.config().then((c) => setVoice(c.voice)).catch(() => setVoice(false)); }, []);
  useEffect(() => { if (items.length) end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [items, busy]);
  useEffect(() => {
    const el = input.current;
    if (el) { el.style.height = "auto"; el.style.height = `${Math.min(el.scrollHeight, 160)}px`; }
  }, [text]);

  const send = async (raw?: string) => {
    const message = (raw ?? text).trim();
    if (!message || busy) return;
    setText("");
    setItems((x) => [...x, { role: "user", text: message }]);
    setBusy(true);
    try {
      const r = await api.chat({ message, session_id: session.current, tehsil_id: place?.tehsil_id, as_of: asOf });
      session.current = r.session_id;
      setItems((x) => [...x, { role: "bot", text: r.answer, result: r }]);
    } catch {
      setItems((x) => [...x, { role: "bot", text: t.error }]);
    } finally {
      setBusy(false);
      input.current?.focus();
    }
  };

  return (
    <div className="wrap">
      <div className="ask-wrap">
        <div className="page-head" style={{ textAlign: items.length ? "start" : "center", paddingBottom: items.length ? 12 : 28 }}>
          <h1>{s.ask_title}</h1>
          {!items.length && <p style={{ marginInline: "auto" }}>{s.ask_sub}</p>}
          {place && <p className="tiny" style={{ marginTop: 8, marginInline: items.length ? 0 : "auto" }}>{s.about_place}: {placeLabel(place, lang)}</p>}
        </div>

        {!items.length && (
          <div style={{ textAlign: "center", marginBottom: 28 }}>
            <span className="tiny">{s.try_asking}</span>
            <div className="suggest">
              {["q1", "q2", "q3"].map((k) => <button key={k} onClick={() => send(s[k])}>{s[k]}</button>)}
            </div>
          </div>
        )}

        <div className="chat" aria-live="polite">
          {items.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              {m.text}
              {m.result && m.result.actions.length > 0 && <ul className="actions">{m.result.actions.map((a, j) => <li key={j}>{a.text}</li>)}</ul>}
              {m.result && voice && lang === "ur" && <Listen text={m.text} label={t.listen} />}
              {/* "Checked" only means something when the answer rests on cited sources. */}
              {m.result && m.result.citations.length > 0 && (
                <div className="src">
                  <span className={`badge ${m.result.checked ? "low" : "neutral"}`}>{m.result.checked ? t.checked : t.not_checked}</span>
                  <span>{t.sources}: {m.result.citations.map((c) => c.label).filter((v, k, a) => a.indexOf(v) === k).slice(0, 3).join(" · ")}</span>
                </div>
              )}
            </div>
          ))}
          {busy && <div className="msg bot"><span className="typing"><i /><i /><i /></span></div>}
          <div ref={end} />
        </div>

        <form className="composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <textarea ref={input} rows={1} value={text} placeholder={t.ask_placeholder} aria-label={s.ask_title}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
          <button className="btn" type="submit" disabled={busy || !text.trim()} aria-label={t.send}>{t.send}</button>
        </form>
        <p className="tiny" style={{ textAlign: "center", marginTop: 12 }}>{t.disclaimer}</p>
      </div>
    </div>
  );
}
