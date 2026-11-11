# Task Brief — Mangrove Indicators
**Owner: Mavya**

---

# 1. Why this matters

Our project's central claim is that **one framework can monitor different
ecosystem types, because indicators are configured per type rather than
hardcoded**. Every competing system we found — ESA CarbonTrust, Kanop,
CarbonEagle — is forest-only.

Mangroves are what makes that claim real. Your job is to establish, with
published evidence, **exactly how mangrove monitoring must differ from
forest monitoring**.

You are not writing a literature review. **You are filling in a config file
and justifying a design decision.**

---

# 2. Context — start from what we already found

We ran this ourselves. Your research should explain these results and tell
us how to handle them.

**Finding 1 — a plain rectangle measures water, not trees.**
We measured NDVI over coastal boxes at Sundarbans and Coringa and got
**0.08 to 0.30**. Real mangrove forest should sit around 0.6–0.8. Checking
the pixel distribution showed more than half of each box was open water or
mudflat, with negative NDVI values. After masking to pixels whose 2019
median NDVI exceeded 0.6, values rose to **0.6–0.8**, giving 35,171 ha at
Sundarbans and 9,971 ha at Coringa.

**Finding 2 — the seasonal swing is enormous.**
Sundarbans monthly NDVI runs about **0.78 in January down to 0.44 in
May–June**, every single year, then recovers by November. That swing is far
larger than any damage signal we are trying to detect.

**Finding 3 — Cyclone Amphan is invisible.**
Amphan hit in May 2020. There is **no drop** in our monthly NDVI. June and
July 2020 sit at or above other years, and the lowest point in the whole
three-year record is June 2021 — a year with no cyclone at all.

**A recent change you need to know:** we tested whether GLAD and RADD radar
forest-alert products could date mangrove disturbances to a month. GLAD only
covers 2025–2026, and RADD barely reaches India. So mangrove disturbance
labels will rely mostly on **Hansen annual forest loss**, which is coarse.
That makes it more important to know **what signature mangrove loss leaves
in the satellite indicators themselves**.

---

# 3. What we need — six questions

Each needs **a number, a place and a method** where possible.

## Q1. How do studies define where mangrove actually is? ← **highest priority**

We need an authoritative mangrove extent layer.

- Look up **Global Mangrove Watch (GMW)**. What versions exist, and is any
  of them usable in Google Earth Engine? Find the asset path if you can.
- *(Note: we tried `JAXA/ALOS/PALSAR/YEARLY/FNF4` — that is radar
  forest/non-forest, not mangrove. Not a substitute.)*
- If GMW isn't usable, what NDVI or other cut-off do published studies use
  when building their own mangrove mask? We used 0.6. Is that defensible?

## Q2. How do studies handle the tide?

This is the central mangrove problem. At high tide, water sits under the
canopy and drags NDVI down even when the trees are perfectly healthy.

Look for: tidal correction methods, tide-aware image selection, or use of a
water index alongside NDVI. What do papers actually do in practice?

## Q3. Is NDVI even the right index for mangroves?

Check the alternatives and whether any outperforms NDVI:

- **NDWI / MNDWI** — water indices
- **SAVI** — soil-adjusted, for sparse canopy over bright substrate
- **Sentinel-1 radar** — sees through cloud and works at night

Radar may matter a lot for us, since the monsoon destroys optical coverage
for months.

## Q4. How is aquaculture conversion detected? ← **highest priority**

Conversion to shrimp and fish ponds is the dominant global threat to
mangroves, and unlike a cyclone it is permanent — which makes it a far
better test of carbon permanence.

Find the signature studies use. We expect NDVI falling while a water index
rises, in geometric pond-shaped patches. Get numbers if you can: what change
in what index, over what period?

## Q5. Why didn't Amphan show, and how do studies detect cyclone damage?

Look for papers on Amphan and the Sundarbans specifically. Did they need
radar, higher resolution, or before/after image pairs rather than monthly
averages? Does mangrove cyclone damage show up in greenness at all, or
mainly as structural change?

## Q6. What baseline do mangrove studies use?

Given the swing we measured, how many years of history do studies use to
define "normal" for a given calendar month? Is a per-month baseline standard
practice, or do they do something else?

---

# 4. How to search

Use **Google Scholar** (`scholar.google.com`), "since 2019" filter.

```
mangrove change detection Sentinel-2 NDVI NDWI
Global Mangrove Watch dataset Google Earth Engine
tidal influence mangrove NDVI correction
mangrove aquaculture conversion detection remote sensing
Cyclone Amphan Sundarbans mangrove damage satellite
Sentinel-1 SAR mangrove monitoring
mangrove loss India Coringa Godavari remote sensing
```

