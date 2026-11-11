# -*- coding: utf-8 -*-
"""
Step 1 - build the sampling frame.

    python src/01_make_patches.py --profile pilot

Candidates are ranked ONCE with a fixed seed.  A profile takes the first N
of that ranking per stratum, so `pilot` is a strict subset of `medium`,
which is a strict subset of `full`.  Re-running with a larger profile adds
patches; it never moves the ones already extracted.
"""
import os, sys, json, math, argparse, random
import ee

sys.path.insert(0, os.path.dirname(__file__))
import cl_config as C
import cl_ee as E

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


# ------------------------------------------------------------------ helpers
def haversine_m(lon1, lat1, lon2, lat2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def square_around(lon, lat, side_m):
    """Approximate square of `side_m` centred on the point, in degrees."""
    half = side_m / 2.0
    dlat = half / 111320.0
    dlon = half / (111320.0 * max(math.cos(math.radians(lat)), 0.05))
    return [lon - dlon, lat - dlat, lon + dlon, lat + dlat]


def drop_excluded(points):
    """Remove candidates inside the buffer around any demonstration site."""
    kept = []
    for lon, lat in points:
        blocked = False
        for name, slon, slat, km in C.EXCLUDE_SITES:
            if haversine_m(lon, lat, slon, slat) < km * 1000:
                blocked = True
                break
        if not blocked:
            kept.append((lon, lat))
    return kept


def enforce_spacing(points, min_m):
    """Greedy thinning so no two centres are closer than min_m."""
    kept = []
    for lon, lat in points:
        if all(haversine_m(lon, lat, kl, kt) >= min_m for kl, kt in kept):
            kept.append((lon, lat))
    return kept


# ------------------------------------------------------------------ sampling
def candidates_for_region(name, country, eco, box, rng):
    """Random points in the region, thinned, excluded, then scored in EE."""
    region = ee.Geometry.Rectangle(box)

    pts = ee.FeatureCollection.randomPoints(
        region=region, points=C.CANDIDATES_PER_REGION, seed=C.SEED, maxError=50)
    coords = E.retry(lambda: pts.geometry().coordinates().getInfo(),
                     f"randomPoints {name}")
    coords = [(round(c[0], 6), round(c[1], 6)) for c in coords]

    rng.shuffle(coords)                       # deterministic: rng is seeded
    coords = drop_excluded(coords)
    coords = enforce_spacing(coords, C.MIN_SPACING_M)
    if not coords:
        print(f"    {name}: no candidates survived spacing/exclusion")
        return []

    # Build the candidate squares and score them in Earth Engine.
    feats = []
    for i, (lon, lat) in enumerate(coords):
        g = ee.Geometry.Rectangle(square_around(lon, lat, C.PATCH_SIDE_M))
        feats.append(ee.Feature(g, {"idx": i, "lon": lon, "lat": lat}))
    fc = ee.FeatureCollection(feats)

    elig  = E.eligibility(eco, region)
    lossY = E.hansen_loss_ha_in(2022)
    for y in (2023, 2024, 2025):
        lossY = lossY.add(E.hansen_loss_ha_in(y))
    lossY = lossY.rename("loss_ha")

    fires = (ee.ImageCollection(C.ASSETS["firms"]).select("T21")
             .filterDate(C.MODEL_START, C.MODEL_END).max().rename("fire"))

    scored = []
    for chunk in E.chunks(feats, C.CHUNK_SIZE):
        sub = ee.FeatureCollection(chunk)

        e = E.retry(lambda: elig.unmask(0).reduceRegions(
                sub, ee.Reducer.mean(), 30).getInfo(), f"eligibility {name}")
        l = E.retry(lambda: lossY.unmask(0).reduceRegions(
                sub, ee.Reducer.sum(), 30).getInfo(), f"loss {name}")
        f = E.retry(lambda: fires.reduceRegions(
                sub, ee.Reducer.count(), 1000).getInfo(), f"fire {name}")

        emap = {x["properties"]["idx"]: x["properties"].get("mean") for x in e["features"]}
        lmap = {x["properties"]["idx"]: x["properties"].get("sum")  for x in l["features"]}
        fmap = {x["properties"]["idx"]: x["properties"].get("count") for x in f["features"]}

        for x in e["features"]:
            i = x["properties"]["idx"]
            frac = emap.get(i) or 0.0
            if frac < C.MIN_ELIGIBLE:
                continue
            lon, lat = x["properties"]["lon"], x["properties"]["lat"]
            loss = lmap.get(i) or 0.0
            fire = fmap.get(i) or 0
            disturbed = (loss >= C.DISTURBED_LOSS_HA) or (fire >= C.DISTURBED_FIRE_COUNT)
            scored.append({
                "region": name, "country": country, "ecosystem": eco,
                "lon": lon, "lat": lat,
                "eligible_frac": round(frac, 3),
                "loss_ha_2022_2025": round(loss, 3),
                "fire_count_2022_2025": int(fire),
                "stratum": f"{eco}_{'disturbed' if disturbed else 'undisturbed'}",
            })

    print(f"    {name:20s} {len(coords):4d} candidates -> {len(scored):4d} eligible "
          f"({sum(1 for s in scored if 'undisturbed' not in s['stratum'])} disturbed)")
    return scored


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="pilot", choices=list(C.PROFILES))
    args = ap.parse_args()

    E.init()
    os.makedirs(OUT_DIR, exist_ok=True)
    rng = random.Random(C.SEED)

    print(f"\nBuilding sampling frame  (profile: {args.profile})")
    print("-" * 68)

    pool = []
    for name, country, eco, box in C.REGIONS:
        pool.extend(candidates_for_region(name, country, eco, box, rng))

    # Deterministic ranking: one shuffle with the fixed seed, then interleave
    # regions so that a small profile is still geographically spread.
    rng2 = random.Random(C.SEED)
    rng2.shuffle(pool)
    by_region = {}
    for p in pool:
        by_region.setdefault(p["region"], []).append(p)
    ranked = []
    while any(by_region.values()):
        for r in list(by_region):
            if by_region[r]:
                ranked.append(by_region[r].pop(0))

    # Take the first N of the ranking per stratum.
    want = C.PROFILES[args.profile]
    taken, counts = [], {k: 0 for k in want}
    for p in ranked:
        s = p["stratum"]
        if s in want and counts[s] < want[s]:
            counts[s] += 1
            taken.append(p)

    # Stable ids derived from rank position, so ids never change between profiles.
    for n, p in enumerate(taken, start=1):
        p["patch_id"] = f"{p['ecosystem'][:3].upper()}_{n:04d}"
        p["split"] = C.SPLIT_BY_COUNTRY.get(p["country"], "train")
        p["bbox"] = square_around(p["lon"], p["lat"], C.PATCH_SIDE_M)

    print("-" * 68)
    print("Stratum counts")
    for k in want:
        flag = "" if counts[k] >= want[k] else "   <-- SHORT, widen regions"
        print(f"  {k:24s} {counts[k]:4d} / {want[k]:4d}{flag}")

    print("\nSplit counts")
    for s in ("train", "validate", "test"):
        print(f"  {s:10s} {sum(1 for p in taken if p['split'] == s):4d}")

    # ---- write GeoJSON
    gj = {"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "geometry": {"type": "Polygon", "coordinates": [[
             [p["bbox"][0], p["bbox"][1]], [p["bbox"][2], p["bbox"][1]],
             [p["bbox"][2], p["bbox"][3]], [p["bbox"][0], p["bbox"][3]],
             [p["bbox"][0], p["bbox"][1]]]]},
         "properties": {k: v for k, v in p.items() if k != "bbox"}}
        for p in taken]}
    gj_path = os.path.join(OUT_DIR, "patches.geojson")
    with open(gj_path, "w") as fh:
        json.dump(gj, fh, indent=1)

    # ---- write manifest
    manifest = {
        "profile": args.profile, "seed": C.SEED,
        "patch_count": len(taken), "patch_side_m": C.PATCH_SIDE_M,
        "min_spacing_m": C.MIN_SPACING_M, "min_eligible_frac": C.MIN_ELIGIBLE,
        "baseline_window": [C.BASELINE_START, C.BASELINE_END],
        "modelling_window": [C.MODEL_START, C.MODEL_END],
        "label_horizon_months": C.LABEL_HORIZON_MONTHS,
        "label_trigger": f"FIRMS >= {C.FIRE_TRIGGER_COUNT} detections in patch-month",
        "label_corroboration": "Hansen lossyear, same year",
        "excluded_sites": [{"name": n, "lon": lo, "lat": la, "buffer_km": km}
                           for n, lo, la, km in C.EXCLUDE_SITES],
        "regions": [{"name": n, "country": c, "ecosystem": e, "bbox": b}
                    for n, c, e, b in C.REGIONS],
        "strata": counts,
        "split_by_country": C.SPLIT_BY_COUNTRY,
        "assets": C.ASSETS,
    }
    mf_path = os.path.join(OUT_DIR, "manifest.json")
    with open(mf_path, "w") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"\nWrote {len(taken)} patches")
    print(f"  {os.path.abspath(gj_path)}")
    print(f"  {os.path.abspath(mf_path)}")


if __name__ == "__main__":
    main()
