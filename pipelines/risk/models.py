"""Candidate models for M5, all trained and scored the same way.

- logistic: standardised features, class-balanced logistic regression (the simple baseline)
- random_forest, extra_trees: class-balanced forests with large leaves
- lightgbm, xgboost: gradient-boosted trees, monotone in rain and soil moisture
  (XGBoost was best in the closest published study: ERA5 + flash-flood reports)

Deep models (LSTM, CNN) are not tried: with under 100 positive days they would
memorise the events. Every model has missing values imputed or handled natively.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.app.risk.features import MONOTONE

KINDS = ["logistic", "random_forest", "extra_trees", "lightgbm", "xgboost"]


def _class_ratio(y: pd.Series) -> float:
    pos = max(int(y.sum()), 1)
    return float(np.sqrt((len(y) - pos) / pos))


def make_model(kind: str, features: list[str], y: pd.Series):
    from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    monotone = [MONOTONE.get(f, 0) for f in features]
    if kind == "logistic":
        return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                             LogisticRegression(C=0.1, class_weight="balanced", max_iter=2000))
    if kind == "random_forest":
        return make_pipeline(SimpleImputer(strategy="median"),
                             RandomForestClassifier(n_estimators=500, min_samples_leaf=20, max_features="sqrt",
                                                    class_weight="balanced_subsample", n_jobs=-1, random_state=7))
    if kind == "extra_trees":
        return make_pipeline(SimpleImputer(strategy="median"),
                             ExtraTreesClassifier(n_estimators=500, min_samples_leaf=20, max_features="sqrt",
                                                  class_weight="balanced_subsample", n_jobs=-1, random_state=7))
    if kind == "lightgbm":
        import lightgbm as lgb

        return lgb.LGBMClassifier(objective="binary", learning_rate=0.03, n_estimators=400, num_leaves=15,
                                  min_child_samples=30, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                                  reg_lambda=1.0, verbose=-1, random_state=7, scale_pos_weight=_class_ratio(y),
                                  monotone_constraints=monotone)
    if kind == "xgboost":
        import xgboost as xgb

        return xgb.XGBClassifier(n_estimators=400, max_depth=4, learning_rate=0.03, subsample=0.8,
                                 colsample_bytree=0.8, min_child_weight=5, reg_lambda=1.0,
                                 scale_pos_weight=_class_ratio(y), monotone_constraints=tuple(monotone),
                                 eval_metric="logloss", n_jobs=4, random_state=7, verbosity=0)
    raise ValueError(f"unknown model kind {kind}")


def fit(kind: str, train: pd.DataFrame, features: list[str]):
    model = make_model(kind, features, train["y"])
    model.fit(train[features], train["y"])
    return model
