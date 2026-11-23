"""M7 backtest: how the whole warning system would have done in past seasons.

Two settings, both scored with models that never saw the season being tested
(each season is predicted by a model trained on the other seasons):

A. Real forecasts, Jun–Sep 2024–2025: the ECMWF / GFS / ICON forecasts as they
   were issued 1, 2 and 3 days ahead (Open-Meteo archived runs), averaged.
B. Best case, Jun–Sep 2019–2025: ERA5 (the rain that actually fell). This is an
   upper bound: no forecast is that good.

Alert rules compared at each lead:
- rain threshold: wettest-cell rain at or above the level that gives the target
  false-alert rate on ERA5 (the baseline);
- model: level high or above (deployed thresholds);
- model or river: high or above, or the GloFAS river flag (2-, 5- or 10-year flow);
- river only: the GloFAS flag alone.
The river flag uses the GloFAS reanalysis (archived GloFAS forecasts are not
available), so its numbers are an upper bound too.

Scoring (same as M5): an event is caught if an alert covers the day before, the
day, or the day after; a false alert is a run of alert days with no event
within a day, per tehsil per season. Lead time: the longest lead at which the
event was caught.

    python -m pipelines.backtest.run
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd

from backend.app.config import get_settings
from backend.app.hydromet.client import OpenMeteoClient
from backend.app.hydromet.rivers import RiverMonitor
from backend.app.risk.features import FEATURES, build_matrix, load_static
from pipelines.hydromet.qa import _md
from pipelines.risk.train import (
    alert_scores,
    apply_platt,
    build_dataset,
    cross_validate,
    fit_platt,
    threshold_for,
)

ONE = dt.timedelta(days=1)
FORECAST_YEARS = (2024, 2025)


def river_daily(monitor: RiverMonitor, years) -> pd.DataFrame:
    """Daily GloFAS reanalysis per river point, Apr–Oct (reuses the M6 cache)."""

    rows = []
    for p in monitor.points:
        for year in years:
            item = monitor.client.flood([p.lat], [p.lon], dt.date(year, 4, 1), dt.date(year, 10, 31))[0]
            for day, value in zip(item["daily"]["time"], item["daily"]["river_discharge"], strict=True):
                if value is not None:
                    rows.append({"point_id": p.point_id, "date": dt.date.fromisoformat(day), "q": float(value)})
    return pd.DataFrame(rows)


def river_flag_set(monitor: RiverMonitor, daily: pd.DataFrame, return_period: int) -> set[tuple[str, dt.date]]:
    flags = set()
    for p in monitor.points:
        level = p.q[return_period]
        days = daily[(daily["point_id"] == p.point_id) & (daily["q"] >= level)]["date"]
        for d in days:
            for t in p.tehsils:
                flags.add((t, d))
    return flags


def caught_lead(events: pd.DataFrame, alerts_by_lead: dict[int, set]) -> list[int]:
    """Longest lead at which each event was caught (0 = not caught)."""

    out = []
    for t, d in zip(events["tehsil_id"], events["date"]):
        best = 0
        for lead, keys in alerts_by_lead.items():
            if any((t, d + k * ONE) in keys for k in (-1, 0, 1)):
                best = max(best, lead)
        out.append(best)
    return out


def main() -> int:
    settings = get_settings()
    data = settings.data_dir
    target = settings.alert_false_alarm_target_per_season
    meta = json.loads(Path("backend/app/risk/artifacts/v1/meta.json").read_text(encoding="utf-8"))
    kind = meta["model_kind"]
    high = meta["levels"]["high"]["probability"]

    frame, events = build_dataset(data)
    loso = cross_validate(frame, FEATURES, "year", kind)
    platt = fit_platt(loso.oof[frame["train"]], frame.loc[frame["train"], "y"].to_numpy())
    frame["p"] = apply_platt(loso.oof, *platt)
    rain_thr = threshold_for(frame, frame["precip_cell_max"].to_numpy(), events, target)["threshold"]

    monitor = RiverMonitor.from_data_dir(data, OpenMeteoClient(data / "cache" / "openmeteo"))
    river = river_daily(monitor, range(2019, 2026))
    flags = {rp: river_flag_set(monitor, river, rp) for rp in (2, 5, 10)}
    keys_all = list(zip(frame["tehsil_id"], frame["date"]))

    # ---- B. best case (ERA5), 2019–2025 ------------------------------------------------------
    best_rows = []
    rules_b = {
        "rain threshold": frame["precip_cell_max"].to_numpy() >= rain_thr,
        "model (high+)": frame["p"].to_numpy() >= high,
        **{f"model or river (>={rp}-yr flow)": (frame["p"].to_numpy() >= high)
           | np.array([k in flags[rp] for k in keys_all]) for rp in (2, 5, 10)},
        "river only (>=5-yr flow)": np.array([k in flags[5] for k in keys_all]),
    }
    for name, alert in rules_b.items():
        r = alert_scores(frame, alert.astype(float), 0.5, events)
        best_rows.append({"rule": name, "events": r["events"], "caught": r["hits"], "hit rate": r["hit_rate"],
                          "false alerts / tehsil-season": r["false_alerts_per_tehsil_season"]})
    best = pd.DataFrame(best_rows)

    # Per year and per district for the deployed rule (model or river at the configured level).
    rp_cfg = settings.river_flag_return_period
    deployed = (frame["p"].to_numpy() >= high) | np.array([k in flags[rp_cfg] for k in keys_all])
    by_year, by_district = [], []
    for year in sorted(frame["year"].unique()):
        m = (frame["year"] == year).to_numpy()
        r = alert_scores(frame[m], deployed[m].astype(float), 0.5, events)
        by_year.append({"season": year, "events": r["events"], "caught": r["hits"],
                        "false alerts / tehsil-season": r["false_alerts_per_tehsil_season"]})
    for district in sorted(frame["district"].unique()):
        m = (frame["district"] == district).to_numpy()
        r = alert_scores(frame[m], deployed[m].astype(float), 0.5, events)
        by_district.append({"district": district, "events": r["events"], "caught": r["hits"],
                            "false alerts / tehsil-season": r["false_alerts_per_tehsil_season"]})

    # ---- A. real forecasts, 2024–2025 ---------------------------------------------------------
    hydro = pd.read_parquet(data / "features" / "hydromet_daily.parquet")
    fc = hydro[(hydro["model"] != "era5") & pd.to_datetime(hydro["date"]).dt.month.between(6, 9)]
    static = load_static(data)
    fc_rows, lead_alerts = [], {name: {} for name in ("rain threshold", "model (high+)", "model or river")}
    merged_by = {}  # (year, lead) -> frame with p and rain
    for year in FORECAST_YEARS:
        base = frame[frame["year"] == year][["tehsil_id", "date", "year", "near_event", "district"]]
        part = build_matrix(fc[pd.to_datetime(fc["date"]).dt.year == year], static)
        part = part[part["tehsil_id"].isin(set(frame["tehsil_id"]))]
        part["p"] = apply_platt(loso.models[year].predict_proba(part[FEATURES])[:, 1], *platt)
        for lead in (1, 2, 3):
            lp = part[part["lead_days"] == lead]
            ens = lp.groupby(["tehsil_id", "date"]).agg(p=("p", "mean"), rain=("precip_cell_max", "mean")).reset_index()
            merged = base.merge(ens, on=["tehsil_id", "date"], how="left").fillna({"p": 0.0, "rain": 0.0})
            merged_by[(year, lead)] = merged
            keys = list(zip(merged["tehsil_id"], merged["date"]))
            rules = {
                "rain threshold": merged["rain"].to_numpy() >= rain_thr,
                "model (high+)": merged["p"].to_numpy() >= high,
                "model or river": (merged["p"].to_numpy() >= high) | np.array([k in flags[rp_cfg] for k in keys]),
            }
            for name, alert in rules.items():
                r = alert_scores(merged, alert.astype(float), 0.5, events)
                fc_rows.append({"season": year, "lead (days)": lead, "rule": name, "events": r["events"],
                                "caught": r["hits"], "false alerts / tehsil-season": r["false_alerts_per_tehsil_season"]})
                lead_alerts[name].setdefault(lead, set()).update(k for k, a in zip(keys, alert) if a)
    fcst = pd.DataFrame(fc_rows)
    summary = fcst.groupby(["rule", "lead (days)"]).agg(events=("events", "sum"), caught=("caught", "sum"),
                                                        fa=("false alerts / tehsil-season", "mean")).reset_index()
    summary["hit rate"] = summary["caught"] / summary["events"]
    summary = summary.rename(columns={"fa": "false alerts / tehsil-season"})

    # ---- A2. Same false-alert rate on forecasts, levels tuned across years ------------------------
    # Live use always runs on forecasts, which are smoother than ERA5, so levels tuned on ERA5
    # fire too rarely. Tune on forecasts: each season's threshold comes from the other season.
    eq_rows, tuned_alerts, forecast_levels = [], {"rain threshold": {}, "model": {}, "model or river": {}}, {}
    for lead in (1, 2, 3):
        for year in FORECAST_YEARS:
            other = [y for y in FORECAST_YEARS if y != year][0]
            train_f, test_f = merged_by[(other, lead)], merged_by[(year, lead)]
            keys = list(zip(test_f["tehsil_id"], test_f["date"]))
            river = np.array([k in flags[rp_cfg] for k in keys])
            t_model = threshold_for(train_f, train_f["p"].to_numpy(), events, target)["threshold"]
            t_rain = threshold_for(train_f, train_f["rain"].to_numpy(), events, target)["threshold"]
            rules = {"rain threshold": test_f["rain"].to_numpy() >= t_rain,
                     "model": test_f["p"].to_numpy() >= t_model,
                     "model or river": (test_f["p"].to_numpy() >= t_model) | river}
            for name, alert in rules.items():
                r = alert_scores(test_f, alert.astype(float), 0.5, events)
                eq_rows.append({"rule": name, "lead (days)": lead, "season": year, "events": r["events"],
                                "caught": r["hits"], "fa": r["false_alerts_per_tehsil_season"]})
                tuned_alerts[name].setdefault(lead, set()).update(k for k, a in zip(keys, alert) if a)
        both = pd.concat([merged_by[(y, lead)] for y in FORECAST_YEARS], ignore_index=True)
        forecast_levels[lead] = {
            "moderate": threshold_for(both, both["p"].to_numpy(), events, 8.0)["threshold"],
            "high": threshold_for(both, both["p"].to_numpy(), events, target)["threshold"],
            "very_high": threshold_for(both, both["p"].to_numpy(), events, 0.5)["threshold"]}
    eq = pd.DataFrame(eq_rows).groupby(["rule", "lead (days)"]).agg(
        events=("events", "sum"), caught=("caught", "sum"), fa=("fa", "mean")).reset_index()
    eq["hit rate"] = eq["caught"] / eq["events"]
    eq = eq.rename(columns={"fa": "false alerts / tehsil-season"})

    ev_fc = events[events["date"].map(lambda d: d.year in FORECAST_YEARS)]
    lead_table = []
    for name, alerts in lead_alerts.items():
        leads = caught_lead(ev_fc, alerts)
        lead_table.append({"rule": name, "events": len(leads), "caught at any lead": sum(1 for x in leads if x),
                           "caught 3 days ahead": sum(1 for x in leads if x >= 3),
                           "caught 2+ days ahead": sum(1 for x in leads if x >= 2),
                           "caught 1+ day ahead": sum(1 for x in leads if x >= 1)})
    leads_df = pd.DataFrame(lead_table)
    tuned_lead_table = []
    for name, alerts in tuned_alerts.items():
        leads = caught_lead(ev_fc, alerts)
        tuned_lead_table.append({"rule": name, "events": len(leads), "caught at any lead": sum(1 for x in leads if x),
                                 "caught 3 days ahead": sum(1 for x in leads if x >= 3),
                                 "caught 2+ days ahead": sum(1 for x in leads if x >= 2)})
    tuned_leads = pd.DataFrame(tuned_lead_table)

    metrics = {"best_case": best.to_dict("records"), "forecast": summary.to_dict("records"),
               "forecast_equal_false_alerts": eq.to_dict("records"), "forecast_levels": forecast_levels,
               "tuned_lead_times": tuned_leads.to_dict("records"),
               "lead_times": leads_df.to_dict("records"), "by_year": by_year, "by_district": by_district,
               "rain_threshold_mm": rain_thr, "high_threshold": high, "river_flag_return_period": rp_cfg}
    # Deployed levels: forecast-tuned per lead (live inputs are always forecasts).
    artifact = Path("backend/app/risk/artifacts/v1")
    (artifact / "forecast_levels.json").write_text(json.dumps({
        "note": "Probability thresholds per lead day, tuned on archived ECMWF/GFS/ICON forecasts "
                "(Jun-Sep 2024-2025) for 8 / target / 0.5 false alerts per tehsil-season. Lead 0 uses lead 1.",
        "target_false_alerts_per_tehsil_season": target,
        "levels": {str(k): {n: round(v, 6) for n, v in lv.items()} for k, lv in forecast_levels.items()},
    }, indent=2), encoding="utf-8")
    out_dir = Path("reports")
    (data / "features" / "backtest_metrics.json").write_text(json.dumps(metrics, indent=2, default=float),
                                                              encoding="utf-8")
    text = f"""# M7 backtest

