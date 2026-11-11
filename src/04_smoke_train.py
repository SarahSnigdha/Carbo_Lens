# -*- coding: utf-8 -*-
"""
Step 4 - SMOKE TEST ONLY.

    python src/04_smoke_train.py

This confirms the assembled table is trainable: that the features load, the
splits group correctly, and the models run end to end.  On a pilot sample
the positive count is far too small for the numbers to mean anything, and
they must NOT be reported as results.  Reportable metrics come from the
full sample with the sealed test countries, per Chapter 8 of the report.
"""
import os, sys, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import cl_config as C

from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GroupKFold
from sklearn.metrics import precision_score, recall_score, average_precision_score

DATA = os.path.join(os.path.dirname(__file__), "..", "data")

FEATURES = [
    "ndvi_median_anom", "ndvi_trend_3m", "ndvi_median_delta_12m",
    "ndwi_median_anom", "nbr_median_anom",
    "tree_prob_anom", "tree_prob_delta_12m",
    "rain_mm_anom", "rain_anom_6m", "temp_c_anom", "soil_moist_anom",
    "wind_ms", "fire_count_5km", "loss_ha_to_prev_year",
    "is_forest", "is_mangrove",
]
TARGET = "disturbed_next_3m"


def main():
    path = os.path.join(DATA, "training_data.csv")
    df = pd.read_csv(path)

    df = df[(df["in_modelling_window"] == 1) & (df["label_confirmed"] == 1)].copy()
    have = [c for c in FEATURES if c in df.columns]
    missing = [c for c in FEATURES if c not in df.columns]
    if missing:
        print(f"note: columns not present, skipped -> {missing}")

    df = df.dropna(subset=[TARGET])
    X = df[have].fillna(0.0).values
    y = df[TARGET].astype(int).values
    groups = df["patch_id"].values

    print("=" * 68)
    print("SMOKE TEST - NOT A RESULT")
    print("=" * 68)
    print(f"rows            : {len(df)}")
    print(f"features        : {len(have)}")
    print(f"positives       : {int(y.sum())}  ({100.0*y.mean():.1f}%)")
    print(f"patches         : {df['patch_id'].nunique()}")
    print(f"countries       : {df['country'].nunique()}")

    if y.sum() < 10:
        print("\nToo few positives to fit anything meaningful. The table is built;")
        print("model fitting waits for the full sample.")
        return

    n_splits = min(4, df["patch_id"].nunique(), int(y.sum()))
    gkf = GroupKFold(n_splits=n_splits)

    rows = []
    for name, model in (
        ("logistic regression", make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=2000, class_weight="balanced"))),
        ("random forest", RandomForestClassifier(
            n_estimators=300, class_weight="balanced",
            min_samples_leaf=2, random_state=C.SEED, n_jobs=-1)),
    ):
        p_s, r_s, a_s = [], [], []
        for tr, te in gkf.split(X, y, groups):
            if y[tr].sum() == 0 or y[te].sum() == 0:
                continue
            model.fit(X[tr], y[tr])
            pred = model.predict(X[te])
            prob = model.predict_proba(X[te])[:, 1]
            p_s.append(precision_score(y[te], pred, zero_division=0))
            r_s.append(recall_score(y[te], pred, zero_division=0))
            a_s.append(average_precision_score(y[te], prob))
        if p_s:
            rows.append((name, np.mean(p_s), np.mean(r_s), np.mean(a_s), len(p_s)))

    print(f"\nGrouped cross-validation by patch  ({n_splits} folds)")
    print(f"  {'model':22s} {'prec':>6s} {'rec':>6s} {'PR-AUC':>7s}  folds")
    for name, p, r, a, k in rows:
        print(f"  {name:22s} {p:6.2f} {r:6.2f} {a:7.2f}  {k}")

    # Isolation Forest, fitted per site on that site's own history.
    print("\nPer-site anomaly detector")
    scored = 0
    for pid, g in df.groupby("patch_id"):
        if len(g) < 24:
            continue
        iso = IsolationForest(contamination=0.08, random_state=C.SEED)
        iso.fit(g[have].fillna(0.0).values)
        scored += 1
    print(f"  fitted on {scored} sites with at least 24 months of history")

    print("\n" + "=" * 68)
    print("Pipeline runs end to end. These numbers are a smoke test on a pilot")
    print("sample and are NOT reportable. Reportable metrics come from the full")
    print("sample with the sealed test countries.")
    print("=" * 68)


if __name__ == "__main__":
    main()
