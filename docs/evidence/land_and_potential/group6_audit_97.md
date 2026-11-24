# Group 6 audit (COMMAND 97): land eligibility in F3

Date: 2026-11-05. Read-only audit; no code, config or record was edited. Specification: `docs/thesis/methods/group6_land_eligibility.tex`
(normative) and `docs/thesis/theory/ch2_land_eligibility_constraints.tex`. Current state: `config/experiments.yaml` `land_availability`,
`src/geofrea/land_eligibility/`, `docs/phases/F3_land_eligibility.md` (D-F3-001 to D-F3-024).

## 1. Current values and sources, old against new

Current scenarios (D-F3-007, `scenarios.py`): a parameter varies only if its range has status `sourced`; everything else is held at the central value.

| Criterion | Tech | Now (restrictive / central / permissive) | Source and tier now | New (restrictive / central / permissive), COMMAND 97 |
|---|---|---|---|---|
| Rivers (E3) | both | setback 1.0 / 0.5 / 0.25 km from the line, every HydroRIVERS stream (`riparian_min_discharge_m3s` 0, held central: unsourced) | MAPRE Table B1, McKenna 2022; central 0.5 km is "an earlier unverified value"; no tier field | corridor `W/2 + B_c(W)`, `W = 7.2 Q^b`, b = 0.52 / 0.50 / 0.48; B_c by country (BRA 5 classes, equal in all scenarios; PRT 30 / 10-or-30 / 10; IND 200 / 100 / 30); Andreadis 2013, Lei 54/2005, Lei 12.651/2012; PRT central and IND Tier 3 |
| Settlements (E6) | both | population density > 200 persons/km2 (E6 is 0 or 1 per pixel), same in all three scenarios | project value, Tier 3 (L-020, OQ-047); range 150-300 unsourced, held | GHS-SMOD L2 >= 13 mask, setback PV 1000 / 500 / 0 m, wind 1000 / 800 / 500 m; density kept only as sensitivity `population_density_200` |
| Slope (E4) | PV | 10 deg in all three (range 10-15 deg is a lead, held) | MAPRE, Ryberg 2017 | 3 / 5 / 10 % (1.72 / 2.86 / 5.71 deg) |
| Slope (E4) | wind | 10.2 / 16.7 / 30 deg (18 / 30 / 58 %) | ENSPRESO 2, Ryberg 2020, McKenna 2022 | 10 / 20 / 30 % (5.71 / 11.31 / 16.70 deg) |
| Elevation | wind | 3,000 m in all three scenarios; none for PV | none (Tier 3, `source: null`, OQ-058, L-025) | 2,000 / 3,000 / none; central stays Tier 3, restrictive and permissive sourced to `epg2024renewland` per the `.tex` |
| Minimum area | PV | cell filter `min_eligible_area_km2` 0.1 km2 on the 0.05 deg cell, all scenarios | ENSPRESO 2 by analogy; `range_pending` | cluster (8-connected 0.01 deg pixels with fraction > 0): none / >= 1 km2 / >= `P_ref/PD_PV` |
| Minimum area | wind | same 0.1 km2 cell filter | ENSPRESO 2 | none / pixel < 10 % dropped / pixel >= 10 % and cluster >= `P_ref/PD_wind` |

Order of the new scenarios in the `.tex` tables is restrictive / central / permissive; the command lists permissive first for b, B_c, setbacks, slope
and elevation. Only the order of writing differs, every value agrees between the command and the `.tex` (checked cell by cell).

Not changed by Group 6 and kept: E1 protected areas (all designations), E2 lakes, E5 land-cover classes (PV excludes tree cover and cropland, wind
tree cover), the three-scenario structure and the `restrictive <= central <= permissive` check per cell.

## 2. Where each criterion enters

- Configuration: `config/experiments.yaml` -> `config_models/land_availability.py` (`Ranged`, `ParameterSet`, `nominal_set`) -> `scenarios.py`
  (`scenario_sets`: a parameter varies only when `status == sourced`; `_PERMISSIVE_IS_HIGH` lists four parameters).
- Pixel fractions (0.01 deg): `eligibility.py:eligible_fraction` = valid x (1-E1)...(1-E6), independent product. E1/E2/E3 from `fractions.py`
  (10 x 10 sub-pixels), E4 from `_steep_share` (slope bins), E5 from land-cover class counts, E6 from `population_count / pixel_area_km2 > max`.
