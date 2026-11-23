import { describe, expect, it } from "vitest";

import { LEVEL_ORDER } from "./api";
import { ADVICE, S } from "./copy";
import { DRIVER_NAMES, LEVEL_NAMES, T, dayLabel, isRtl } from "./i18n";

const URDU = /[؀-ۿ]/;

describe("website copy", () => {
  it("has the same keys in English and Urdu", () => {
    expect(Object.keys(S.ur).sort()).toEqual(Object.keys(S.en).sort());
    expect(Object.keys(T.ur).sort()).toEqual(Object.keys(T.en).sort());
    expect(Object.keys(DRIVER_NAMES.ur).sort()).toEqual(Object.keys(DRIVER_NAMES.en).sort());
  });

  it("has no empty strings, and Urdu strings are in Urdu script", () => {
    for (const [key, en] of Object.entries(S.en)) {
      expect(en.trim(), key).not.toBe("");
      expect(S.ur[key].trim(), key).not.toBe("");
    }
    for (const key of ["hero_title", "nav_map", "get_alerts", "safety_title", "what_to_do"]) {
      expect(S.ur[key], key).toMatch(URDU);
    }
  });

  it("is English and Urdu only: Roman Urdu falls back to English", () => {
    expect(S.ur_roman).toBe(S.en);
    expect(ADVICE.ur_roman).toEqual(ADVICE.en);
  });

  it("never claims delivery the website does not have", () => {
    const text = [...Object.values(S.en), ...Object.values(T.en)].join(" ").toLowerCase();
    for (const claim of ["on your phone", "sms", "whatsapp", "notification", "install app", "challenge"]) {
      expect(text, claim).not.toContain(claim);
    }
  });

  it("gives advice and a name for every level in both languages", () => {
    for (const lang of ["en", "ur"] as const) {
      for (const level of LEVEL_ORDER) {
        expect(ADVICE[lang][level]).toBeTruthy();
        expect(LEVEL_NAMES[lang][level]).toBeTruthy();
      }
    }
  });

  it("labels days and direction", () => {
    expect(dayLabel("en", 0)).toBe("Today");
    expect(dayLabel("en", 1)).toBe("Tomorrow");
    expect(dayLabel("ur", 0)).toMatch(URDU);
    expect(isRtl("ur")).toBe(true);
    expect(isRtl("en")).toBe(false);
  });
});
