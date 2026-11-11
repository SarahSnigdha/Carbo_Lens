# Task Brief — Forest Indicators
**Owner: Pranathi**

---

# 1. Why this matters

Our system will tell a user a forest project is at LOW, MEDIUM or HIGH risk.
The panel's standing question is **"where did those numbers come from?"**

"We chose them" is not an answer that survives. Your job is to find numbers
that came from published research, so every threshold and weight in our
config file has a citation behind it.

You are not writing a literature review. **You are filling in a config file.**

---

# 2. Context — what we already know from our own data

Read this first; it shapes what you're looking for.

**Our forest test site is Similipal, Odisha** — dry deciduous forest, with
confirmed fires in March 2021 and March 2018.

We counted NASA FIRMS fire detections inside Similipal for March of each
year:

| 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 |
|---|---|---|---|---|---|---|
| 139 | 730 | 17 | 18 | **1,013** | 136 | 469 |

Two things follow from that table. Fire activity varies enormously year to
year, so a fixed threshold is useless and everything must be measured
against a site's own history. And March 2021 was roughly seven times a
normal March, which is the event we will test our system against.

**A recent change you need to know:** we checked whether GLAD and RADD
forest-alert products could date disturbances to a month. GLAD only covers
2025–2026, and RADD barely reaches India. So **FIRMS fire detections are now
our primary dated trigger for forest labels.** That makes your work more
important, not less: what we most need to know is **what conditions precede
a fire**, because that is what the model will learn to detect.

---

# 3. What we need — six questions

Each needs **a number, a place and a method**. If a paper gives you no
number you can use, record it as "read, not useful" and move on.

## Q1. Which index best detects fire damage?

NDVI is the obvious choice, but burn studies usually prefer **NBR**
(Normalized Burn Ratio) and **dNBR** (NBR before minus NBR after).

Find out: does NBR outperform NDVI for burn detection, and by how much? If
clearly yes, we should add NBR to our indicator set.

## Q2. What size of change counts as damage?

This is the single most valuable number you can bring back. Burn-severity
studies classify severity into bands with specific cut-offs — low, moderate,
high. Write down the actual values and which index they apply to.

Also look for: what NDVI drop, measured against a baseline, has been used to
flag disturbance?

## Q3. How long does recovery take?

If dry deciduous forest regains its greenness within one season, a drop
alone does not mean carbon was lost. This decides how long we keep a project
flagged after an event.

## Q4. Which drought measure, over what window?

SPI or SPEI? And SPI-1, SPI-3, SPI-6 or SPI-12? Find which window best
relates to fire risk in Indian or similar dry forests.

