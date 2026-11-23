"""Train and validate the flash-flood risk model (M5).

Rows: (tehsil, date) for in-scope tehsils, Jun–Sep 2019–2025, ERA5 features.

Labels (from M1 positives):
- 1 on the day of a tehsil-level event.
- Left out of training: the day before and after a tehsil-level event (report
  dates can be a day off), and every tehsil of a district on days when PDMA
  only named the district (we do not know which tehsil flooded).
- 0 otherwise.

Validation: leave-one-season-out (7 folds) and leave-one-district-out.
Alerts are scored the way they will be used:
- hit: a tehsil-level event with an alert on the day before, the day, or the day after;
- false alert: a run of consecutive alert days in a tehsil with no event
  (tehsil-level, or district-level in its district) within a day; counted per
  tehsil per season.
Every method is compared at the same false-alert rate.

Baselines: a single rain threshold (best of day / wettest cell / 3-day rain) and
an ERA5-only rain model (no terrain features).

Outputs: backend/app/risk/artifacts/v1/{model.txt, meta.json, metrics.json},
data/features/risk_oof.parquet, reports/risk_model.md.

    python -m pipelines.risk.train
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from backend.app.config import get_settings
from backend.app.config.region import slugify
from backend.app.risk.features import ALL_FEATURES, FEATURES, MONOTONE, RAIN_ONLY_FEATURES, build_matrix, load_static
from pipelines.risk.models import KINDS
from pipelines.risk.models import fit as fit_model

YEARS = list(range(2019, 2026))
ARTIFACT_DIR = Path("backend/app/risk/artifacts/v1")
LEVEL_FA_TARGETS = {"moderate": 8.0, "very_high": 0.5}  # "high" uses the configured target


# ---- dataset -------------------------------------------------------------------------------

def build_dataset(data: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    tehsils = json.loads((data / "reference" / "tehsils.geojson").read_text(encoding="utf-8"))["features"]
    in_scope = {f["properties"]["tehsil_id"] for f in tehsils if f["properties"]["in_scope"]}
    hydro = pd.read_parquet(data / "features" / "hydromet_daily.parquet")
    era5 = hydro[(hydro["model"] == "era5") & hydro["tehsil_id"].isin(in_scope)].copy()
    era5 = era5[pd.to_datetime(era5["date"]).dt.month.between(6, 9)
                & pd.to_datetime(era5["date"]).dt.year.isin(YEARS)]
    frame = build_matrix(era5, load_static(data))
    frame["district"] = frame["tehsil_id"].str.split("__").str[0]
    frame["year"] = pd.to_datetime(frame["date"]).dt.year

    events = pd.read_parquet(data / "events" / "flood_events.parquet")
    events = events[events["is_positive"]].copy()
    events["district_slug"] = events["district"].map(slugify)
    tehsil_events = events[events["tehsil_id"].isin(in_scope)][["tehsil_id", "date"]].drop_duplicates()
    district_events = events[events["tehsil_id"].isna()][["district_slug", "date"]].drop_duplicates()

    one = dt.timedelta(days=1)
    t_days = set(zip(tehsil_events["tehsil_id"], tehsil_events["date"]))
    t_near = {(t, d + k * one) for t, d in t_days for k in (-1, 0, 1)}
    d_near = {(s, d + k * one) for s, d in zip(district_events["district_slug"], district_events["date"])
              for k in (-1, 0, 1)}
    keys_t = list(zip(frame["tehsil_id"], frame["date"]))
    keys_d = list(zip(frame["district"], frame["date"]))
    frame["y"] = [int(k in t_days) for k in keys_t]
    frame["near_event"] = [kt in t_near or kd in d_near for kt, kd in zip(keys_t, keys_d)]
    frame["train"] = (frame["y"] == 1) | ~frame["near_event"]
    tehsil_events = tehsil_events[tehsil_events["date"].map(lambda d: d.month in (6, 7, 8, 9) and d.year in YEARS)]
    return frame.reset_index(drop=True), tehsil_events.reset_index(drop=True)


# ---- alert scoring -------------------------------------------------------------------------

def alert_scores(frame: pd.DataFrame, score: np.ndarray, threshold: float, events: pd.DataFrame) -> dict:
    alerts = frame.loc[score >= threshold, ["tehsil_id", "date", "near_event"]]
    alert_keys = set(zip(alerts["tehsil_id"], alerts["date"]))
    one = dt.timedelta(days=1)
    ev = events[events["tehsil_id"].isin(set(frame["tehsil_id"])) & events["date"].isin(set(frame["date"]))]
    hits = sum(any((t, d + k * one) in alert_keys for k in (-1, 0, 1)) for t, d in zip(ev["tehsil_id"], ev["date"]))
    false = alerts[~alerts["near_event"]].sort_values(["tehsil_id", "date"])
    episodes = 0
    for _, part in false.groupby("tehsil_id"):
        days = pd.to_datetime(part["date"]).to_numpy()
        episodes += 1 + int((np.diff(days) > np.timedelta64(1, "D")).sum())
    n_tehsil_seasons = frame.groupby(["tehsil_id", "year"]).ngroups
    return {"threshold": float(threshold), "events": int(len(ev)), "hits": int(hits),
            "hit_rate": hits / len(ev) if len(ev) else float("nan"),
            "false_alerts_per_tehsil_season": episodes / n_tehsil_seasons,
            "alert_days_share": float((score >= threshold).mean())}


def threshold_for(frame: pd.DataFrame, score: np.ndarray, events: pd.DataFrame, target_fa: float) -> dict:
    """Lowest threshold whose false-alert rate is at or below the target."""

    candidates = np.unique(np.quantile(score, np.linspace(0.80, 0.99995, 400)))
    best = None
    for thr in candidates:
        result = alert_scores(frame, score, thr, events)
        if result["false_alerts_per_tehsil_season"] <= target_fa:
            return result
        best = result
    return best


# ---- models --------------------------------------------------------------------------------

@dataclass
class FoldResult:
    oof: np.ndarray
    models: dict


def cross_validate(frame: pd.DataFrame, features: list[str], group: str, kind: str = "lightgbm") -> FoldResult:
    oof = np.full(len(frame), np.nan)
    models = {}
    for key in sorted(frame[group].unique()):
        test = frame[group] == key
        train = frame[~test & frame["train"]]
        if train["y"].sum() == 0:
            continue
        model = fit_model(kind, train, features)
        oof[test.to_numpy()] = model.predict_proba(frame.loc[test, features])[:, 1]
        models[key] = model
    return FoldResult(oof, models)


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def fit_platt(raw: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    lr = LogisticRegression(C=1e6)
    lr.fit(logit(raw).reshape(-1, 1), y)
    return float(lr.coef_[0, 0]), float(lr.intercept_[0])


def apply_platt(raw: np.ndarray, a: float, b: float) -> np.ndarray:
    return 1 / (1 + np.exp(-(a * logit(raw) + b)))


def row_metrics(y: np.ndarray, p: np.ndarray) -> dict:
    return {"roc_auc": float(roc_auc_score(y, p)), "pr_auc": float(average_precision_score(y, p)),
            "brier": float(brier_score_loss(y, p)) if p.max() <= 1 else float("nan"), "base_rate": float(y.mean())}


def reliability(y: np.ndarray, p: np.ndarray, bins: int = 8) -> pd.DataFrame:
    edges = np.unique(np.quantile(p, np.linspace(0, 1, bins + 1)))
    idx = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, len(edges) - 2)
    rows = []
    for i in range(len(edges) - 1):
        m = idx == i
        if m.sum():
            rows.append({"predicted (mean)": float(p[m].mean()), "observed rate": float(y[m].mean()),
                         "rows": int(m.sum()), "events": int(y[m].sum())})
    return pd.DataFrame(rows)


# ---- forecast gap --------------------------------------------------------------------------

def forecast_gap(data: Path, frame: pd.DataFrame, loso: FoldResult, platt: tuple[float, float],
                 events: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """Score archived forecasts (2024–2025) with the season-held-out model of that year."""

    hydro = pd.read_parquet(data / "features" / "hydromet_daily.parquet")
    fc = hydro[(hydro["model"] != "era5")]
    fc = fc[pd.to_datetime(fc["date"]).dt.month.between(6, 9)]
    static = load_static(data)
    rows = []
    for year in (2024, 2025):
        if year not in loso.models:
            continue
        model = loso.models[year]
        part = build_matrix(fc[pd.to_datetime(fc["date"]).dt.year == year], static)
        part = part[part["tehsil_id"].isin(set(frame["tehsil_id"]))]
        part["p"] = apply_platt(model.predict_proba(part[FEATURES])[:, 1], *platt)
        base = frame[frame["year"] == year][["tehsil_id", "date", "year", "near_event"]]
        for lead in range(4):
            lead_part = part[part["lead_days"] == lead]
            ens = lead_part.groupby(["tehsil_id", "date"])["p"].mean().rename("ens")
            per_model = lead_part.pivot_table(index=["tehsil_id", "date"], columns="model", values="p")
            merged = base.merge(ens.reset_index(), on=["tehsil_id", "date"]) \
                .merge(per_model.reset_index(), on=["tehsil_id", "date"])
            for source in ["ens", "ecmwf", "gfs", "icon"]:
                r = alert_scores(merged, merged[source].to_numpy(), threshold, events)
                rows.append({"year": year, "lead": lead, "source": "3-model mean" if source == "ens" else source, **r})
        era = frame[frame["year"] == year]
        r = alert_scores(era, era["p_cal"].to_numpy(), threshold, events)
        rows.append({"year": year, "lead": "analysis", "source": "ERA5 (what actually fell)", **r})
    return pd.DataFrame(rows)


# ---- main ----------------------------------------------------------------------------------

def _md(frame: pd.DataFrame) -> str:
    from pipelines.hydromet.qa import _md as md

    return md(frame)


def main() -> int:
    settings = get_settings()
    data = settings.data_dir
    target_fa = settings.alert_false_alarm_target_per_season
    frame, events = build_dataset(data)
    train_rows = frame[frame["train"]]
    print(f"rows {len(frame)}, training rows {len(train_rows)}, positives {int(frame['y'].sum())}, "
          f"tehsil events {len(events)}")

    rain_only = RAIN_ONLY_FEATURES
    hit_col = f"hit rate at {target_fa:g} false alerts"
    y = frame.loc[frame["train"], "y"].to_numpy()
    mask = frame["train"].to_numpy()

    def score_row(name: str, score: np.ndarray) -> dict:
        valid = ~np.isnan(score)
        rm = row_metrics(frame.loc[valid & mask, "y"].to_numpy(), score[valid & mask])
        al = threshold_for(frame[valid], score[valid], events, target_fa)
        return {"method": name, "ROC-AUC": rm["roc_auc"], "PR-AUC": rm["pr_auc"], hit_col: al["hit_rate"],
                "false alerts / tehsil-season": al["false_alerts_per_tehsil_season"], "events": al["events"]}

    # 1. Compare model types (all features), seasons held out and districts held out.
    loso_by_kind, candidate_rows = {}, []
    for kind in KINDS:
        loso_k = cross_validate(frame, FEATURES, "year", kind)
        lodo_k = cross_validate(frame, FEATURES, "district", kind)
        loso_by_kind[kind] = loso_k
        a_row, b_row = score_row(kind, loso_k.oof), score_row(kind, lodo_k.oof)
        candidate_rows.append({"model": kind, "seasons held out: hit rate": a_row[hit_col],
                               "seasons held out: PR-AUC": a_row["PR-AUC"],
                               "seasons held out: ROC-AUC": a_row["ROC-AUC"],
                               "districts held out: hit rate": b_row[hit_col],
                               "districts held out: PR-AUC": b_row["PR-AUC"]})
        print(f"{kind}: LOSO hit {a_row[hit_col]:.2f} PR {a_row['PR-AUC']:.3f} | "
              f"LODO hit {b_row[hit_col]:.2f} PR {b_row['PR-AUC']:.3f}", flush=True)
    candidates = pd.DataFrame(candidate_rows)
    # Pick: mean of the two hit rates, PR-AUC breaks ties; simpler models come first in KINDS.
    score = (candidates["seasons held out: hit rate"] + candidates["districts held out: hit rate"]) / 2 \
        + 0.01 * candidates["seasons held out: PR-AUC"]
    best_kind = str(candidates.loc[score.round(4).idxmax(), "model"])

    # 2. The chosen model against the baselines.
    loso = loso_by_kind[best_kind]
    lodo = cross_validate(frame, FEATURES, "district", best_kind)
    loso_rain = cross_validate(frame, rain_only, "year", best_kind)
    platt = fit_platt(loso.oof[frame["train"]], frame.loc[frame["train"], "y"].to_numpy())
    frame["p_cal"] = apply_platt(loso.oof, *platt)
    rain_vars = {c: frame[c].to_numpy() for c in ("precip_sum", "precip_cell_max", "precip_3d")}
    best_rain = max(rain_vars, key=lambda c: average_precision_score(y, rain_vars[c][mask]))
    comparison = pd.DataFrame([
        score_row(f"{best_kind} (rain + terrain), seasons held out", loso.oof),
        score_row(f"{best_kind} (rain + terrain), districts held out", lodo.oof),
        score_row(f"{best_kind} ERA5-only rain model, seasons held out", loso_rain.oof),
        score_row(f"Rain threshold ({best_rain})", rain_vars[best_rain]),
    ])
    model_row, base_row = comparison.iloc[0], comparison.iloc[3]
    gate = bool(model_row[hit_col] > base_row[hit_col] and model_row["PR-AUC"] > base_row["PR-AUC"])

    # Levels on the calibrated season-held-out probabilities.
    p = frame["p_cal"].to_numpy()
    levels = {}
    for level, fa in {"moderate": LEVEL_FA_TARGETS["moderate"], "high": target_fa,
                      "very_high": LEVEL_FA_TARGETS["very_high"]}.items():
        r = threshold_for(frame, p, events, fa)
        levels[level] = {"probability": round(r["threshold"], 5), "target_false_alerts_per_tehsil_season": fa,
                         "hit_rate": round(r["hit_rate"], 3),
                         "false_alerts_per_tehsil_season": round(r["false_alerts_per_tehsil_season"], 2)}
    calib = row_metrics(y, p[mask])
    rel = reliability(y, p[mask])

    # Final model on all training rows.
    final = fit_model(best_kind, train_rows, FEATURES)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    for old in ARTIFACT_DIR.glob("model.*"):
        old.unlink()
    joblib.dump(final, ARTIFACT_DIR / "model.joblib")
    meta = {
        "version": "v1", "trained_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "model_kind": best_kind, "features": FEATURES, "monotone": MONOTONE,
        "feature_medians": {f: float(train_rows[f].median()) for f in FEATURES},
        "calibration": {"method": "platt", "a": platt[0], "b": platt[1]},
        "levels": levels, "period": "Jun-Sep 2019-2025", "tehsils": int(frame["tehsil_id"].nunique()),
        "rows": int(len(frame)), "training_rows": int(len(train_rows)), "positives": int(frame["y"].sum()),
        "fallback": not gate,
    }
    (ARTIFACT_DIR / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    gap = forecast_gap(data, frame, loso, platt, events, levels["high"]["probability"])
    importance = feature_influence(final, train_rows, FEATURES)

    metrics = {"gate_g2_passed": gate, "model_kind": best_kind, "candidates": candidates.to_dict("records"),
               "comparison": comparison.to_dict("records"), "calibrated": calib,
               "levels": levels, "reliability": rel.to_dict("records"),
               "forecast_gap": gap.to_dict("records")}
    (ARTIFACT_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2, default=float), encoding="utf-8")
    frame[["tehsil_id", "date", "year", "y", "train", "near_event", "p_cal"]].to_parquet(
        data / "features" / "risk_oof.parquet", index=False)

    write_report(candidates, best_kind, comparison, gate, levels, calib, rel, gap, importance, meta, frame,
                 events, target_fa)
    print(json.dumps({"gate_g2": gate, "levels": levels}, indent=2))
    return 0


def feature_influence(model, rows: pd.DataFrame, features: list[str], n: int = 3000) -> pd.DataFrame:
    """Mean change in log-odds when one feature is set to its median (works for any model)."""

    sample = rows.sample(min(n, len(rows)), random_state=7)
    base = logit(model.predict_proba(sample[features])[:, 1])
    out = []
    for f in features:
        changed = sample[features].copy()
        changed[f] = rows[f].median()
        out.append({"feature": f, "share": float(np.abs(base - logit(model.predict_proba(changed)[:, 1])).mean())})
    frame = pd.DataFrame(out).sort_values("share", ascending=False)
    frame["share"] = frame["share"] / frame["share"].sum()
    return frame


def write_report(candidates, best_kind, comparison, gate, levels, calib, rel, gap, importance, meta, frame, events, target_fa) -> None:
    per_year = frame.groupby("year").agg(positives=("y", "sum"), tehsil_days=("y", "size")).reset_index()
    lv = pd.DataFrame([{"level": k, **v} for k, v in levels.items()])
    gap_view = gap[["year", "lead", "source", "events", "hits", "hit_rate", "false_alerts_per_tehsil_season"]]
    text = f"""# M5 risk model QA

