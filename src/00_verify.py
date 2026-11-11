# -*- coding: utf-8 -*-
"""
Step 0 - verify every asset loads and carries the bands we rely on.

Run this before anything else.  Thirty seconds here saves a day of a failed
extraction, which is exactly what it caught the last time.
"""
import os, sys
import ee
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
import cl_config as C

load_dotenv()
ee.Initialize(project=os.getenv("EE_PROJECT_ID"))

AOI = ee.Geometry.Rectangle([79.50, 21.50, 80.00, 22.00])   # a forest test box
TEST_START, TEST_END = "2023-01-01", "2023-02-01"

NEEDED_BANDS = {
    "s2":     ["B3", "B4", "B8", "B12", "SCL"],
    "dw":     ["trees", "water", "built"],
    "chirps": ["precipitation"],
    "era5":   ["temperature_2m", "volumetric_soil_water_layer_1",
               "u_component_of_wind_10m", "v_component_of_wind_10m"],
    "firms":  ["T21"],
}

print("=" * 68)
print("IMAGE COLLECTIONS")
print("=" * 68)
ok = True
for key in ("s2", "dw", "chirps", "era5", "firms"):
    path = C.ASSETS[key]
    try:
        col = ee.ImageCollection(path).filterBounds(AOI).filterDate(TEST_START, TEST_END)
        n = col.size().getInfo()
        bands = col.first().bandNames().getInfo()
        missing = [b for b in NEEDED_BANDS[key] if b not in bands]
        status = "PASS" if (n > 0 and not missing) else "CHECK"
        if missing or n == 0:
            ok = False
        print(f"  {status}  {key:7s} {n:5d} images   {path}")
        if missing:
            print(f"         MISSING BANDS: {missing}")
            print(f"         available: {bands[:14]}")
    except Exception as e:
        ok = False
        print(f"  FAIL  {key:7s} {path}\n         {str(e)[:150]}")

print()
print("=" * 68)
print("SINGLE IMAGES")
print("=" * 68)
for key, need in (("hansen", ["treecover2000", "lossyear"]), ("srtm", ["elevation"])):
    path = C.ASSETS[key]
    try:
        bands = ee.Image(path).bandNames().getInfo()
        missing = [b for b in need if b not in bands]
        if missing:
            ok = False
            print(f"  CHECK {key:7s} MISSING {missing}; available {bands}")
        else:
            print(f"  PASS  {key:7s} {path}")
    except Exception as e:
        ok = False
        print(f"  FAIL  {key:7s} {path}\n         {str(e)[:150]}")

print()
print("=" * 68)
print("SAMPLING REGIONS")
print("=" * 68)
for name, country, eco, box in C.REGIONS:
    g = ee.Geometry.Rectangle(box)
    try:
        n = (ee.ImageCollection(C.ASSETS["s2"])
             .filterBounds(g).filterDate("2019-01-01", "2019-04-01").size().getInfo())
        area = g.area(maxError=1000).divide(1e6).getInfo()
        flag = "ok " if n > 0 else "EMPTY"
        print(f"  {flag} {name:20s} {country:10s} {eco:9s} {area:7.0f} km2   {n:4d} S2 scenes")
        if n == 0:
            ok = False
    except Exception as e:
        ok = False
        print(f"  FAIL {name:20s} {str(e)[:90]}")

print()
print("=" * 68)
print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED - fix before extracting")
print("=" * 68)
sys.exit(0 if ok else 1)
