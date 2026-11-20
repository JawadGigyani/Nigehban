"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

/**
 * Entrance motion: elements with class "reveal" fade (and rise a few pixels) the first time they
 * scroll into view; `style={{ "--d": "80ms" }}` staggers siblings. When the system asks for reduced
 * motion, CSS keeps only gentle fades (no movement, no looping effects). Without JS, content shows.
 */
export default function Motion() {
  const path = usePathname();
  useEffect(() => {
    document.documentElement.classList.add("motion");
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
      });
    }, { rootMargin: "0px 0px -6% 0px", threshold: 0.05 });
    const watch = () => document.querySelectorAll(".reveal:not(.in)").forEach((el) => io.observe(el));
    watch();
    const mo = new MutationObserver(watch);
    mo.observe(document.body, { childList: true, subtree: true });
    return () => { io.disconnect(); mo.disconnect(); };
  }, [path]);
  return null;
}
