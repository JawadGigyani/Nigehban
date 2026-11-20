"use client";

import Link from "next/link";

import { S } from "@/lib/copy";
import { T } from "@/lib/i18n";
import { useSite } from "@/lib/site";
import { NAV } from "./Header";
import { Logo } from "./ui";

export default function Footer() {
  const { lang } = useSite();
  const s = S[lang];
  return (
    <footer className="site-footer">
      <div className="wrap">
        <div className="footer-grid">
          <div>
            <Logo withUrdu={lang !== "ur"} />
            <p style={{ marginTop: 12, maxWidth: 360 }}>{s.footer_about}</p>
          </div>
          <div>
            <h4>Nigehban</h4>
            {NAV.map((n) => <Link key={n.href} href={n.href}>{s[n.key]}</Link>)}
          </div>
          <div>
            <h4>{s.footer_help}</h4>
            <a href="tel:1122">{s.rescue} · <span className="ltr">1122</span></a>
            <a href="tel:1700">{s.pdma} · <span className="ltr">1700</span></a>
          </div>
          <div>
            <h4>PDMA · Districts</h4>
            <Link href="/board">{s.footer_board}</Link>
          </div>
        </div>
        <div className="footer-base">
          <span>{T[lang].disclaimer}</span>
          <span>{s.footer_sources}</span>
        </div>
      </div>
    </footer>
  );
}
