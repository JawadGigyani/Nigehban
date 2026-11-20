"use client";

import Link from "next/link";

import { S } from "@/lib/copy";
import { T } from "@/lib/i18n";
import { REPLAYS, useSite } from "@/lib/site";
import { NAV } from "./Header";
import { Logo } from "./ui";

export default function Footer() {
  const { lang, asOf, setAsOf } = useSite();
  const s = S[lang];
  return (
    <footer className="site-footer">
      <div className="wrap">
        <div className="footer-grid">
          <div>
            <Logo withUrdu={false} />
            <p style={{ marginTop: 12, maxWidth: 340 }}>{s.footer_about}</p>
            <p className="tiny" style={{ marginTop: 10, maxWidth: 340 }}>{T[lang].disclaimer}</p>
          </div>
          <div>
            <h4>Nigehban</h4>
            {NAV.map((n) => <Link key={n.href} href={n.href}>{s[n.key]}</Link>)}
          </div>
          <div>
            <h4>{s.footer_help}</h4>
            <a href="tel:1122">{s.rescue} · <span className="ltr">1122</span></a>
            <a href="tel:1700">{s.pdma} · <span className="ltr">1700</span></a>
            <h4 style={{ marginTop: 18 }}>PDMA · Districts</h4>
            <Link href="/board">{s.footer_board}</Link>
          </div>
          <div>
            <h4>{s.replay_title}</h4>
            <p className="tiny" style={{ marginBottom: 6 }}>{s.replay_help}</p>
            {REPLAYS.map((r) => (
              <button key={r.asOf} className={`footer-link ${asOf === r.asOf ? "on" : ""}`}
                onClick={() => { setAsOf(r.asOf); window.scrollTo({ top: 0, behavior: "smooth" }); }}>{s[r.key]}</button>
            ))}
            {asOf && <button className="footer-link" onClick={() => setAsOf(null)}>{s.back_live}</button>}
          </div>
        </div>
        <div className="footer-base"><span>{s.footer_sources}</span></div>
      </div>
    </footer>
  );
}