- Stripes (D-F3-024): `windows.py:ScenarioStripes._get` builds the six exclusions of a window of rows and `aggregate_to_cells` sums the 5 x 5 cells
  (a cell takes its pixels from one stripe). The scenario sets feed `riparian_shares` and `slope_steep_share` per window.
- Cells: `cells.py:candidate_cells` applies `min_eligible_area_km2`; `scenarios.py:candidate_exclusion_reasons` applies `elevation_max` and
  `missing_elevation`; `candidate_stability` repeats both across scenarios.
- Rivers: HydroRIVERS lines clipped per country; `river_fractions(lines, transform, shape, setbacks, discharges)` burns lines `all_touched` and takes a
  geodesic distance transform; the shares are cached once per (discharge, setback) pair and read back through `NpyRows`. `DIS_AV_CMS` is used only as a
  threshold today (`lines[lines.DIS_AV_CMS >= q]`).

## 3. Slope resolution

Native. `grid_alignment/raster_alignment.py:glo30_aligned_outputs` differentiates the 30 m GLO-30 samples with WGS84 geodesic spacing (central
differences) and counts each sample into the 0.01 deg pixel that contains its centre, in 1-degree bins (41 bins, last open-ended); E4 is the share of
the pixel's samples above the threshold (D-F2a-016, D-F3-005). The 0.01 deg slope raster is a mean and is not used for E4. So the item-3 requirement
(native resolution, converted to pixel fraction) already holds; no method change is needed.

Consequence of the percent thresholds: `_steep_share` takes thresholds in degrees and interpolates inside a 1-degree bin assuming a uniform
distribution. The new thresholds are `atan(p/100)` = 1.718 / 2.862 / 5.711 deg (PV) and 5.711 / 11.310 / 16.699 deg (wind): the bin interpolation is
exact for integer degrees and approximate otherwise (central PV 5 % = 2.862 deg sits inside bin 2). Within the 0-40 deg resolvable range. Reported, not
changed.

### 3.1 Error of the 1-degree bins (measured 2026-11-05, requested by Douglas)

Method: the slope samples of F2a (`_glo30_strip_samples`, the same function and the same pixel rule), 1 x 1 degree windows of 100 x 100 pixels of 0.01 deg;
for each pixel the exact steep share (mean of `slope > threshold` over the valid 30 m samples) against `_steep_share` on the 1-degree bins built from the same
samples. Sample: all 19 GLO-30 tiles of PRT (190,000 pixels) and 40 tiles of BRA drawn at random with seed 97 (400,000 pixels). Error of the eligible area
by slope alone, `sum(1 - E4)` over the pixels, bins against exact:

| Threshold | deg | PRT | BRA | mean abs share error PRT / BRA | max abs share error (pixel) PRT / BRA |
|---|---|---|---|---|---|
| PV 3 % | 1.718 | +0.33 % | +0.17 % | 0.0049 / 0.0079 | 0.180 / 0.283 |
| PV 5 % | 2.862 | -0.08 % | -0.28 % | 0.0025 / 0.0036 | 0.052 / 0.104 |
| PV 10 % | 5.711 | -0.14 % | -0.19 % | 0.0023 / 0.0026 | 0.029 / 0.039 |
| wind 20 % | 11.310 | -0.03 % | -0.04 % | 0.0012 / 0.0011 | 0.017 / 0.014 |
| wind 30 % | 16.699 | -0.02 % | -0.01 % | 0.0008 / 0.0006 | 0.015 / 0.012 |

The error of the eligible area is at most 0.33 % (below the 2 % limit of the command), so the 1-degree bins stay. A pixel can be off by up to 0.28 of
its share at 3 % (the within-bin distribution falls with slope, the interpolation assumes it flat), with signs that cancel in the sum; not changed. The
script is `scripts/audit_slope_bin_error_97.py`. The windows are tiles of the DEM, not the cells of the land-use mix, so a country-wide figure could be a
little different; the sample covers flat (Amazon) and hilly (Serra do Mar, Chapada, north of Portugal) terrain.

## 4. Water classes of the land cover against the river corridor

E5 excludes WorldCover class 80 (permanent water, 10 m) for both technologies, so the bed of rivers wide enough to be mapped at 10 m is already
excluded by E5, and the HydroLAKES polygons by E2. E3 (today a distance from the centre line, setback 0.5 km) and E5 are combined as independent
(`eligible *= 1 - share`), which counts the channel twice. The specification asks for the union, "without summing". The land cover is held as per-class
sample counts per 0.01 deg pixel, with no sub-pixel geometry, so the overlap of the corridor with class 80 inside a pixel is not known. See conflict C1.

