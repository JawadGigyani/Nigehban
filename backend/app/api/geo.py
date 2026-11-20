"""Point check, route to safety, and advisory drafts.

- POST /geo/check          danger zone at a point + model level today/tomorrow -> advice
- POST /route/shelter      route to the nearest safer place (OpenRouteService or OSM roads)
- POST /advisories/draft   draft advisory for selected tehsils (board login)
- GET  /rain/observed      satellite rain already fallen (NASA IMERG), per tehsil + wet cells
"""

from __future__ import annotations

import datetime as dt
from functools import lru_cache

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from backend.app.config import get_settings

router = APIRouter(tags=["geo"])
PKT = dt.timezone(dt.timedelta(hours=5))
ADVICE_TEXT = {
    "move_away": {"en": "Move away from the riverbank to higher ground now.",
                  "ur": "ابھی دریا کے کنارے سے ہٹ کر اونچی جگہ پر چلے جائیں۔",
                  "ur_roman": "Abhi darya ke kinare se hat kar oonchi jagah par chale jayein."},
    "be_ready": {"en": "You are on low ground by a river. Be ready to move if rain gets heavy.",
                 "ur": "آپ دریا کے قریب نشیبی جگہ پر ہیں۔ بارش تیز ہو تو فوراً ہٹنے کے لیے تیار رہیں۔",
                 "ur_roman": "Aap darya ke qareeb nasheebi jagah par hain. Barish tez ho to foran hatne ke liye tayyar rahein."},
    "stay_alert": {"en": "You are on low ground by a river. The risk is low now, but never camp or park by the water.",
                   "ur": "آپ دریا کے قریب نشیبی جگہ پر ہیں۔ ابھی خطرہ کم ہے، مگر پانی کے کنارے نہ ٹھہریں۔",
                   "ur_roman": "Aap darya ke qareeb nasheebi jagah par hain. Abhi khatra kam hai, magar pani ke kinare na thehrein."},
    "normal": {"en": "This spot is not on low ground beside a large river.",
               "ur": "یہ جگہ کسی بڑے دریا کے کنارے نشیبی زمین پر نہیں۔",
               "ur_roman": "Yeh jagah kisi bare darya ke kinare nasheebi zameen par nahi."},
}


@lru_cache(maxsize=1)
def _checker():
    from backend.app.api.risk import _context
    from backend.app.geo.danger import DangerChecker

    ctx = _context()
    locator = ctx.risk.locator if ctx.risk is not None else None
    if locator is None:
        from backend.app.geo.locator import TehsilLocator

        locator = TehsilLocator.from_geojson(get_settings().data_dir / "reference" / "tehsils.geojson")
    return DangerChecker(get_settings().data_dir, locator)


@lru_cache(maxsize=1)
def _router():
    from backend.app.api.risk import _context
    from backend.app.geo.routing import LowGround, RoadTiles, SafeRouter

    data = get_settings().data_dir
    terrain = data / "interim" / "terrain"
    key = get_settings().ors_api_key
    return SafeRouter(RoadTiles(data / "cache" / "osm_roads"),
                      LowGround([terrain / "swat30" / "hand.tif", terrain / "hand.tif"]),
                      _context().facilities, key.get_secret_value() if key else None)


class PointRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    as_of: dt.datetime | None = None


def _levels(tehsil_id: str, as_of: dt.datetime | None) -> dict[int, dict]:
    from backend.app.api.risk import _context, _issue

    ctx = _context()
    issue, replay = _issue(as_of)
    try:
        forecasts = [f for f in ctx.risk.forecast(issue, replay) if f.tehsil_id == tehsil_id]
    except Exception:
        return {}
    return {f.lead_days: {"date": str(f.valid_date), "level": f.level.value, "river_flag": f.glofas_flag}
            for f in forecasts}


@router.post("/geo/check")
def geo_check(request: PointRequest) -> dict:
    from backend.app.geo.danger import advice

    result = _checker().check(request.lat, request.lon)
    if result["tehsil_id"] is None:
        raise HTTPException(422, "This point is outside the area Nigehban covers.")
    levels = _levels(result["tehsil_id"], request.as_of)
    order = ["low", "moderate", "high", "very_high"]
    near = [levels[k]["level"] for k in (0, 1) if k in levels]
    level = max(near, key=order.index) if near else None
    river = any(levels[k]["river_flag"] for k in (0, 1) if k in levels)
    if river and level in (None, "low"):
        level = "moderate"  # the river flag alone means: be ready (it never lowers a level)
    code = advice(result["in_danger_zone"], level)
    return {**result, "level_today_tomorrow": level, "river_flag": river, "levels": levels,
            "advice": code, "advice_text": ADVICE_TEXT[code],
            "note": "Terrain from a 30 m (Swat) or 90 m elevation model; check the ground around you."}


class RouteRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    mode: str = Field(default="walk", pattern="^(walk|drive)$")


@router.post("/route/shelter")
def route_shelter(request: RouteRequest) -> dict:
    try:
        route = _router().route(request.lat, request.lon, request.mode)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(503, str(exc)) from exc
    if route is None:
        raise HTTPException(404, "No mapped shelter or higher ground within 12 km.")
    return route.as_dict()


class AdvisoryRequest(BaseModel):
    tehsil_ids: list[str] = Field(min_length=1, max_length=12)
    as_of: dt.datetime | None = None


def _board(authorization: str | None = Header(default=None)) -> None:
    from backend.app.api.risk import check_board_token

    check_board_token(authorization)


@router.post("/advisories/draft", dependencies=[Depends(_board)])
def advisory_draft(request: AdvisoryRequest) -> dict:
    from backend.app.alerts.advisory import compose_advisory
    from backend.app.api.risk import _context, _issue
    from backend.app.llm import LLMService

    ctx = _context()
    unknown = [t for t in request.tehsil_ids if t not in ctx.tehsils]
    if unknown:
        raise HTTPException(422, f"Unknown tehsils: {unknown}")
    issue, replay = _issue(request.as_of)
    forecasts = ctx.risk.forecast(issue, replay)
    by_tehsil = {t: [f for f in forecasts if f.tehsil_id == t] for t in request.tehsil_ids}
    return compose_advisory(_llm(), ctx, by_tehsil, issue)


@lru_cache(maxsize=1)
def _llm():
    from backend.app.llm import LLMService

    return LLMService.from_settings(get_settings())


@lru_cache(maxsize=1)
def _nowcast():
    from backend.app.hydromet.imerg import ImergClient, tehsil_weights
    from backend.app.hydromet.nowcast import RainNowcast

    settings = get_settings()
    return RainNowcast(ImergClient.from_settings(settings),
                       tehsil_weights(settings.data_dir / "reference" / "tehsils.geojson"))


@router.get("/rain/observed")
def rain_observed(as_of: dt.datetime | None = None) -> dict:
    """Rain that has already fallen (satellite). Not a forecast and not used by the risk model."""

    obs = _nowcast().observed(as_of)
    return {
        "date": str(obs.date) if obs.date else None,
        "run": obs.run,
        "available": obs.date is not None,
        "note": obs.note,
        "cell_size_deg": 0.1,
        "tehsils": [{"tehsil_id": t, "mean_mm": m, "max_mm": x} for t, (m, x) in sorted(obs.tehsils.items())],
        "cells": [{"lon": lon, "lat": lat, "mm": mm} for lon, lat, mm in obs.cells],
    }
