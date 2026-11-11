# -*- coding: utf-8 -*-
"""Shared Earth Engine helpers: cloud masking, indices, eligibility masks."""
import os, sys, time
import ee

sys.path.insert(0, os.path.dirname(__file__))
import cl_config as C


# ------------------------------------------------------------------ basics
def init():
    from dotenv import load_dotenv
    load_dotenv()
    pid = os.getenv("EE_PROJECT_ID")
    if not pid:
        raise SystemExit("EE_PROJECT_ID is not set in .env")
    ee.Initialize(project=pid)
    return pid


def retry(fn, what=""):
    """Earth Engine throttles under load; back off and try again."""
    last = None
    for attempt in range(C.MAX_RETRIES):
        try:
            return fn()
        except Exception as e:
            last = e
            if attempt < C.MAX_RETRIES - 1:
                wait = C.RETRY_WAIT_S * (attempt + 1)
                print(f"      retry {attempt+1}/{C.MAX_RETRIES-1} in {wait}s  ({what}) "
                      f"{str(e)[:70]}")
                time.sleep(wait)
    raise last


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


# ------------------------------------------------------------- Sentinel-2
def mask_clouds(img):
    """Drop cloud shadow, medium/high cloud and cirrus using the scene class band."""
    scl = img.select("SCL")
    clear = (scl.neq(3)        # cloud shadow
             .And(scl.neq(8))  # cloud, medium probability
             .And(scl.neq(9))  # cloud, high probability
             .And(scl.neq(10)))# cirrus
    return img.updateMask(clear)


def s2_indices(img):
    """Per-pixel indices, computed BEFORE compositing (a ratio of means is wrong)."""
    ndvi = img.normalizedDifference(["B8", "B4"]).rename("ndvi")
    ndwi = img.normalizedDifference(["B3", "B8"]).rename("ndwi")
    nbr  = img.normalizedDifference(["B8", "B12"]).rename("nbr")
    return ee.Image.cat([ndvi, ndwi, nbr]).copyProperties(img, ["system:time_start"])


def s2_collection(geom, start, end):
    return (ee.ImageCollection(C.ASSETS["s2"])
            .filterBounds(geom)
            .filterDate(start, end)
            .map(mask_clouds)
            .map(s2_indices))


# --------------------------------------------------------- eligibility masks
def forest_mask():
    """Hansen canopy cover above threshold AND Dynamic World tree probability in 2019."""
    hansen = ee.Image(C.ASSETS["hansen"])
    cover = hansen.select("treecover2000").gte(C.FOREST_TREECOVER_MIN)
    treeprob = (ee.ImageCollection(C.ASSETS["dw"])
                .filterDate("2019-01-01", "2020-01-01")
                .select("trees").median())
    return cover.And(treeprob.gte(C.FOREST_TREEPROB_MIN)).rename("eligible")


def mangrove_mask(geom):
    """
    Dense evergreen canopy at low elevation.

    This is the fallback validated in our own work: an unmasked coastal
    polygon measures water rather than canopy, and a median (not minimum)
    over the reference year is what separates the two populations.
    """
    typical = s2_collection(geom, "2019-01-01", "2020-01-01").select("ndvi").median()
    low = ee.Image(C.ASSETS["srtm"]).select("elevation").lte(C.MANGROVE_ELEV_MAX)
    return typical.gt(C.MANGROVE_NDVI_MIN).And(low).rename("eligible")


def eligibility(ecosystem, geom):
    return forest_mask() if ecosystem == "forest" else mangrove_mask(geom)


# ------------------------------------------------------------------ Hansen
def hansen_loss_ha_through(year):
    """
    Cumulative Hansen loss area, in hectares, for loss years up to and
    including `year`.  Used with year = Y-1 so the feature can never reach
    into the label's forward window.
    """
    hansen = ee.Image(C.ASSETS["hansen"])
    code = year - 2000                      # lossyear is encoded 1 = 2001
    lost = hansen.select("lossyear").lte(code).And(hansen.select("lossyear").gt(0))
    return lost.multiply(ee.Image.pixelArea()).divide(1e4).rename("loss_ha")


def hansen_loss_ha_in(year):
    """Hansen loss area for a single year."""
    hansen = ee.Image(C.ASSETS["hansen"])
    code = year - 2000
    lost = hansen.select("lossyear").eq(code)
    return lost.multiply(ee.Image.pixelArea()).divide(1e4).rename("loss_ha")