*(Note: we fit SPI against a 30-year CHIRPS climatology, 1991–2020, so
don't worry about baseline length — just the window.)*

## Q5. What conditions come before a fire? ← **highest priority**

This is the heart of early warning, and it is now our main label. Look for
fire-risk or fire-danger modelling studies:

- How many consecutive dry days raise risk measurably?
- What temperature or humidity thresholds appear?
- How far in advance is elevated risk detectable?
- Which variables do these models actually use?

## Q6. How do studies separate normal dry-season leaf-fall from real damage?

Similipal sheds leaves every dry season. Its NDVI falls naturally. How do
published studies avoid false alarms from that?

---

# 4. How to search

Use **Google Scholar** (`scholar.google.com`). Set "since 2019" in the left
filter — Sentinel-2 only became widely used after 2017.

Start with these:

```
forest fire severity dNBR Sentinel-2 India
burn severity thresholds dry deciduous forest
NDVI anomaly forest disturbance detection threshold
SPI drought index forest fire risk India
forest fire danger prediction machine learning India
post-fire recovery NDVI dry deciduous forest
Similipal forest fire remote sensing
```

> **The word that unlocks this literature is "severity", not "monitoring".**
> Burn-severity papers are full of the numeric cut-offs we need.

**Tips:** click "All versions" under a result to find a free PDF. MDPI
*Remote Sensing* and *Forests* are fully open access and strong in this area.
Never pay for a paper. If only the abstract is free, the number you need is
often in it — cite it as an abstract.

**Target: 4–6 genuinely useful papers.** Two with solid numbers beat ten
vague ones.

---

# 5. What a good finding looks like

❌ "NDVI is commonly used to monitor forest health."

✅ "Study X (dry deciduous forest, Odisha, Sentinel-2) found dNBR above 0.27
corresponded to moderate burn severity, validated against field plots, with
82% accuracy."

The difference: a number, a place, a method.

---

# 6. Deliverable 1 — the paper table

One row per paper. Use exactly these columns so your table and Mavya's merge
cleanly.

| Field | What to write |
|---|---|
| Citation | Author, year, title, journal, link |
| Ecosystem and place | e.g. dry deciduous forest, Odisha |
| Data used | e.g. Sentinel-2, MODIS, ERA5 |
| Indicators used | e.g. NDVI, NBR, SPI-3 |
| **Threshold** | the actual number, with units |
| Baseline method | what they compared against |
| How they defined damage | burned-area map, field survey, Hansen loss |
| Accuracy reported | e.g. 82%, or F1 0.71 |
| **Weakness** | what the authors say doesn't work well |
| Use for us? | Yes / Partly / No, plus one line why |

> The **Weakness** column matters more than it looks. Our report needs a
> limitations section, and examiners respect a team that knows what its
> method cannot do.

---

# 7. Deliverable 2 — draft config

Convert your findings into a draft of `config/forest.yaml`. Every weight
gets a comment citing its source. Rough shape:

```yaml
type_id: forest
display_name: Forest Restoration / Afforestation

indicators:
  - id: ndvi_anom
    weight: 0.30        # [Author Year] found drop > X flagged disturbance
    direction: negative

  - id: nbr_anom
    weight: 0.00        # set > 0 only if Q1 shows NBR beats NDVI
    direction: negative

  - id: fire_count_5km_90d
    weight: 0.25        # [Author Year]
    direction: positive

  - id: spi_3
    weight: 0.15        # window chosen per Q4 — [Author Year]
    direction: negative

  - id: consec_dry_days
    weight: 0.10        # threshold from Q5 — [Author Year]
    direction: positive

  - id: temp_anom_c
    weight: 0.05
    direction: positive

  - id: loss_ha_cumulative
    weight: 0.15
    direction: positive

baseline:
  method: per_site_monthly_median
  years: 5
  exclude_years: [2021]   # Similipal: fire year distorts its own baseline

recovery_window_months: 0   # fill from Q3

preprocessing:
  seasonal_leaf_fall_handling: ""   # fill from Q6
```

Weights must sum to 1.0. If the literature doesn't settle a weight, put your
best estimate and mark it `# UNSUPPORTED — needs sensitivity analysis`.

---

# 8. Deliverable 3 — one-page summary

Half a page of prose answering:

- Which indicators we should use for forest, and why
- What threshold defines "disturbed" for a forest project
- What the literature says we **cannot** reliably detect

---

# 9. Done when

- [ ] 4–6 useful papers in the table, all columns filled
- [ ] At least **three concrete numeric thresholds** found and cited
- [ ] Q5 answered — we know what precedes a fire
- [ ] `config/forest.yaml` drafted, every weight commented with a source
- [ ] One-page summary written
- [ ] Pushed and a pull request opened into `dev`

---

# 10. Where to put it

```bash
git checkout dev
git pull
git checkout feature_Pranathi
git merge dev
```

Files:
- `docs/research_forest.md` — table plus summary
- `config/forest.yaml` — draft config

```bash
git add docs/ config/
git commit -m "Add forest indicator research and draft config"
git push
```

Then open a pull request into `dev` on GitHub and tell the group.

---

# 11. Traps to avoid

- **Keyword traps.** Papers can match on words and be irrelevant. One we
  already hit: a mangrove "bioindicator" paper turned out to be about heavy
  metal pollution measured through crabs and molluscs, with no satellite
  data at all. Check it is remote sensing before reading further.
- **Reviews give no numbers.** They summarise other studies. Useful for
  framing, weak for thresholds. Prefer papers with their own results.
- **Don't force a paper to be useful.** "Read, not useful" is a valid row and
  saves everyone time.
- **Papers disagreeing is good.** Record both — disagreement justifies
  testing a range of thresholds in our sensitivity analysis.
