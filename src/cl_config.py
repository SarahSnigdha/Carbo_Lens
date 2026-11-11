# -*- coding: utf-8 -*-
"""
Carbo_Lens — sampling and extraction configuration.

The pilot and the full dataset use the SAME code path and the SAME random
seed.  Candidate patches are ranked once, deterministically, and a profile
simply takes the first N of that ranking.  The pilot sample is therefore a
strict subset of the full sample: enlarging the profile adds patches, it
never reshuffles the ones already extracted.
"""

SEED = 42

# ----------------------------------------------------------------- profiles
PROFILES = {
    # one focused day of work
    "pilot": {
        "forest_disturbed":    20,
        "forest_undisturbed":  20,
        "mangrove_disturbed":  10,
        "mangrove_undisturbed": 15,
    },
    # intermediate, if you want something between the two
    "medium": {
        "forest_disturbed":    80,
        "forest_undisturbed":  80,
        "mangrove_disturbed":  35,
        "mangrove_undisturbed": 45,
    },
    # the target described in the dataset specification
    "full": {
        "forest_disturbed":    260,
        "forest_undisturbed":  240,
        "mangrove_disturbed":  110,
        "mangrove_undisturbed": 130,
    },
}

# ----------------------------------------------------------------- geometry
PATCH_SIDE_M    = 1000     # 1 km x 1 km  = 100 ha
MIN_SPACING_M   = 2000     # between patch centres
MIN_ELIGIBLE    = 0.80     # fraction of the patch that must be eligible

# Demonstration sites are held out of training entirely.
EXCLUDE_SITES = [
    # name,        lon,    lat,   buffer km
    ("Similipal",  86.35, 21.80, 25),
    ("Coringa",    82.32, 16.85, 25),
    ("Sundarbans", 88.75, 21.85, 25),   # used in the report's figures
]

# ----------------------------------------------------------------- time
BASELINE_START  = "2019-01-01"
BASELINE_END    = "2022-01-01"    # baseline window: 2019-2021
MODEL_START     = "2022-01-01"
MODEL_END       = "2025-10-01"    # modelling window ends 2025-09 (tail censoring)
LABEL_END       = "2026-01-01"    # trigger data pulled past the window to confirm zeros

EXTRACT_START   = BASELINE_START
EXTRACT_END     = MODEL_END       # raw extraction covers baseline + modelling

# ----------------------------------------------------------------- labels
LABEL_HORIZON_MONTHS = 3
FIRE_TRIGGER_COUNT   = 3          # detections inside the patch in a month
DISTURBED_LOSS_HA    = 1.0        # Hansen loss in the modelling window
DISTURBED_FIRE_COUNT = 5          # FIRMS detections in the modelling window

# ----------------------------------------------------------------- masks
FOREST_TREECOVER_MIN = 30         # Hansen treecover2000, per cent
FOREST_TREEPROB_MIN  = 0.50       # Dynamic World tree probability, 2019 median
MANGROVE_NDVI_MIN    = 0.60       # validated against our own pixel distributions
MANGROVE_ELEV_MAX    = 15         # metres, SRTM

# ----------------------------------------------------------------- regions
# Sampling regions, named so the manifest records exactly where patches came
# from.  Adding a region is how the sample is widened geographically.
REGIONS = [
    # (name, country, ecosystem, [west, south, east, north])
    ("Kanha-Pench",      "India",      "forest",   [79.50, 21.50, 81.50, 23.00]),
    ("Western Ghats",    "India",      "forest",   [74.50, 12.50, 76.00, 14.00]),
    ("Central Kalimantan","Indonesia", "forest",   [112.50, -2.50, 114.50, -0.50]),
    ("Para",             "Brazil",     "forest",   [-55.00, -5.00, -53.00, -3.00]),
    ("Southern Tanzania","Tanzania",   "forest",   [35.00, -9.50, 37.00, -7.50]),

    ("Bhitarkanika",     "India",      "mangrove", [86.70, 20.55, 87.15, 20.90]),
    ("Pichavaram",       "India",      "mangrove", [79.45, 10.25, 79.95, 10.65]),
    ("East Sumatra",     "Indonesia",  "mangrove", [103.40, -1.10, 104.60, 0.10]),
    ("Mekong Delta",     "Vietnam",    "mangrove", [104.90, 8.55, 106.30, 9.70]),
    ("Rufiji Delta",     "Tanzania",   "mangrove", [38.95, -8.25, 39.70, -7.55]),
]

# Candidate points drawn per region before eligibility filtering.
CANDIDATES_PER_REGION = 400

# ----------------------------------------------------------------- splits
# Country-level holdout.  Assigned before extraction and sealed.
SPLIT_BY_COUNTRY = {
    "India":     "train",
    "Indonesia": "train",
    "Tanzania":  "validate",
    "Brazil":    "test",
    "Vietnam":   "test",
}

# ----------------------------------------------------------------- assets
ASSETS = {
    "s2":       "COPERNICUS/S2_SR_HARMONIZED",
    "dw":       "GOOGLE/DYNAMICWORLD/V1",
    "chirps":   "UCSB-CHG/CHIRPS/DAILY",
    "era5":     "ECMWF/ERA5_LAND/MONTHLY_AGGR",
    "firms":    "FIRMS",
    "hansen":   "UMD/hansen/global_forest_change_2025_v1_13",
    "srtm":     "USGS/SRTMGL1_003",
}

# ----------------------------------------------------------------- runtime
CHUNK_SIZE   = 40     # patches per reduceRegions call; lower if EE complains
MAX_RETRIES  = 3
RETRY_WAIT_S = 8