Generated {dt.date.today()} by `python -m pipelines.risk.train`. Model artifact:
`backend/app/risk/artifacts/v1/` (model.joblib + Platt calibration in meta.json).

## Gate G2

**{'Passed' if gate else 'NOT passed: ship the calibrated threshold model, labelled as such'}.** The model
(seasons held out) must beat the best single rain threshold on hit rate at the same false-alert
rate ({target_fa:g} per tehsil per season) and on PR-AUC.

## Data

- {meta['rows']:,} tehsil-days ({meta['tehsils']} in-scope tehsils, Jun–Sep 2019–2025); {meta['training_rows']:,} used for training.
- {meta['positives']} positive tehsil-days ({len(events)} tehsil-level flood events in these months).
- Left out of training: the day either side of an event, and districts on days PDMA named only the district.

{_md(per_year)}

## Feature sets x model types (exploration, `python -m pipelines.risk.experiment`)

{_md(pd.read_csv(get_settings().data_dir / "features" / "risk_experiment.csv")) if (get_settings().data_dir / "features" / "risk_experiment.csv").is_file() else "not run"}

With all {len(ALL_FEATURES)} features, tree models latched onto season, temperature and
population and lost to a plain rain threshold. A small rain-centred set with a logistic
model generalised best, so that set is used below.

