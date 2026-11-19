"""Compare model types x feature sets on the same folds (exploration for M5).

    python -m pipelines.risk.experiment
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.app.config import get_settings
from backend.app.risk.features import ALL_FEATURES as FEATURES
from backend.app.risk.features import add_log_features
from pipelines.risk.train import build_dataset, cross_validate, row_metrics, threshold_for

FEATURE_SETS = {
    "all": FEATURES,
    "rain core + 2 terrain": ["log_precip_cell_max", "log_precip_3d", "log_precip_max_1h",
                              "log_precip_7d_antecedent", "soil_moisture_0_7",
                              "log_population", "log_high_villages"],
    "rain core only": ["log_precip_cell_max", "log_precip_3d", "log_precip_max_1h",
                       "log_precip_7d_antecedent", "soil_moisture_0_7"],
    "rain core + terrain": ["log_precip_cell_max", "log_precip_3d", "log_precip_max_1h",
                            "log_precip_7d_antecedent", "soil_moisture_0_7", "log_population",
                            "log_high_villages", "mean_slope", "share_low_hand", "log_catchment_km2"],
}


def main() -> int:
    data = get_settings().data_dir
    target = get_settings().alert_false_alarm_target_per_season
    frame, events = build_dataset(data)
    frame = add_log_features(frame)
    mask = frame["train"].to_numpy()
    rows = []
    for set_name, feats in FEATURE_SETS.items():
        for kind in ("logistic", "lightgbm", "extra_trees"):
            res = {}
            for group in ("year", "district"):
                oof = cross_validate(frame, feats, group, kind).oof
                valid = ~np.isnan(oof)
                al = threshold_for(frame[valid], oof[valid], events, target)
                rm = row_metrics(frame.loc[valid & mask, "y"].to_numpy(), oof[valid & mask])
                res[group] = (al["hit_rate"], rm["pr_auc"])
            rows.append({"features": set_name, "model": kind, "seasons hit": round(res["year"][0], 3),
                         "seasons PR-AUC": round(res["year"][1], 4), "districts hit": round(res["district"][0], 3),
                         "districts PR-AUC": round(res["district"][1], 4)})
            print(rows[-1], flush=True)
    base = frame["precip_cell_max"].to_numpy()
    al = threshold_for(frame, base, events, target)
    print({"features": "threshold precip_cell_max", "hit": round(al["hit_rate"], 3)})
    pd.DataFrame(rows).to_csv(data / "features" / "risk_experiment.csv", index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