> **Always include "remote sensing", "satellite" or "Sentinel" in every
> search.** Without it you land in ecology, fisheries and pollution
> journals. We already wasted time on a paper about heavy metals in mangrove
> crabs that matched purely on the word "indicator".

**Target: 4–6 genuinely useful papers.**

---

# 5. What a good finding looks like

❌ "NDWI is used to study mangroves."

✅ "Study X (Mekong Delta, Sentinel-2, 2016–2020) detected pond conversion
where NDVI fell below 0.3 while MNDWI rose above 0.2 within 12 months,
validated against 180 field points, 89% accuracy."

---

# 6. Deliverable 1 — the paper table

Same columns as Pranathi's, so the two merge cleanly.

| Field | What to write |
|---|---|
| Citation | Author, year, title, journal, link |
| Ecosystem and place | e.g. mangrove, Mekong Delta |
| Data used | e.g. Sentinel-2, Sentinel-1, GMW |
| Indicators used | e.g. NDVI, MNDWI, VH backscatter |
| **Threshold** | the actual number, with units |
| Baseline method | what they compared against |
| How they defined damage | field survey, GMW change layer, visual |
| Accuracy reported | e.g. 89%, or F1 0.73 |
| **Weakness** | what the authors say doesn't work well |
| Use for us? | Yes / Partly / No, plus one line why |

---

# 7. Deliverable 2 — draft config

Draft `config/mangrove.yaml`, every weight commented with its source:

```yaml
type_id: mangrove
display_name: Mangrove / Coastal Wetland

indicators:
  - id: ndvi_anom
    weight: 0.20        # lower than forest — [Author Year]
    direction: negative

  - id: ndwi_anom
    weight: 0.15        # rising water + falling NDVI = conversion [Author Year]
    direction: positive

  - id: tree_prob_delta_12m
    weight: 0.25
    direction: negative

  - id: loss_ha_cumulative
    weight: 0.25
    direction: positive

  - id: wind_max_ms
    weight: 0.10        # cyclone exposure — [Author Year]
    direction: positive

  - id: fire_count_5km_90d
    weight: 0.05        # low but not zero — mangroves rarely burn
    direction: positive

mask:
  source: ""            # GMW asset path, or our NDVI rule — fill from Q1
  ndvi_threshold: 0.6   # confirm or correct from Q1
  baseline_year: 2019

baseline:
  method: per_site_monthly_median
  years: 5              # confirm from Q6

preprocessing:
  tide_handling: ""     # fill from Q2
  cloud_threshold: 40
```

Weights must sum to 1.0. Mark anything the literature doesn't support as
`# UNSUPPORTED — needs sensitivity analysis`.

---

# 8. Deliverable 3 — the difference statement ← **most valuable output**

Half a page, in plain prose, answering:

> **How must mangrove monitoring differ from forest monitoring, and why?**

Be specific. Name the indicator differences, the masking requirement, the
tidal problem, and the different threat profile (cyclones, erosion and pond
conversion versus fire, drought and clearing).

This paragraph is the evidence for our project's main claim — that one
framework needs different settings per ecosystem. It will go almost verbatim
into the report and the paper. Make it concrete, and cite it.

---

# 9. Done when

- [ ] 4–6 useful papers in the table, all columns filled
- [ ] **Q1 answered** — we know how to define mangrove extent, ideally with
      a usable Earth Engine asset path
- [ ] **Q4 answered** — we know the conversion signature
- [ ] At least **two concrete numeric thresholds** found and cited
- [ ] `config/mangrove.yaml` drafted with sources
- [ ] The difference statement written
- [ ] Pushed and a pull request opened into `dev`

---

# 10. Where to put it

```bash
git checkout dev
git pull
git checkout feature_Mavya
git merge dev
```

Files:
- `docs/research_mangrove.md` — table, summary, difference statement
- `config/mangrove.yaml` — draft config

```bash
git add docs/ config/
git commit -m "Add mangrove indicator research and draft config"
git push
```

Then open a pull request into `dev` and tell the group.

---

# 11. Traps to avoid

- **The keyword trap is worse for mangroves.** "Mangrove" plus "indicator"
  returns ecology, fisheries and pollution papers. Always add a remote
  sensing term.
- **Don't force a paper to be useful.** "Read, not useful" is a valid row.
- **If a study is from Indonesia or Vietnam, it still counts.** Most mangrove
  remote-sensing work is from Southeast Asia. Note that the site differs from
  ours and use it anyway.
- **A negative finding is a real finding.** If the literature says monthly
  NDVI cannot detect cyclone damage, that explains our Amphan result and
  belongs in the report.
