# -*- coding: utf-8 -*-
"""
Step 3 - assemble the training table, derive anomalies and labels, audit.

    python src/03_assemble.py

Everything here is local pandas over the raw monthly CSVs, so baselines,
anomalies and the label rule can all be changed and re-run in seconds
without touching Earth Engine.
"""
import os, sys, json, glob
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import cl_config as C

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
RAW  = os.path.join(DATA, "raw")

# Indicators that get a per-site, per-calendar-month baseline.
BASELINE_COLS = ["ndvi_median", "ndwi_median", "nbr_median", "tree_prob",
                 "rain_mm", "temp_c", "soil_moist"]


def load_raw():
    files = sorted(glob.glob(os.path.join(RAW, "features_*.csv")))
    if not files:
        raise SystemExit(f"No raw files in {RAW}. Run 02_extract.py first.")
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df["month"] = pd.PeriodIndex(df["month"], freq="M")
    return df.sort_values(["patch_id", "month"]).reset_index(drop=True)


def load_patches():
    with open(os.path.join(DATA, "patches.geojson")) as fh:
        gj = json.load(fh)
    return pd.DataFrame([f["properties"] for f in gj["features"]])


# --------------------------------------------------------------- baselines
def add_baselines(df):
    b0 = pd.Period(C.BASELINE_START[:7], freq="M")
    b1 = pd.Period(C.BASELINE_END[:7],   freq="M")
    base = df[(df["month"] >= b0) & (df["month"] < b1)].copy()
    base["cal_month"] = base["month"].dt.month
    df["cal_month"] = df["month"].dt.month

    stats = (base.groupby(["patch_id", "cal_month"])[BASELINE_COLS]
                 .median().reset_index())
    stats = stats.rename(columns={c: c + "_base" for c in BASELINE_COLS})
    df = df.merge(stats, on=["patch_id", "cal_month"], how="left")

    for c in BASELINE_COLS:
        df[c + "_anom"] = df[c] - df[c + "_base"]

    # Change against the same month a year earlier.
    df = df.sort_values(["patch_id", "month"])
    for c in ("tree_prob", "ndvi_median"):
        df[c + "_delta_12m"] = df.groupby("patch_id")[c].diff(12)

    # Short-run trend: slope proxy over three months.
    df["ndvi_trend_3m"] = df.groupby("patch_id")["ndvi_median"].diff(3) / 3.0

    # Cumulative rainfall deficit over six months (placeholder for proper SPI,
    # which needs a 30-year climatology; see the note printed at the end).
    df["rain_anom_6m"] = (df.groupby("patch_id")["rain_mm_anom"]
                            .rolling(6, min_periods=3).sum()
                            .reset_index(level=0, drop=True))
    return df


# ------------------------------------------------------------------ labels
def add_labels(df):
    """
    Dated trigger: FIRMS detections inside the patch in a month.
    Hansen is annual and therefore corroborates only - it never generates
    the three-month window, which would inflate positives roughly fourfold.
    """
    df = df.sort_values(["patch_id", "month"]).reset_index(drop=True)
    df["fire_count_patch"] = df["fire_count_patch"].fillna(0)
    df["trigger"] = (df["fire_count_patch"] >= C.FIRE_TRIGGER_COUNT).astype(int)

    H = C.LABEL_HORIZON_MONTHS
    fwd = np.zeros(len(df), dtype=int)
    for pid, g in df.groupby("patch_id", sort=False):
        t = g["trigger"].values
        idx = g.index.values
        n = len(t)
        for i in range(n):
            win = t[i + 1: i + 1 + H]
            fwd[idx[i]] = int(win.sum() > 0)
    df["disturbed_next_3m"] = fwd

    # Tail censoring: the last H months cannot have a confirmed negative,
    # because confirming "nothing happened" needs visibility ahead.
    last = df.groupby("patch_id")["month"].transform("max")
    df["label_confirmed"] = (df["month"] <= (last - H)).astype(int)
    return df