## 5. LUF of Group 1

`group1_technical_potential.tex` defines the residual LUF as only the constraints not encoded in F3. Its values (PV 0.10 / 0.25 / 0.35 BRA and PRT,
0.05 / 0.10 / 0.25 IND; wind 0.05 / 0.15 / 0.30 and 0.05 / 0.075 / 0.15) are Tier 3 author judgment and do not repeat any Group 6 criterion. One
sentence of the Group 1 `.tex` (line 34-36) says "population density, protected areas and slope are excluded for both"; after this command the first
item is replaced by settlements. That sentence is in a thesis `.tex` file; it needs your authorization to change (conflict C4).

## 6. Memory of the labelling (item 4) and the ceiling

F3 of BRA peaks at 1,260 MB (caches current), 1,218 MB (rebuilt), 1,438 MB through the pipeline (`memory_budget.json`, `f3_phase`); cap 1,536 MB. The BRA grid has 7.10 M pixels, so one `int32` label array is 28 MB, one `float32` fraction array 28 MB and the `bool` mask 7 MB. The global labelling therefore fits by a wide margin if the fractions are kept on disk and mapped, one technology and scenario at a time (the peak adds about 70 MB, to be measured). This
is the design: pass 1 writes the eligible fraction after the pixel rules by stripes into a memory-mapped file; the labelling runs once on that file;
pass 2 re-aggregates the cells with the removed pixels set to zero. It does not need union-find. The test of the command (stripes against the whole
grid, a cluster crossing several stripes) is still written, with the whole-grid labelling as the oracle.

## 7. Conflicts with the specification

- **C1 (needs your decision).** Union of the river corridor with the water class. The corridor contains the channel by construction only if the width
  estimate is at least the real width, and the `.tex` says the estimate tends to be too small (bankfull relation fitted to larger discharge, applied to
  mean discharge). Without sub-pixel geometry of class 80 the union per pixel can only be bounded: `max(E3, w) <= union <= min(1, E3 + w)`, `w` the
  water share. Today's independent product is `1 - (1-E3)(1-w)`, between the two. Choices: (a) `max(E3, w)` (exact when the corridor contains the water;
  permissive side where it does not); (b) keep the independent product, which still double counts; (c) rasterize the water class at 10 m inside F2a,
  which is a new F2a layer. Recommendation: (a), recorded as a limitation (permissive bias for rivers wider than the corridor). E2 lakes and E5 stay
  independent of it as now.
- **C2 (needs your decision).** The 0.1 km2 cell filter `min_eligible_area_km2` (M-F3-04) acts on the 0.05 deg cell and is not in the `.tex`. The new
  minimum area acts on pixel clusters and replaces the idea of a minimum project size. Keep the cell filter in addition (so a cell of 0.1 km2 or more
  can still be dropped in the permissive scenario, which says "none"), or remove it and let the cluster rule be the only minimum? The `.tex` table says
  "none" for permissive; keeping 0.1 km2 contradicts it. Recommendation: remove it from the three scenarios, keep a numerical floor only to avoid
  zero-area candidates (area > 0).
- **C3 (information).** Cluster area: "eligible area reaches A_min" (`.tex`) against "cluster >= 1 km2" (command). Implemented as the sum of
  `eligible_fraction x geodesic pixel area` over the cluster, as the `.tex` says.
- **C4 (information; needs authorization to edit the thesis).** Group 1 `.tex` sentence on population density (section 5). The `.tex` files of Group 6
  are copied as given; nothing else in `docs/thesis` is edited without your word.
- **C5 (information).** Existing `land_availability` ranges are tied to status `sourced`; the new B_c, W exponent, setbacks, elevation limits and
  minimum areas are scenario values with a source and a tier each. `scenario_composition` will need a second way to declare a scenario value (explicit
  per-scenario table, `status: verify` allowed) beside the range mechanism. Design change, not a method change.
- **C6 (information).** `slope_max_deg` and the old `pop_density_max_per_km2` disappear from the per-technology ranges; slope is stored in percent. F7b
  uses the whole-grid functions (`prepare_shared_layers`, `technology_layers`, OQ-068); they have to learn the new exclusions too.
- **C7 (information).** The settlement layer is not in `database/raw`; it goes in `GeoFREA_data/external/ghsl/` (folder absent today). The download needs
  network access to the JRC GHSL server and a hash in the manifest; GHS-SMOD R2023A has no authentication.
