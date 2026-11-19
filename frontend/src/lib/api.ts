// Small typed client for the Nigehban backend.

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type Level = "low" | "moderate" | "high" | "very_high";
export type Lang = "ur" | "en" | "ur_roman";

export interface RiskDay {
  date: string;
  lead_days: number;
  level: Level;
  probability: number;
  glofas_flag: boolean;
  drivers: string[];
  driver_codes: string[];
}

export interface TehsilRisk {
  tehsil_id: string;
  tehsil: string;
  district: string;
  tehsil_ur: string | null;
  district_ur: string | null;
  max_level: Level;
  max_probability: number;
  days: RiskDay[];
}

export interface RiskResponse {
  issue_date: string;
  replay: boolean;
  generated_at: string;
  tehsils: TehsilRisk[];
}

export interface Facility {
  id: string;
  kind: string;
  subtype: string;
  name: string;
  lat: number;
  lon: number;
  km: number;
  exposure_band: string;
  source: string;
}

export interface TehsilDetail {
  tehsil_id: string;
  name_ur: string | null;
  centroid: [number, number];
  exposure: { high: number; medium: number; low: number; villages: number };
  high_villages: { id: string; name: string; lat: number; lon: number; hand_min_m: number }[];
  shelters: Facility[];
  rescue_1122: Facility[];
  health: Facility[];
  rescue_1122_control_room: { district: string; control_room: string; district_office: string; source: string } | null;
  rivers: { point_id: string; name: string; q2: number; q5: number; series: { date: string; discharge: number; return_period: number }[] }[];
  note: string;
}

export interface Place {
  type: "tehsil" | "village";
  id: string;
  name: string;
  tehsil_id: string;
  label_ur: string | null;
  tehsil?: string;
  lat?: number;
  lon?: number;
}

export interface GeoCheck {
  tehsil_id: string;
  in_danger_zone: boolean;
  reasons: string[];
  level_today_tomorrow: Level | null;
  river_flag: boolean;
  advice: "move_away" | "be_ready" | "stay_alert" | "normal";
  advice_text: Record<Lang, string>;
}

export interface SafeRoute {
  engine: string;
  destination: { id: string; kind: string; name: string; subtype: string; lat: number; lon: number };
  distance_m: number;
  duration_min: number;
  geometry: { type: "LineString"; coordinates: [number, number][] };
  low_ground_share: number | null;
  notes: string[];
}

export interface Advisory {
  title: string;
  date: string;
  area: string[];
  risk: { tehsil_id: string; tehsil: string; days: { date: string; level: Level; river_flag: boolean }[] }[];
  actions: { text: string; refs: string[] }[];
  public_message_en: string;
  public_message_ur: string;
  sources: string[];
  footer: string;
  checked: boolean;
  markdown: string;
}

export interface ChatResult {
  session_id: string;
  answer: string;
  actions: { text: string; refs: string[] }[];
  language: Lang;
  level: Level | null;
  place: string | null;
  citations: { ref: string; label: string; kind: string }[];
  checked: boolean;
  fallback: boolean;
}

export interface InboxAlert {
  id: string;
  tehsil_id: string;
  level: Level;
  valid_date: string;
  issued_at: string;
  lead_days: number;
  message: string;
  replay: boolean;
  audio_url: string | null;
  citations: { ref: string; label: string }[];
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers: { ...headers, ...(init.headers || {}) } });
  } catch {
    throw new ApiError(0, "Cannot reach the Nigehban server.");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

const asOfParam = (asOf?: string | null) => (asOf ? `?as_of=${encodeURIComponent(asOf)}` : "");

export const api = {
  tehsils: () => request<GeoJSON.FeatureCollection>("/geo/tehsils"),
  risk: (asOf?: string | null) => request<RiskResponse>(`/risk${asOfParam(asOf)}`),
  tehsil: (id: string, asOf?: string | null) => request<TehsilDetail>(`/tehsils/${id}${asOfParam(asOf)}`),
  search: (q: string) => request<Place[]>(`/places/search?q=${encodeURIComponent(q)}`),
  chat: (body: { message: string; session_id?: string; language?: Lang; tehsil_id?: string; as_of?: string | null }) =>
    request<ChatResult>("/chat", { method: "POST", body: JSON.stringify(body) }),
  subscribe: (body: { channel: string; address: string; language: Lang; tehsil_ids: string[]; village_ids: string[] }) =>
    request<{ id: string }>("/subscriptions", { method: "POST", body: JSON.stringify(body) }),
  unsubscribe: (id: string) => request<{ deleted: boolean }>(`/subscriptions/${id}`, { method: "DELETE" }),
  deleteMyData: (address: string) =>
    request<{ deleted_subscriptions: number }>("/me/delete", { method: "POST", body: JSON.stringify({ address }) }),
  inbox: (id: string) => request<{ language: Lang; alerts: InboxAlert[] }>(`/inbox/${id}`),
  login: (password: string) =>
    request<{ token: string; expires_at: number }>("/board/login", { method: "POST", body: JSON.stringify({ password }) }),
  alerts: (token: string, replay?: boolean) =>
    request<any[]>(`/alerts?limit=100${replay === undefined ? "" : `&replay=${replay}`}`, {}, token),
  geoCheck: (lat: number, lon: number, asOf?: string | null) =>
    request<GeoCheck>("/geo/check", { method: "POST", body: JSON.stringify({ lat, lon, as_of: asOf ?? null }) }),
  route: (lat: number, lon: number, mode: "walk" | "drive" = "walk") =>
    request<SafeRoute>("/route/shelter", { method: "POST", body: JSON.stringify({ lat, lon, mode }) }),
  advisory: (token: string, tehsilIds: string[], asOf?: string | null) =>
    request<Advisory>("/advisories/draft", { method: "POST", body: JSON.stringify({ tehsil_ids: tehsilIds, as_of: asOf ?? null }) }, token),
  config: () => request<{ voice: boolean; webpush_public_key: string | null; sms: boolean; whatsapp: boolean }>("/config"),
  tts: (text: string) => request<{ audio_url: string }>("/tts", { method: "POST", body: JSON.stringify({ text }) }),
  runCycle: (asOf: string | null) =>
    request<any>("/internal/run-cycle", { method: "POST", body: JSON.stringify({ as_of: asOf }) }),
};

export const LEVEL_ORDER: Level[] = ["low", "moderate", "high", "very_high"];
export const LEVEL_COLORS: Record<Level, string> = {
  low: "#6b9e78",
  moderate: "#e9b44c",
  high: "#e0662b",
  very_high: "#b3261e",
};
