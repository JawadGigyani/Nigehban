"""Chat agent: place lookup, evidence gathering, sessions, and the compiled graph."""

from __future__ import annotations

import datetime as dt
import logging
import uuid
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

from backend.app.agent.evidence import (
    HELPLINES,
    EvidenceBundle,
    doc_items,
    exposure_items,
    facility_items,
    risk_items,
    tehsil_name,
)
from backend.app.agent.graph import Understanding, build_graph

log = logging.getLogger(__name__)
PKT = dt.timezone(dt.timedelta(hours=5))
POPULATED = {"city", "town", "village", "hamlet", "suburb", "ppl", "ppla", "ppla2", "ppla3", "pplc", "pplx"}


class AgentContext:
    def __init__(self, risk_service, knowledge, gazetteer: pd.DataFrame, villages: pd.DataFrame,
                 facilities: pd.DataFrame, tehsils: dict[str, dict]) -> None:
        self.risk = risk_service
        self.kb = knowledge
        self.villages = villages
        self.facilities = facilities
        self.tehsils = tehsils  # tehsil_id -> {lat, lon, in_scope}
        g = gazetteer[gazetteer["tehsil_id"].isin([t for t, v in tehsils.items() if v["in_scope"]])].copy()
        g["rank"] = g["feature"].map({"city": 0, "town": 1}).fillna(2)
        g = g.sort_values(["rank", "population"], ascending=[True, False], na_position="last")
        self.gazetteer = g
        self._names: dict[str, int] = {}
        for idx, r in g.iterrows():
            for name in [r["name"], *str(r["alt_names"] or "").split("|"), r["name_ur"]]:
                if isinstance(name, str) and name.strip():
                    self._names.setdefault(name.strip().lower(), idx)
        self._tehsil_names = {tid.split("__")[1].replace("_", " "): tid for tid, v in tehsils.items() if v["in_scope"]}

    # ---- place lookup --------------------------------------------------------------------------

    def locate(self, place: str, tehsil_id: str | None, lat: float | None, lon: float | None) -> dict | None:
        place = (place or "").strip()
        if place:
            found = self._find_place(place)
            if found:
                return found
        if lat is not None and lon is not None and self.risk is not None and self.risk.locator is not None:
            region = self.risk.locator.locate(lat, lon)
            if region:
                return {"tehsil_id": region.tehsil_id, "name": tehsil_name(region.tehsil_id),
                        "lat": lat, "lon": lon, "village_id": None}
        if tehsil_id and tehsil_id in self.tehsils:
            t = self.tehsils[tehsil_id]
            return {"tehsil_id": tehsil_id, "name": tehsil_name(tehsil_id), "lat": t["lat"], "lon": t["lon"],
                    "village_id": None}
        return None

    def _find_place(self, place: str) -> dict | None:
        key = place.lower()
        tehsil = self._tehsil_names.get(key)
        idx = self._names.get(key)
        if idx is None and tehsil is None:
            # Plain ratio: WRatio scores short partial matches too high ("pir baba" -> "bab").
            match = process.extractOne(key, list(self._names), scorer=fuzz.ratio, score_cutoff=88)
            if match:
                idx = self._names[match[0]]
            else:
                tm = process.extractOne(key, list(self._tehsil_names), scorer=fuzz.ratio, score_cutoff=88)
                tehsil = self._tehsil_names[tm[0]] if tm else None
        if idx is not None:
            r = self.gazetteer.loc[idx]
            return {"tehsil_id": r["tehsil_id"], "name": f"{r['name']} ({tehsil_name(r['tehsil_id'])})",
                    "lat": float(r["lat"]), "lon": float(r["lon"]), "village_id": r["place_id"]}
        if tehsil is not None:
            t = self.tehsils[tehsil]
            return {"tehsil_id": tehsil, "name": tehsil_name(tehsil), "lat": t["lat"], "lon": t["lon"],
                    "village_id": None}
        return None

    # ---- evidence --------------------------------------------------------------------------

    @staticmethod
    def issue_date(as_of: dt.datetime | None) -> dt.date:
        return (as_of.astimezone(PKT) if as_of else dt.datetime.now(PKT)).date()

    def target_day(self, day: str, as_of: dt.datetime | None) -> dt.date | None:
        offset = {"today": 0, "tomorrow": 1, "day_after": 2}.get(day)
        return None if offset is None else self.issue_date(as_of) + dt.timedelta(days=offset)

    def add_evidence(self, bundle: EvidenceBundle, located: dict, u: Understanding,
                     as_of: dt.datetime | None) -> None:
        tehsil_id = located.get("tehsil_id")
        if tehsil_id and self.risk is not None:
            issue = self.issue_date(as_of)
            replay = as_of is not None and issue < dt.datetime.now(PKT).date()
            try:
                forecasts = [f for f in self.risk.forecast(issue, replay) if f.tehsil_id == tehsil_id]
            except Exception as exc:  # weather service down: answer without risk, never guess it
                log.warning("risk unavailable: %s", exc)
                forecasts = []
            for item in risk_items(forecasts):
                bundle.add(item)
            bundle.levels = {f.valid_date: f.level for f in forecasts}
        if tehsil_id:
            for item in exposure_items(self.villages, tehsil_id, located.get("village_id")):
                bundle.add(item)
            if u.intent in ("shelter_or_help", "safety_advice", "risk"):
                for item in facility_items(self.facilities, tehsil_id, located["lat"], located["lon"]):
                    bundle.add(item)
        if self.kb is not None and u.intent != "small_talk":
            k = 2 if u.intent == "risk" else 4
            for item in doc_items(self.kb.search(u.search_query or "flash flood safety", k=k)):
                bundle.add(item)
        bundle.add(HELPLINES)


