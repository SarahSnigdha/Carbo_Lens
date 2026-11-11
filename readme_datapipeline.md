# Carbo_Lens — training dataset pipeline

Builds the training table from Earth Engine. The **pilot** and the **full**
sample run through the same code with the same random seed, so the pilot is a
strict subset: enlarging the profile *adds* patches and never reshuffles the
ones already extracted.

---

## Runbook

```bash
cd ~/projects/Carbo_Lens
source venv/Scripts/activate          # Git Bash on Windows
pip install pandas numpy scikit-learn python-dotenv
```

| # | Command | Time | What it does |
|---|---|---|---|
| 0 | `python src/00_verify.py` | 1 min | Checks every asset and band loads. **Run first.** |
| 1 | `python src/01_make_patches.py --profile pilot` | 10–20 min | Samples patches, writes `data/patches.geojson` + `manifest.json` |
| 2 | `python src/02_extract.py --months 3` | 5 min | **Smoke test** on three months |
| 2 | `python src/02_extract.py` | 45–90 min | Full extraction, resumable |
| 3 | `python src/03_assemble.py` | 10 sec | Baselines, anomalies, labels, audit |
| 4 | `python src/04_smoke_train.py` | 1 min | Confirms the table is trainable |

Step 2 writes one CSV per month and **skips months already on disk**, so a
crash or a Ctrl-C costs you one month, not the run. Just start it again.

---

## Scaling up

Everything is driven by `src/cl_config.py`.

```bash
python src/01_make_patches.py --profile medium   # 240 patches
python src/01_make_patches.py --profile full     # 740 patches
python src/02_extract.py                         # re-extracts only new months
```

Because patch ids come from a fixed, seeded ranking, `FOR_0001` is the same
square in every profile. To widen the sample geographically, add rows to
`REGIONS` in the config — that is the intended extension point.

Two things to change when you move past the pilot:

- **`CHUNK_SIZE`** — lower it to 20 if Earth Engine returns concurrency errors.
- **`rain_anom_6m`** is a rainfall-deficit proxy. Proper SPI needs a 30-year
  CHIRPS climatology and is a follow-up, not a pilot task.

---

## What the pipeline guarantees

These are enforced in code, not left to discipline:

| Guarantee | Where |
|---|---|
| Demonstration sites excluded with a 25 km buffer | `01`, `EXCLUDE_SITES` |
| Patches at least 2 km apart, 80% eligible | `01` |
| Country-level split assigned *before* extraction and sealed | `01`, `SPLIT_BY_COUNTRY` |
| Cumulative loss stops at the previous year — no leakage | `02`, `hansen_loss_ha_through(y-1)` |
| An absent data feed is flagged, never read as zero | `02`, `s2_data` / `dw_data` / `fire_data` |
| Labels come from dated fire triggers; Hansen only corroborates | `03` |
| Last 3 months per patch marked unconfirmed (tail censoring) | `03` |
| Cross-validation grouped by patch, never by row | `04`, `GroupKFold` |

Step 3 runs four audits and refuses to pass on leakage. The leakage check was
tested by deliberately injecting leakage into 13 rows; it caught all 13.

---

## Outputs

```
data/
  patches.geojson          the sample, with stratum and split per patch
  manifest.json            seed and every parameter — regenerates the sample
  raw/features_YYYY-MM.csv one file per month (resumable)
  training_data.csv        the assembled table
```

`data/` is gitignored. **Commit the scripts and `manifest.json`, not the CSVs** —
the manifest plus the seed regenerates the identical sample from a clean clone.

---

## A warning about pilot numbers

`04_smoke_train.py` prints precision and recall. On a 65-patch pilot the
positive count is in the dozens and those numbers are noise. They confirm the
pipeline runs; they are **not results** and should not be shown as such.
Reportable metrics come from the full sample against the sealed test countries.
