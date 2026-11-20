import type { Lang, Place, TehsilRisk } from "./api";

export function tehsilPlace(r: TehsilRisk, geo: GeoJSON.FeatureCollection | null): Place {
  const f = geo?.features.find((x) => x.properties?.tehsil_id === r.tehsil_id);
  return { type: "tehsil", id: r.tehsil_id, name: r.tehsil, tehsil_id: r.tehsil_id, label_ur: r.tehsil_ur,
    lat: f?.properties?.centroid_lat, lon: f?.properties?.centroid_lon };
}
export const tehsilName = (r: TehsilRisk, lang: Lang) => (lang === "ur" && r.tehsil_ur ? r.tehsil_ur : r.tehsil);
export const districtName = (r: TehsilRisk, lang: Lang) => (lang === "ur" && r.district_ur ? r.district_ur : r.district);