## Model types compared on the chosen features (same folds, same false-alert rate)

{_md(candidates)}

Chosen: **{best_kind}** (best average hit rate over held-out seasons and held-out districts;
PR-AUC breaks ties). Hit rate = share of tehsil-level events caught at {target_fa:g} false alerts
per tehsil per season.

## Chosen model against the baselines (same false-alert rate)

{_md(comparison)}

How alerts are scored: an event counts as caught if an alert was on the day before, the day, or the
day after. A false alert is a run of alert days in a tehsil with no event within a day. Rates are per
tehsil per season (122 days).

## Alert levels (calibrated probability)

{_md(lv)}

`high` uses `NIGEHBAN_ALERT_FALSE_ALARM_TARGET_PER_SEASON` ({target_fa:g}). Levels come only from the
model and these fixed thresholds, never from the LLM.

## Calibration (seasons held out, Platt scaling)

ROC-AUC {calib['roc_auc']:.3f}, PR-AUC {calib['pr_auc']:.3f}, Brier {calib['brier']:.5f}
(base rate {calib['base_rate']:.4f}).

{_md(rel)}

## With real forecasts (2024–2025, archived runs, season held out)

Same model and "high" threshold, fed with what each weather model forecast 0–3 days ahead,
compared with feeding it ERA5 (what actually fell, known only afterwards).

{_md(gap_view)}

## What the model leans on (share of influence)

{_md(importance.head(12))}

## Limits

- About {meta['positives']} positive days: the model is pooled across tehsils and kept simple
  (monotone in rain and soil moisture, shallow trees).
- Labels are PDMA reports: floods that hurt nobody, or happened in remote places, are missing,
  so some "false alerts" are real floods nobody reported.
- ERA5 is 25 km; local cloudbursts are smoothed, which caps what any rain-based model can catch.
- Archived forecasts exist only from 2024, so the forecast check rests on two seasons.
"""
    Path("reports/risk_model.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
