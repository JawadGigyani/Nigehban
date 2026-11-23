"""Evidence the agent may use, each item with an id the answer must cite.

Ids:
- risk:<tehsil_id>:<date>      model risk level for that day (lead 0–3) and its reasons
- river:<point_id>:<date>      GloFAS river flag at or above the flag level
- exposure:<village_id>        village flood-exposure band (terrain)
- exposure:tehsil:<tehsil_id>  how many villages in the tehsil are on low ground
- facility:<facility_id>       nearest named shelters, higher ground, Rescue 1122, health
- doc:<slug>:p<page>#<n>       passage from official guidance (PDMA, NDMA, NIH)
- contact:helplines            Rescue 1122 and the PDMA helpline
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field

import pandas as pd

from backend.app.contracts import RiskLevel, TehsilRiskForecast
from backend.app.risk.service import describe_driver

LEVEL_WORDS = {RiskLevel.LOW: "LOW", RiskLevel.MODERATE: "MODERATE", RiskLevel.HIGH: "HIGH",
               RiskLevel.VERY_HIGH: "VERY HIGH"}


@dataclass(frozen=True)
class EvidenceItem:
    ref: str
    kind: str  # risk | river | exposure | facility | doc | contact
    text: str
    label: str = ""  # short human label for citations


@dataclass
class EvidenceBundle:
    items: list[EvidenceItem] = field(default_factory=list)
    # The model's level per valid date for the place asked about (never set by the LLM).
    levels: dict[dt.date, RiskLevel] = field(default_factory=dict)
    tehsil_id: str | None = None
    place_name: str | None = None

    @property
    def refs(self) -> set[str]:
        return {i.ref for i in self.items}

    def add(self, item: EvidenceItem) -> None:
        if item.ref not in self.refs:
            self.items.append(item)

    def render(self) -> str:
        if not self.items:
            return "(no evidence available)"
        return "\n".join(f"[{i.ref}] {i.text}" for i in self.items)


def _km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(a))


def tehsil_name(tehsil_id: str) -> str:
    district, tehsil = tehsil_id.split("__")
    return f"{tehsil.replace('_', ' ').title()} tehsil ({district.replace('_', ' ').title()} district)"


def risk_items(forecasts: list[TehsilRiskForecast], river_names: dict[str, str] | None = None) -> list[EvidenceItem]:
    out = []
    for f in sorted(forecasts, key=lambda x: x.valid_date):
        reasons = "; ".join(describe_driver(d) for d in f.drivers[:3]) or "no strong drivers"
        when = "today" if f.lead_days == 0 else f"{f.lead_days} day{'s' if f.lead_days > 1 else ''} ahead"
        text = (f"Flash-flood risk for {tehsil_name(f.tehsil_id)} on {f.valid_date:%d %b %Y} "
                f"(forecast issued {f.issued_at:%d %b %Y}, {when}): {LEVEL_WORDS[f.level]}. "
                f"Main reasons: {reasons}. Weather models: {', '.join(m.value.upper() for m in f.models_used)}.")
        if f.glofas_flag:
            text += " River flag: a river serving this tehsil is forecast at an unusually high flow."
        out.append(EvidenceItem(f"risk:{f.tehsil_id}:{f.valid_date}", "risk", text,
                                f"Nigehban risk model, {f.valid_date:%d %b}"))
    return out


def exposure_items(villages: pd.DataFrame, tehsil_id: str, village_id: str | None) -> list[EvidenceItem]:
    out = []
    part = villages[villages["tehsil_id"] == tehsil_id]
    if village_id is not None:
        row = part[part["village_id"] == village_id]
        if not row.empty:
            r = row.iloc[0]
            out.append(EvidenceItem(
                f"exposure:{village_id}", "exposure",
                f"{r['name']} village: {str(r['exposure_band']).upper()} flood exposure from terrain "
                f"(lowest ground within about 180 m is {r['hand_min_m']:.0f} m above the nearest stream; "
                f"that stream drains {r['upstream_area_km2']:,.0f} km²). Exposure bands are a guide, not a flood map.",
                "Nigehban terrain analysis"))
    if not part.empty:
        counts = part["exposure_band"].value_counts()
        high = part[part["exposure_band"] == "high"].nsmallest(6, "hand_min_m")["name"].tolist()
        out.append(EvidenceItem(
            f"exposure:tehsil:{tehsil_id}", "exposure",
            f"{tehsil_name(tehsil_id)}: {int(counts.get('high', 0))} of {len(part)} mapped villages have high "
            f"flood exposure (low ground beside a large river), {int(counts.get('medium', 0))} medium. "
            f"Examples of high-exposure villages: {', '.join(high) or 'none'}.",
            "Nigehban terrain analysis"))
    return out


def facility_items(facilities: pd.DataFrame, tehsil_id: str, lat: float, lon: float) -> list[EvidenceItem]:
    out = []
    near = facilities.copy()
    near["km"] = [_km(lat, lon, a, b) for a, b in zip(near["lat"], near["lon"])]
    picks = []
    shelters = near[near["kind"].isin(["shelter", "high_ground"]) & (near["exposure_band"] != "high")]
    shelters = shelters[shelters["tehsil_id"] == tehsil_id].sort_values(["shelter_priority", "km"])
    shelters = shelters[~shelters["name"].astype(str).str.strip().str.lower().duplicated()]  # mapped twice
    picks += list(shelters.nsmallest(3, "km").itertuples(index=False))
    picks += list(near[near["kind"] == "rescue_1122"].nsmallest(1, "km").itertuples(index=False))
    picks += list(near[near["kind"] == "health"].nsmallest(1, "km").itertuples(index=False))
    for r in picks:
        kind = {"shelter": "possible shelter", "high_ground": "suggested higher ground (no known building)",
                "rescue_1122": "Rescue 1122", "health": "health facility"}[r.kind]
        name = r.name if isinstance(r.name, str) and r.name.strip() else ("Rescue 1122" if r.kind == "rescue_1122" else "")
        if not name:
            continue
        out.append(EvidenceItem(
            f"facility:{r.facility_id}", "facility",
            f"{kind}: {name}, about {r.km:.1f} km away ({r.tehsil_id.split('__')[1].replace('_', ' ').title()}). "
            f"Location from {r.source.split(';')[0]}.", "OpenStreetMap / Nigehban"))
    return out


def doc_items(passages) -> list[EvidenceItem]:
    return [EvidenceItem(p.ref, "doc", f"{p.label}: \"{p.text[:700]}\"", p.label) for p in passages]


HELPLINES = EvidenceItem("contact:helplines", "contact",
                         "Emergency help: Rescue 1122 (dial 1122). PDMA helpline: 1700.",
                         "Rescue 1122; PDMA helpline")