class ChatAgent:
    """Holds the compiled graph and short conversation memory per session."""

    def __init__(self, llm, context: AgentContext, max_sessions: int = 500) -> None:
        self.graph = build_graph(llm, context)
        self.sessions: OrderedDict[str, list[tuple[str, str]]] = OrderedDict()
        self.max_sessions = max_sessions

    def ask(self, message: str, session_id: str | None = None, *, language: str | None = None,
            tehsil_id: str | None = None, lat: float | None = None, lon: float | None = None,
            as_of: dt.datetime | None = None) -> dict:
        session_id = session_id or uuid.uuid4().hex
        history = self.sessions.get(session_id, [])
        state = self.graph.invoke({"message": message, "history": history, "language": language,
                                   "tehsil_id": tehsil_id, "lat": lat, "lon": lon, "as_of": as_of})
        result = dict(state["result"])
        history = [*history, ("user", message), ("assistant", result["answer"])][-12:]
        self.sessions[session_id] = history
        self.sessions.move_to_end(session_id)
        while len(self.sessions) > self.max_sessions:
            self.sessions.popitem(last=False)
        result["session_id"] = session_id
        return result


def load_context(data_dir: Path, risk_service=None) -> AgentContext:
    import json

    from backend.app.knowledge import KnowledgeBase

    ref = data_dir / "reference"
    features = json.loads((ref / "tehsils.geojson").read_text(encoding="utf-8"))["features"]
    tehsils = {f["properties"]["tehsil_id"]: {"lat": f["properties"]["centroid_lat"],
                                              "lon": f["properties"]["centroid_lon"],
                                              "in_scope": f["properties"]["in_scope"]} for f in features}
    gazetteer = pd.read_csv(ref / "gazetteer.csv")
    manual = ref / "manual_places.csv"
    if manual.is_file():  # well-known places missing from OSM and GeoNames
        gazetteer = pd.concat([pd.read_csv(manual), gazetteer], ignore_index=True)
    gazetteer = gazetteer[gazetteer["feature"].isin(POPULATED)]
    return AgentContext(risk_service, KnowledgeBase.load(), gazetteer, pd.read_csv(ref / "village_exposure.csv"),
                        pd.read_csv(ref / "facilities.csv"), tehsils)


@lru_cache(maxsize=1)
def get_agent() -> ChatAgent:
    from backend.app.config import get_settings
    from backend.app.llm import LLMService
    from backend.app.risk.service import get_risk_service

    settings = get_settings()
    return ChatAgent(LLMService.from_settings(settings), load_context(settings.data_dir, get_risk_service()))