- **C8 (information).** PROGRESS.json marks BRA and IND F3 as `awaiting_content_check_post_77`; the rerun order in the command (F2a layer, F3 cold) is
  consistent with the deferred check of PV-77, which will compare artifacts after this change as DIFERENTE by design.

## 8. Decisions needed before editing

C1 and C2. Everything else follows the command and the `.tex`.

## 9. Decisions taken and what was implemented (2026-11-05)

- **C1** (Douglas): `max(E3, w)` for the union with the water; implemented as the corridor share net of the water, `E3 = max(0, (c - w) / (1 - w))`, which removes `max(c, w)` where the water lies inside the corridor (L-049).
- **C2** (Douglas): the 0.1 km2 cell filter is removed from the three scenarios; a candidate has any eligible area (`> 0`), an elevation and, for wind, not above the limit of the scenario.
- **Bin error** (Douglas): measured (section 3.1), at most 0.33 % of the slope-eligible area, below the 2 % limit: the 1-degree bins stay.
- **Group 1 `.tex`** (Douglas): the sentence on population density now names the settlement setback of Group 6.
- **GHS-SMOD** downloaded on 2026-11-05 (`GeoFREA_data/external/ghsl/`, SHA-256 of the archive and of the raster in `D-F2a-027`).
- **Memory.** Settlement layer of F2a on BRA: peak 314.6 MB, 4.1 s (PRT 159 MB). F3 of BRA, cold shares, scratch directory: **peak 1,375 MB** (cap 1,536), 1,501 s; the label array is one `int32` of the grid (61 MB) and the peak sits in `aggregate_to_cells`, not in the labelling (`apply_minimum_area` 1,003 MB).
- **Specification conflicts found while running** (Douglas decided on 2026-11-05): (i) for `Q` below 1 m3/s the permissive exponent gave a wider channel than the central one, so the corridors were not nested (PRT: worst cell 0.1 % of the cell area); decision: the width is taken at the extremes of the exponent range reach by reach, `7.2 min(Q^0.48, Q^0.52)` permissive, `7.2 max(...)` restrictive, `7.2 Q^0.50` central; the tolerance of the order check and its limitation were removed and the corridors are nested by construction; (ii) the values of Group 6 are in `config/experiments.yaml` `land_availability`, where F3 reads its parameters (D-F3-002, D-F3-007), not in `parameters.json` as the command and the `.tex` header say; only `P_ref` and `PD` are read from `parameters.json`.
- **Tests.** F3 unit tests, `test_land_eligibility_group6_values.py` (every value of the specification per country, technology and scenario), `test_land_eligibility_min_area.py` (labels against a flood fill, a cluster across all stripes), stripes against the whole-grid oracle with the rules on; V-01 refrozen (30 earlier layers bit-identical; new layers verified by hand); ZZZ and ZZZ2 expected values rederived with the independent validator (wind 42 of 42, solar 40 of 40 checks).

## 10. Estimate of the effect on the eligible area (synthetic world ZZZ2, F3 only)

Same fixture, old code (commit 2bb1161) against the new code, 24 cells of 0.05 degree (area of the world 736 km2):

| Technology / scenario | Before (km2, share, candidates) | After (km2, share, candidates) | Change |
|---|---|---|---|
| solar restrictive | 375.3, 51.0 %, 17 | 435.5, 59.2 %, 17 | +16.0 % |
| solar central | 410.9, 55.8 %, 17 | 470.3, 63.9 %, 17 | +14.4 % |
| solar permissive | 425.1, 57.8 %, 17 | 497.3, 67.6 %, 17 | +17.0 % |
| wind restrictive | 375.3, 51.0 %, 17 | 435.5, 59.2 %, 17 | +16.0 % |
| wind central | 410.9, 55.8 %, 17 | 467.1, 63.5 %, 17 | +13.7 % |
| wind permissive | 425.1, 57.8 %, 17 | 491.6, 66.8 %, 17 | +15.6 % |

The rise is specific to this world: the population gradient of the fixture no longer excludes land (it was the old E6), and the new rules (a corridor of about 0.5 km, a 2 x 2 pixel settlement, a 1 km2 PV cluster) remove little. It says nothing about the real countries, whose effect depends on slope (PV 5 % against 10 degrees), the settlement mask and the minimum area. For orientation only, scratch runs of the real code (not rounds, nothing written under `outputs/`): PRT central solar 9,151 km2 (before 21,169) and wind 29,831 (before 28,136); BRA central solar 1,130,465 km2 (before 1,535,473) and wind 2,640,018 (before 2,196,099). The real effect is measured by the round of `PIPELINE_GUIDE.md` (Group 6 round).
