"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

/**
 * Subtle entrance motion: elements with class "reveal" fade and rise a few pixels the first time
 * they scroll into view. `style={{ "--d": "80ms" }}` staggers siblings. Without JS, or with
 * reduced motion, content is simply shown (CSS only hides it under html.motion).
 */
export default function Motion() {
  const path = usePathname();
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    document.documentElement.classList.add("motion");
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.05 });
    const watch = () => document.querySelectorAll(".reveal:not(.in)").forEach((el) => io.observe(el));
    watch();
    const mo = new MutationObserver(watch);
    mo.observe(document.body, { childList: true, subtree: true });
    return () => { io.disconnect(); mo.disconnect(); };
  }, [path]);
  return null;
}
