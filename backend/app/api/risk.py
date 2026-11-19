"""Risk, places and board routes used by the web app.

Public (citizen app and board):
- GET /geo/tehsils                 in-scope tehsil polygons (GeoJSON)
- GET /risk                        risk for every tehsil, lead 0–3 (as_of = replay)
- GET /tehsils/{tehsil_id}         exposure, nearest shelters / higher ground / Rescue 1122, rivers
- GET /places/search?q=            villages and tehsils for subscribing (English or Urdu)
Board (password login, English):
- POST /board/login                returns a signed token valid for 12 hours
- GET /alerts is protected with the same token (see api/alerts.py)
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import time
from functools import lru_cache

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from backend.app.config import get_settings

router = APIRouter(tags=["risk"])
PKT = dt.timezone(dt.timedelta(hours=5))
TOKEN_HOURS = 12


# ---- shared data ---------------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _context():
    from backend.app.agent.service import load_context
    from backend.app.risk.service import get_risk_service

    return load_context(get_settings().data_dir, get_risk_service())


@lru_cache(maxsize=1)
def _tehsil_geojson() -> dict:
    path = get_settings().data_dir / "reference" / "tehsils.geojson"
    data = json.loads(path.read_text(encoding="utf-8"))
    from backend.app.geo.urdu import district_ur, tehsil_ur

    features = []
    for f in data["features"]:
        p = f["properties"]
        if not p.get("in_scope"):
            continue
        p = {**p, "tehsil_ur": tehsil_ur(p["tehsil_id"]), "district_ur": district_ur(p["tehsil_id"])}
        features.append({**f, "properties": p})
    return {"type": "FeatureCollection", "features": features}


def _issue(as_of: dt.datetime | None) -> tuple[dt.date, bool]:
    now = dt.datetime.now(PKT)
    issue = (as_of.astimezone(PKT) if as_of else now).date()
    return issue, as_of is not None and issue < now.date()


# ---- public ----------------------------------------------------------------------------------

@router.get("/geo/tehsils")
def tehsils_geojson() -> dict:
    return _tehsil_geojson()


@router.get("/risk")
def risk_all(as_of: dt.datetime | None = None) -> dict:
    from backend.app.geo.urdu import district_ur, tehsil_ur
    from backend.app.risk.service import describe_driver

    ctx = _context()
    issue, replay = _issue(as_of)
    if replay and issue < dt.date(2024, 3, 1):
        raise HTTPException(422, "Replay is available from 1 March 2024 (archived forecasts).")
    try:
        forecasts = ctx.risk.forecast(issue, replay)
    except Exception as exc:  # weather service down
        raise HTTPException(503, "Weather data is unavailable right now.") from exc
    by_tehsil: dict[str, list] = {}
    for f in forecasts:
        if ctx.tehsils.get(f.tehsil_id, {}).get("in_scope"):
            by_tehsil.setdefault(f.tehsil_id, []).append(f)
    rows = []
    for tehsil_id, items in by_tehsil.items():
        items.sort(key=lambda f: f.lead_days)
        district, tehsil = tehsil_id.split("__")
        days = [{"date": str(f.valid_date), "lead_days": f.lead_days, "level": f.level.value,
                 "probability": f.probability, "glofas_flag": f.glofas_flag,
                 "drivers": [describe_driver(d) for d in f.drivers[:3]],
                 "driver_codes": [d.feature for d in f.drivers[:3]]} for f in items]
        top = max(items, key=lambda f: (f.level.rank, f.probability))
        rows.append({"tehsil_id": tehsil_id, "tehsil": tehsil.replace("_", " ").title(),
                     "district": district.replace("_", " ").title(), "tehsil_ur": tehsil_ur(tehsil_id),
                     "district_ur": district_ur(tehsil_id), "max_level": top.level.value,
                     "max_probability": top.probability, "days": days})
    rows.sort(key=lambda r: (-["low", "moderate", "high", "very_high"].index(r["max_level"]),
                             -r["max_probability"]))
    return {"issue_date": str(issue), "replay": replay, "generated_at": dt.datetime.now(PKT).isoformat(),
            "tehsils": rows}


@router.get("/tehsils/{tehsil_id}")
def tehsil_detail(tehsil_id: str, as_of: dt.datetime | None = None) -> dict:
    from backend.app.agent.evidence import _km
    from backend.app.geo.urdu import place_ur

    ctx = _context()
    if tehsil_id not in ctx.tehsils:
        raise HTTPException(404, "Unknown tehsil.")
    t = ctx.tehsils[tehsil_id]
    villages = ctx.villages[ctx.villages["tehsil_id"] == tehsil_id]
    counts = villages["exposure_band"].value_counts().to_dict()
    high = villages[villages["exposure_band"] == "high"].nsmallest(15, "hand_min_m")
    fac = ctx.facilities.copy()
    fac["km"] = [_km(t["lat"], t["lon"], a, b) for a, b in zip(fac["lat"], fac["lon"], strict=True)]
    local = fac[fac["tehsil_id"] == tehsil_id]

    def rows(frame, n):
        return [{"id": r.facility_id, "kind": r.kind, "subtype": r.subtype, "name": r.name if isinstance(r.name, str) else "",
                 "lat": r.lat, "lon": r.lon, "km": round(r.km, 1), "exposure_band": r.exposure_band if isinstance(r.exposure_band, str) else "",
                 "verified": False, "source": r.source} for r in frame.nsmallest(n, "km").itertuples(index=False)]

    shelters = local[local["kind"].isin(["shelter", "high_ground"]) & (local["exposure_band"] != "high")]
    rivers = []
    if ctx.risk is not None and ctx.risk.rivers is not None:
        issue, replay = _issue(as_of)
        serving = [p for p in ctx.risk.rivers.points if tehsil_id in p.tehsils]
        if serving:
            try:
                readings = ctx.risk.river_readings(issue, replay)
            except Exception:
                readings = []
            for p in serving:
                series = [{"date": str(r.date), "discharge": round(r.discharge, 1), "return_period": r.return_period}
                          for r in readings if r.point_id == p.point_id]
                rivers.append({"point_id": p.point_id, "name": p.name, "q2": p.q[2], "q5": p.q[5], "series": series})
    return {
        "tehsil_id": tehsil_id, "name_ur": place_ur(tehsil_id), "centroid": [t["lon"], t["lat"]],
        "exposure": {"high": int(counts.get("high", 0)), "medium": int(counts.get("medium", 0)),
                     "low": int(counts.get("low", 0)), "villages": len(villages)},
        "high_villages": [{"id": r.village_id, "name": r.name, "lat": r.lat, "lon": r.lon,
                           "hand_min_m": r.hand_min_m} for r in high.itertuples(index=False)],
        "shelters": rows(shelters.sort_values("shelter_priority"), 6),
        "rescue_1122": rows(fac[fac["kind"] == "rescue_1122"], 2),
        "health": rows(fac[fac["kind"] == "health"], 2),
        "rivers": rivers,
        "note": "Shelter, Rescue 1122 and health locations are from OpenStreetMap and news reports and are unverified.",
    }


@router.get("/places/search")
def places_search(q: str = Query(min_length=2, max_length=60), limit: int = 12) -> list[dict]:
    from backend.app.geo.urdu import place_ur

    ctx = _context()
    key = q.strip().lower()
    out, seen = [], set()
    for name, tehsil_id in ctx._tehsil_names.items():
        if key in name:
            t = ctx.tehsils[tehsil_id]
            out.append({"type": "tehsil", "id": tehsil_id, "name": name.title(), "tehsil_id": tehsil_id,
                        "label_ur": place_ur(tehsil_id), "lat": t["lat"], "lon": t["lon"]})
            seen.add(tehsil_id)
    g = ctx.gazetteer
    names = g["name"].str.lower()
    hits = g[names.str.startswith(key) | g["name_ur"].fillna("").str.startswith(q.strip())]
    for r in hits.head(limit).itertuples(index=False):
        out.append({"type": "village", "id": r.place_id, "name": r.name, "tehsil_id": r.tehsil_id,
                    "label_ur": r.name_ur if isinstance(r.name_ur, str) else None,
                    "tehsil": r.tehsil_id.split("__")[1].replace("_", " ").title(),
                    "lat": float(r.lat), "lon": float(r.lon)})
    return out[:limit]


# ---- board login -----------------------------------------------------------------------------

def _secret() -> bytes:
    settings = get_settings()
    if settings.board_password is None:
        raise HTTPException(503, "NIGEHBAN_BOARD_PASSWORD is not set.")
    seed = settings.board_password.get_secret_value()
    extra = settings.contact_hash_key.get_secret_value() if settings.contact_hash_key else ""
    return hashlib.sha256(f"board:{seed}:{extra}".encode()).digest()


def make_token(expires: int) -> str:
    sig = hmac.new(_secret(), str(expires).encode(), hashlib.sha256).digest()
    return f"{expires}.{base64.urlsafe_b64encode(sig).decode().rstrip('=')}"


def check_board_token(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Board login required.")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        expires = int(token.split(".", 1)[0])
    except ValueError as exc:
        raise HTTPException(401, "Invalid token.") from exc
    if expires < time.time() or not hmac.compare_digest(token, make_token(expires)):
        raise HTTPException(401, "Session expired. Please log in again.")


class LoginRequest(BaseModel):
    password: str


@router.post("/board/login")
def board_login(request: LoginRequest) -> dict:
    settings = get_settings()
    _secret()
    if not hmac.compare_digest(request.password.encode(), settings.board_password.get_secret_value().encode()):
        time.sleep(0.5)  # slow down guessing
        raise HTTPException(401, "Wrong password.")
    expires = int(time.time()) + TOKEN_HOURS * 3600
    return {"token": make_token(expires), "expires_at": expires}