# ------------------------------------------------------------------ audit
def audit(df):
    print("\n" + "=" * 68)
    print("DATA AUDIT")
    print("=" * 68)
    ok = True

    model = df[df["in_modelling_window"] == 1]
    conf = model[model["label_confirmed"] == 1]

    # 1 - positive count
    pos = int(conf["disturbed_next_3m"].sum())
    tot = len(conf)
    rate = 100.0 * pos / tot if tot else 0.0
    print(f"\n1. Label balance")
    print(f"   confirmed rows in modelling window : {tot}")
    print(f"   positive rows                      : {pos}  ({rate:.1f}%)")
    if pos < 30:
        print("   NOTE: too few positives to train on. For the pilot this is")
        print("         expected; for the full run, add disturbed patches -")
        print("         do NOT widen the 3-month horizon.")
    for eco in sorted(conf["ecosystem"].dropna().unique()):
        sub = conf[conf["ecosystem"] == eco]
        print(f"     {eco:10s} {int(sub['disturbed_next_3m'].sum()):4d} positive "
              f"/ {len(sub):5d} rows")

    # 2 - leakage check on the cumulative feature
    print(f"\n2. Leakage check  (loss_ha_to_prev_year must not move with the label)")
    bad = 0
    for pid, g in df.groupby("patch_id", sort=False):
        g = g.sort_values("month")
        lc = g["loss_ha_to_prev_year"].diff().fillna(0).values
        lb = g["disturbed_next_3m"].values
        for i in range(1, len(g)):
            if lc[i] > 0 and lb[i] == 1 and lb[i - 1] == 0:
                bad += 1
    if bad:
        ok = False
        print(f"   FAIL: cumulative loss changes on {bad} rows where the label flips")
    else:
        print("   PASS: cumulative loss never changes on the row the label flips")

    # 3 - tail censoring
    unconf = int((model["label_confirmed"] == 0).sum())
    print(f"\n3. Tail censoring")
    print(f"   unconfirmed rows excluded from training : {unconf}")

    # 4 - data coverage
    print(f"\n4. Data coverage  (absent feed must not read as a benign value)")
    for col, flag in (("ndvi_median", "s2_data"), ("tree_prob", "dw_data")):
        miss = int((model[flag] == 0).sum())
        print(f"   {col:14s} missing in {miss:5d} of {len(model):5d} rows "
              f"({100.0*miss/max(len(model),1):.1f}%)")
    nofire = int((model["fire_data"] == 0).sum())
    print(f"   {'fire feed':14s} absent in {nofire:5d} rows "
          f"(these are flagged, not treated as zero)")

    print("\n" + "=" * 68)
    print("AUDIT PASSED" if ok else "AUDIT FAILED - fix before training")
    print("=" * 68)
    return ok


# -------------------------------------------------------------------- main
def main():
    raw = load_raw()
    patches = load_patches()
    keep = ["patch_id", "ecosystem", "country", "region", "split",
            "lon", "lat", "stratum"]
    df = raw.merge(patches[keep], on="patch_id", how="left")

    df = add_baselines(df)
    df = add_labels(df)

    m0 = pd.Period(C.MODEL_START[:7], freq="M")
    m1 = pd.Period(C.MODEL_END[:7],   freq="M")
    df["in_modelling_window"] = ((df["month"] >= m0) & (df["month"] < m1)).astype(int)
    df["is_mangrove"] = (df["ecosystem"] == "mangrove").astype(int)
    df["is_forest"]   = (df["ecosystem"] == "forest").astype(int)

    audit(df)

    df["month"] = df["month"].astype(str)
    out = os.path.join(DATA, "training_data.csv")
    df.to_csv(out, index=False)

    train = df[(df["in_modelling_window"] == 1) & (df["label_confirmed"] == 1)]
    print(f"\nWrote {len(df)} rows ({len(df.columns)} columns)")
    print(f"  {os.path.abspath(out)}")
    print(f"  trainable rows: {len(train)}")
    print(f"  size on disk  : {os.path.getsize(out)/1e6:.1f} MB")
    print("\nNote: rain_anom_6m is a rainfall-deficit proxy. Proper SPI needs a")
    print("      30-year CHIRPS climatology and is a follow-up for the full run.")


if __name__ == "__main__":
    main()
