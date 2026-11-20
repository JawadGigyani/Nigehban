"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import type { Lang } from "@/lib/api";
import { S } from "@/lib/copy";
import { useSite } from "@/lib/site";
import { Icon, Logo } from "./ui";

export const NAV: { href: string; key: string }[] = [
  { href: "/area", key: "nav_area" },
  { href: "/map", key: "nav_map" },
  { href: "/ask", key: "nav_ask" },
  { href: "/alerts", key: "nav_alerts" },
  { href: "/safety", key: "nav_safety" },
];

function LangSwitch({ lang, setLang }: { lang: Lang; setLang: (l: Lang) => void }) {
  return (
    <div className="seg-lang" role="group" aria-label="Language / زبان">
      <button className={lang !== "ur" ? "on" : ""} onClick={() => setLang("en")} aria-pressed={lang !== "ur"}>EN</button>
      <button className={`ur-btn ${lang === "ur" ? "on" : ""}`} onClick={() => setLang("ur")} lang="ur" aria-pressed={lang === "ur"}>اردو</button>
    </div>
  );
}

export default function Header() {
  const { lang, setLang, asOf, setAsOf } = useSite();
  const s = S[lang];
  const path = usePathname();
  const [scrolled, setScrolled] = useState(false);
  const [sheet, setSheet] = useState(false);
  useEffect(() => {
    const h = () => setScrolled(window.scrollY > 8);
    h();
    window.addEventListener("scroll", h, { passive: true });
    return () => window.removeEventListener("scroll", h);
  }, []);
  useEffect(() => setSheet(false), [path]);
  useEffect(() => {
    if (!sheet) return;
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") setSheet(false); };
    document.addEventListener("keydown", k);
    return () => document.removeEventListener("keydown", k);
  }, [sheet]);

  return (
    <>
      <a href="#main" className="skip">Skip to content</a>
      <header className={`site-header ${scrolled ? "scrolled" : ""}`}>
        <div className="wrap">
          <Link href="/" aria-label="Nigehban home"><Logo withUrdu={false} /></Link>
          <nav className="nav" aria-label="Main">
            {NAV.map((n) => <Link key={n.href} href={n.href} className={path === n.href ? "on" : ""} aria-current={path === n.href ? "page" : undefined}>{s[n.key]}</Link>)}
          </nav>
          <div className="header-end">
            <LangSwitch lang={lang} setLang={setLang} />
            <Link href="/alerts" className="btn sm">{Icon.bell}{s.get_alerts}</Link>
            <button className="menu-btn" onClick={() => setSheet(true)} aria-label={s.menu} aria-expanded={sheet}>{Icon.menu}</button>
          </div>
        </div>
      </header>
      {asOf && (
        <div className="demo-bar">
          <div className="wrap">
            <span>{s.replay_banner} <b className="ltr">{asOf.slice(0, 10)}</b></span>
            <button onClick={() => setAsOf(null)}>{s.back_live}</button>
          </div>
        </div>
      )}
      {sheet && (
        <div className="sheet" onClick={() => setSheet(false)}>
          <div className="sheet-card" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={s.menu}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <Logo withUrdu={false} />
              <button className="menu-btn" style={{ display: "inline-flex" }} onClick={() => setSheet(false)} aria-label={s.close}>{Icon.close}</button>
            </div>
            <nav aria-label="Main">
              <Link href="/" className={path === "/" ? "on" : ""}>{s.nav_home}</Link>
              {NAV.map((n) => <Link key={n.href} href={n.href} className={path === n.href ? "on" : ""}>{s[n.key]}</Link>)}
            </nav>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <LangSwitch lang={lang} setLang={setLang} />
              <Link href="/alerts" className="btn sm">{Icon.bell}{s.get_alerts}</Link>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