Generated {dt.date.today()} by `python -m pipelines.backtest.run`. Every season is predicted by a model
trained without it. Model: {kind}; "high" at probability {high:.4f}; rain threshold
{rain_thr:.0f} mm in the wettest cell; river flag at the {rp_cfg}-year GloFAS flow
(`NIGEHBAN_RIVER_FLAG_RETURN_PERIOD`).

## A. With the forecasts as they were issued (Jun–Sep 2024–2025)

### Levels tuned on forecasts (each season tuned on the other), {target:g} false alerts per tehsil-season

{_md(eq)}

{_md(tuned_leads)}

### Levels tuned on ERA5 (as in M5): too few alerts on forecasts

{_md(summary)}

### How early were events caught?

{_md(leads_df)}

## B. Best case: if the forecast were perfect (ERA5, Jun–Sep 2019–2025)

{_md(best)}

### Deployed rule (model high+ or river flag) by season

{_md(pd.DataFrame(by_year))}

### By district

{_md(pd.DataFrame(by_district))}

## How to read this

- Hit rates are low in absolute terms, and that is the honest picture: many PDMA flood reports
  come from short local storms that 25 km weather data and global forecasts do not resolve.
- "Best case" shows the ceiling with today's inputs; the gap to "real forecasts" is the forecast error.
- The river flag uses the GloFAS reanalysis, so its contribution is also a best case.
- About {len(ev_fc)} events in 2024–2025: one or two events change a hit rate by several points.
- Scoring follows M5: ±1 day window; false alerts are runs of alert days with no event, per tehsil
  per season (122 days).
"""
    (out_dir / "backtest.md").write_text(text, encoding="utf-8")
    print(_md(eq))
    print(_md(tuned_leads))
    print(json.dumps(forecast_levels, indent=1))
    print(_md(leads_df))
    print(_md(best))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
