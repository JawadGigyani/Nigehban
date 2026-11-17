"""Write one JSON fixture per contract, so later modules can start on mocks.

The values are made up and only illustrate the shape; they are not real data.
Run: python -m tests.fixtures.contracts.build_fixtures
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from pydantic import BaseModel

from backend.app.contracts import (
    Alert,
    ChannelName,
    DeliveryResult,
    EventType,
    ExposureBand,
    FloodEvent,
    GeocodeLevel,
    HydrometDaily,
    HydrometModel,
    Language,
    RiskDriver,
    RiskLevel,
    RiverPointThresholds,
    RiverThresholds,
    Subscription,
    SubscriptionCreate,
    TehsilRegion,
    TehsilRiskForecast,
    TehsilStatic,
    VillageExposure,
)

FIXTURE_DIR = Path(__file__).parent
ISSUED = dt.datetime(2025, 8, 14, 6, 0, tzinfo=dt.UTC)

FIXTURES: dict[str, list[BaseModel]] = {
    "tehsil_region": [
        TehsilRegion(
            tehsil_id="buner__daggar", district="Buner", tehsil="Daggar",
            centroid_lat=34.50, centroid_lon=72.48,
        ),
        TehsilRegion(
            tehsil_id="bajaur__khar", district="Bajaur", tehsil="Khar",
            centroid_lat=34.73, centroid_lon=71.52, is_ardc=True,
        ),
    ],
    "flood_event": [
        FloodEvent(
            event_id="evt_0001", date=dt.date(2025, 8, 15), report_date=dt.date(2025, 8, 15),
            district="Buner", tehsil="Daggar", tehsil_id="buner__daggar", village="Example Village",
            lat=34.51, lon=72.47, geocode_level=GeocodeLevel.VILLAGE,
            event_type=EventType.FLASH_FLOOD, deaths=3, houses_damaged=5,
            source_dsrid=1, extract_confidence=0.9,
        ),
        FloodEvent(
            event_id="evt_0002", date=dt.date(2025, 8, 15), report_date=dt.date(2025, 8, 15),
            district="Shangla", geocode_level=GeocodeLevel.DISTRICT,
            event_type=EventType.ROOF_COLLAPSE, deaths=1, source_dsrid=1, extract_confidence=0.7,
        ),
    ],
    "hydromet_daily": [
        HydrometDaily(
            tehsil_id="buner__daggar", date=dt.date(2025, 8, 15), model=HydrometModel.ERA5,
            lead_days=0, precip_sum=44.4, precip_max_1h=9.1, precip_3d=77.2,
            precip_7d_antecedent=40.0, soil_moisture_0_7=0.31, soil_moisture_7_28=0.29,
            t2m_max=31.5, t2m_anomaly=0.8,
        ),
        HydrometDaily(
            tehsil_id="buner__daggar", date=dt.date(2025, 8, 15), model=HydrometModel.ECMWF,
            lead_days=1, precip_sum=34.2,
        ),
    ],
    "tehsil_static": [
        TehsilStatic(
            tehsil_id="buner__daggar", mean_slope=18.2, p90_slope=34.0, catchment_area_km2=410.0,
            drainage_density=1.4, share_low_hand=0.12, population=150000, population_low_hand=21000,
        ),
    ],
    "village_exposure": [
        VillageExposure(village_id="vil_0001", hand_m=2.1, exposure_band=ExposureBand.HIGH,
                        dist_to_stream_m=85),
        VillageExposure(village_id="vil_0002", hand_m=14.0, exposure_band=ExposureBand.LOW,
                        dist_to_stream_m=900),
    ],
    "river_thresholds": [
        RiverThresholds(
            method="Gumbel fit on annual maxima",
            points=(
                RiverPointThresholds(
                    point_id="swat_chakdara", name="Swat at Chakdara", lat=34.625, lon=71.975,
                    q2=900, q5=1400, q10=1800, q20=2200, years_used=29,
                ),
            ),
        ),
    ],
    "tehsil_risk_forecast": [
        TehsilRiskForecast(
            tehsil_id="buner__daggar", issued_at=ISSUED, valid_date=dt.date(2025, 8, 15),
            lead_days=1, probability=0.42, level=RiskLevel.HIGH,
            drivers=(
                RiskDriver(feature="precip_sum", value=34.2, contribution=1.1),
                RiskDriver(feature="soil_moisture_0_7", value=0.31, contribution=0.4),
            ),
            models_used=(HydrometModel.ECMWF, HydrometModel.GFS, HydrometModel.ICON),
        ),
    ],
    "subscription_create": [
        SubscriptionCreate(channel=ChannelName.WEB_INBOX, address="device-token-example",
                           language=Language.UR, tehsil_ids=("buner__daggar",)),
    ],
    "subscription": [
        Subscription(id="sub_0001", channel=ChannelName.WEB_INBOX, language=Language.UR,
                     tehsil_ids=("buner__daggar",), village_ids=(), created_at=ISSUED, active=True),
    ],
    "alert": [
        Alert(
            id="alr_0001", tehsil_id="buner__daggar", level=RiskLevel.HIGH,
            valid_date=dt.date(2025, 8, 15), issued_at=ISSUED,
            reason_codes=("heavy_rain_forecast", "wet_ground"),
            message_ur="(نمونہ) ڈگر میں کل سیلاب کا خطرہ زیادہ ہے۔ پی ڈی ایم اے اور ضلعی انتظامیہ کی ہدایات پر عمل کریں۔",
            message_en="(Sample) High flash-flood risk in Daggar tomorrow. Follow PDMA and district administration instructions.",
            citations=("risk:FlashFloodRiskModel",),
        ),
    ],
    "delivery_result": [
        DeliveryResult(ok=True, channel=ChannelName.CONSOLE),
    ],
}


def main() -> None:
    for name, items in FIXTURES.items():
        payload = [item.model_dump(mode="json") for item in items]
        (FIXTURE_DIR / f"{name}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(f"Wrote {len(FIXTURES)} fixtures to {FIXTURE_DIR}")


if __name__ == "__main__":
    main()
