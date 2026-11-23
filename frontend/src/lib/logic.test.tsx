import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { LevelStrip } from "@/components/site/ui";

import { LEVEL_COLORS, type Level, type Place, type TehsilRisk } from "./api";
import { countLevels, levelAt, rankTehsils } from "./hooks";
import { districtName, tehsilName, tehsilPlace } from "./places";
import { placeLabel } from "./site";

function tehsil(id: string, levels: Level[], probs: number[]): TehsilRisk {
  return {
    tehsil_id: id, tehsil: id.split("__")[1], district: id.split("__")[0], tehsil_ur: "کبل", district_ur: "سوات",
    max_level: levels[0], max_probability: probs[0],
    days: levels.map((level, i) => ({
      date: `2025-08-${14 + i}`, lead_days: i, level, probability: probs[i], glofas_flag: false,
      drivers: [], driver_codes: [],
    })),
  };
}

const rows = [
  tehsil("buner__daggar", ["low", "high", "low", "low"], [0.001, 0.009, 0.001, 0.001]),
  tehsil("swat__kabal", ["very_high", "very_high", "moderate", "moderate"], [0.03, 0.02, 0.004, 0.004]),
  tehsil("swat__kalam", ["low", "high", "low", "low"], [0.001, 0.012, 0.001, 0.001]),
];

describe("ranking and counts", () => {
  it("ranks by level, then probability, for the chosen day", () => {
    expect(rankTehsils(rows, 1).map((r) => r.tehsil_id)).toEqual(["swat__kabal", "swat__kalam", "buner__daggar"]);
    expect(rankTehsils(rows, 0)[0].tehsil_id).toBe("swat__kabal");
  });

  it("does not reorder the input", () => {
    const before = rows.map((r) => r.tehsil_id);
    rankTehsils(rows, 1);
    expect(rows.map((r) => r.tehsil_id)).toEqual(before);
  });

  it("counts tehsils per level", () => {
    expect(countLevels(rows, 1)).toEqual({ low: 0, moderate: 0, high: 2, very_high: 1 });
    expect(levelAt(rows[0], 3)?.level).toBe("low");
    expect(levelAt(rows[0], 9)).toBeUndefined();
  });
});

describe("places", () => {
  it("names tehsils in the chosen language", () => {
    expect(tehsilName(rows[1], "en")).toBe("kabal");
    expect(tehsilName(rows[1], "ur")).toBe("کبل");
    expect(districtName(rows[1], "ur")).toBe("سوات");
  });

  it("turns a tehsil into a place with its centroid", () => {
    const geo = { type: "FeatureCollection", features: [{ type: "Feature", geometry: null,
      properties: { tehsil_id: "swat__kabal", centroid_lat: 34.8, centroid_lon: 72.3 } }] } as unknown as GeoJSON.FeatureCollection;
    const p = tehsilPlace(rows[1], geo);
    expect(p).toMatchObject({ type: "tehsil", id: "swat__kabal", tehsil_id: "swat__kabal", lat: 34.8, lon: 72.3 });
  });

  it("labels villages with their tehsil, and uses Urdu labels in Urdu", () => {
    const village: Place = { type: "village", id: "v1", name: "Pir Baba", tehsil_id: "buner__gagra", tehsil: "Gagra", label_ur: "پیر بابا" };
    expect(placeLabel(village, "en")).toBe("Pir Baba, Gagra");
    expect(placeLabel(village, "ur")).toBe("پیر بابا");
  });
});

describe("LevelStrip", () => {
  it("renders one coloured block per day, highlighting the chosen day", () => {
    const html = renderToStaticMarkup(<LevelStrip days={rows[1].days} lang="en" focus={1} />);
    expect(html.match(/<b /g)).toHaveLength(4);
    expect(html).toContain(LEVEL_COLORS.very_high);
    expect(html).toContain("Tomorrow");
    expect(html.match(/class="d focus"/g)).toHaveLength(1);
  });
});
