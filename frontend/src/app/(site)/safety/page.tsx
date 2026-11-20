"use client";

import Link from "next/link";

import { Icon } from "@/components/site/ui";
import { S } from "@/lib/copy";
import { useSite } from "@/lib/site";

export default function SafetyPage() {
  const { lang } = useSite();
  const s = S[lang];
  const groups: [string, string[]][] = [
    [s.before, ["b1", "b2", "b3", "b4"]],
    [s.during, ["d1", "d2", "d3", "d4"]],
    [s.after, ["a1", "a2", "a3", "a4"]],
  ];
  return (
    <div className="wrap">
      <div className="page-head">
        <h1>{s.safety_page_title}</h1>
        <p>{s.safety_page_sub}</p>
      </div>
      <div className="guide">
        {groups.map(([title, keys], i) => (
          <div key={title} className="card">
            <h2><span className="n">{i + 1}</span>{title}</h2>
            <ul>{keys.map((k) => <li key={k}>{Icon.check}<span>{s[k]}</span></li>)}</ul>
          </div>
        ))}
      </div>
      <h2 className="h-section" style={{ fontSize: 28, marginTop: 56 }}>{s.numbers}</h2>
      <div className="numbers">
        <div className="card number-card">
          <div><span className="muted">{s.rescue}</span><br /><b>1122</b></div>
          <a href="tel:1122" className="btn">{Icon.phone}{s.call_1122}</a>
        </div>
        <div className="card number-card">
          <div><span className="muted">{s.pdma}</span><br /><b>1700</b></div>
          <a href="tel:1700" className="btn ghost">{Icon.phone}1700</a>
        </div>
      </div>
      <div className="callout" style={{ marginTop: 24, padding: "16px 18px" }}>
        <span>{s.b_safe_d}</span>
        <Link href="/area" className="btn sm">{s.nav_area}{Icon.arrow}</Link>
      </div>
    </div>
  );
}
