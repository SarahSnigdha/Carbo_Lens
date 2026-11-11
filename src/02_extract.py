# -*- coding: utf-8 -*-
"""
Step 2 - extract raw monthly values for every patch.

    python src/02_extract.py              # all months
    python src/02_extract.py --months 3   # smoke test: first 3 months only

One CSV per month is written to data/raw/.  A month already on disk is
skipped, so the run RESUMES after a crash or an interrupt instead of
starting over.

Only RAW values are extracted here.  Baselines, anomalies and labels are
derived locally in step 3, so those can be changed without re-running any
Earth Engine query.
"""
import os, sys, csv, json, argparse
from datetime import date
import ee

sys.path.insert(0, os.path.dirname(__file__))
import cl_config as C
import cl_ee as E

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
RAW  = os.path.join(DATA, "raw")

FIELDS = [
    "patch_id", "month",
    "ndvi_median", "ndvi_min", "ndwi_median", "nbr_median",
    "tree_prob", "water_prob", "built_prob",
    "rain_mm", "temp_c", "soil_moist", "wind_ms",
    "fire_count_patch", "fire_count_5km",
    "loss_ha_to_prev_year",
    "n_clear_images", "s2_data", "dw_data", "fire_data",
]


def month_list(start, end):
    y, m = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    out = []
    while (y, m) < (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def load_patches():
    with open(os.path.join(DATA, "patches.geojson")) as fh:
        gj = json.load(fh)
    patches = []
    for f in gj["features"]:
        p = f["properties"]
        ring = f["geometry"]["coordinates"][0]
        lons = [c[0] for c in ring]; lats = [c[1] for c in ring]
        patches.append({
            "patch_id": p["patch_id"], "ecosystem": p["ecosystem"],
            "lon": p["lon"], "lat": p["lat"],
            "bbox": [min(lons), min(lats), max(lons), max(lats)],
        })
    return patches


def feature_collection(sub):
    return ee.FeatureCollection([
        ee.Feature(ee.Geometry.Rectangle(p["bbox"]), {"patch_id": p["patch_id"]})
        for p in sub])


def buffered_collection(sub, metres):
    return ee.FeatureCollection([
        ee.Feature(ee.Geometry.Rectangle(p["bbox"]).buffer(metres).bounds(),
                   {"patch_id": p["patch_id"]})
        for p in sub])


def reduce_bands(image, fc, reducer, scale, bands, key):
    """
    One reduceRegions call for a multi-band image.

    Earth Engine names the output property after the REDUCER when the image
    has a single band, and after each BAND when it has several, so both
    cases are handled here.  Reducing all bands of a dataset together is what
    keeps the number of server round trips manageable.
    """
    res = E.retry(lambda: image.reduceRegions(fc, reducer, scale).getInfo(), key)
    out = {}
    for f in res["features"]:
        props = f["properties"]
        pid = props.get("patch_id")
        vals = {}
        if len(bands) == 1:
            got = None
            for k in ("mean", "sum", "min", "max", "count", "first"):
                if k in props:
                    got = props[k]
                    break
            vals[bands[0]] = got
        else:
            for b in bands:
                vals[b] = props.get(b)
        out[pid] = vals
    return out


def one(m, pid, band):
    """Read a single band value out of a reduce_bands result."""
    return (m.get(pid) or {}).get(band)


def extract_month(ym, patches):
    y, m = int(ym[:4]), int(ym[5:7])
    start = ee.Date.fromYMD(y, m, 1)
    end = start.advance(1, "month")
    rows = {p["patch_id"]: {"patch_id": p["patch_id"], "month": ym} for p in patches}

    loss_prev = E.hansen_loss_ha_through(y - 1)   # strictly before the current year

    for sub in E.chunks(patches, C.CHUNK_SIZE):
        fc = feature_collection(sub)
        fc5 = buffered_collection(sub, 5000)
        geom = fc.geometry()

        # ---- Sentinel-2 indices: all three bands in ONE call
        s2 = E.s2_collection(geom, start, end)
        n_img = E.retry(lambda: s2.size().getInfo(), f"s2 size {ym}")
        if n_img > 0:
            opt = reduce_bands(s2.median(), fc, ee.Reducer.mean(), 30,
                               ["ndvi", "ndwi", "nbr"], f"s2 {ym}")
            mn = reduce_bands(s2.select("ndvi").min().rename("ndvi_min"), fc,
                              ee.Reducer.mean(), 30, ["ndvi_min"], f"ndvimin {ym}")
        else:
            opt = mn = {}

        # ---- Dynamic World: all three classes in ONE call
        dw = (ee.ImageCollection(C.ASSETS["dw"])
              .filterBounds(geom).filterDate(start, end))
        n_dw = E.retry(lambda: dw.size().getInfo(), f"dw size {ym}")
        if n_dw > 0:
            dwv = reduce_bands(dw.mean().select(["trees", "water", "built"]), fc,
                               ee.Reducer.mean(), 30,
                               ["trees", "water", "built"], f"dw {ym}")
        else:
            dwv = {}

        # ---- CHIRPS rainfall (monthly total)
        rain_img = (ee.ImageCollection(C.ASSETS["chirps"])
                    .filterDate(start, end).select("precipitation").sum()
                    .rename("rain"))
        rainv = reduce_bands(rain_img, fc, ee.Reducer.mean(), 5000,
                             ["rain"], f"rain {ym}")

        # ---- ERA5-Land: temperature, soil moisture and wind in ONE call
        ecol = ee.ImageCollection(C.ASSETS["era5"]).filterDate(start, end)
        n_era = E.retry(lambda: ecol.size().getInfo(), f"era size {ym}")
        erav = {}
        if n_era > 0:
            era = ee.Image(ecol.first())
            t_c = era.select("temperature_2m").subtract(273.15).rename("temp")
            sm  = era.select("volumetric_soil_water_layer_1").rename("soil")
            u   = era.select("u_component_of_wind_10m")
            v   = era.select("v_component_of_wind_10m")
            spd = u.pow(2).add(v.pow(2)).sqrt().rename("wind")
            erav = reduce_bands(ee.Image.cat([t_c, sm, spd]), fc,
                                ee.Reducer.mean(), 11000,
                                ["temp", "soil", "wind"], f"era {ym}")

        # ---- FIRMS fire detections, inside the patch and within 5 km
        fcol = (ee.ImageCollection(C.ASSETS["firms"]).select("T21")
                .filterDate(start, end))
        n_fire_img = E.retry(lambda: fcol.size().getInfo(), f"firms size {ym}")
        if n_fire_img > 0:
            fimg = fcol.max().rename("fire")
            fin = reduce_bands(fimg, fc,  ee.Reducer.count(), 1000,
                               ["fire"], f"fire {ym}")
            f5k = reduce_bands(fimg, fc5, ee.Reducer.count(), 1000,
                               ["fire"], f"fire5 {ym}")
        else:
            fin = f5k = {}

        # ---- Hansen cumulative loss, strictly to the PREVIOUS year
        lp = reduce_bands(loss_prev.unmask(0).rename("loss"), fc,
                          ee.Reducer.sum(), 30, ["loss"], f"loss {ym}")

        for p in sub:
            pid = p["patch_id"]
            r = rows[pid]
            r["ndvi_median"] = one(opt, pid, "ndvi")
            r["ndvi_min"]    = one(mn,  pid, "ndvi_min")
            r["ndwi_median"] = one(opt, pid, "ndwi")
            r["nbr_median"]  = one(opt, pid, "nbr")
            r["tree_prob"]   = one(dwv, pid, "trees")
            r["water_prob"]  = one(dwv, pid, "water")
            r["built_prob"]  = one(dwv, pid, "built")
            r["rain_mm"]     = one(rainv, pid, "rain")
            r["temp_c"]      = one(erav, pid, "temp")
            r["soil_moist"]  = one(erav, pid, "soil")
            r["wind_ms"]     = one(erav, pid, "wind")
            r["fire_count_patch"] = one(fin, pid, "fire") or 0
            r["fire_count_5km"]   = one(f5k, pid, "fire") or 0
            r["loss_ha_to_prev_year"] = one(lp, pid, "loss") or 0.0
            r["n_clear_images"] = n_img
            # Coverage flags: an absent feed must never look like a quiet month.
            r["s2_data"]   = int(n_img > 0 and one(opt, pid, "ndvi") is not None)
            r["dw_data"]   = int(n_dw > 0 and one(dwv, pid, "trees") is not None)
            r["fire_data"] = int(n_fire_img > 0)

    return [rows[p["patch_id"]] for p in patches]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=0,
                    help="extract only the first N months (smoke test)")
    ap.add_argument("--start", default=C.EXTRACT_START)
    ap.add_argument("--end",   default=C.EXTRACT_END)
    args = ap.parse_args()

    E.init()
    os.makedirs(RAW, exist_ok=True)
    patches = load_patches()
    months = month_list(args.start, args.end)
    if args.months:
        months = months[:args.months]

    print(f"\nExtracting {len(patches)} patches x {len(months)} months")
    print(f"  raw output: {os.path.abspath(RAW)}")
    print("-" * 68)

    for i, ym in enumerate(months, start=1):
        path = os.path.join(RAW, f"features_{ym}.csv")
        if os.path.exists(path):
            print(f"  [{i:3d}/{len(months)}] {ym}  skipped (already on disk)")
            continue
        rows = extract_month(ym, patches)
        tmp = path + ".part"
        with open(tmp, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k) for k in FIELDS})
        os.replace(tmp, path)          # only a complete month lands on disk
        got = sum(1 for r in rows if r.get("ndvi_median") is not None)
        print(f"  [{i:3d}/{len(months)}] {ym}  {len(rows)} rows, "
              f"{got} with optical data")

    print("-" * 68)
    print(f"Done. {len(os.listdir(RAW))} monthly files in {os.path.abspath(RAW)}")


if __name__ == "__main__":
    main()
