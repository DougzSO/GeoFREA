# Distance-to-substation layer: consumers, other single-latitude conversions and a prototype of three methods (COMMAND 113)

Date: 2026-11-09. Audit and prototype outside the repository: no code, configuration or fixture was changed and nothing was committed; the prototype scripts and their records live in the session scratch folder, outside the repository. Data: the outputs of round 9c2dc3c8. Follows `docs/_audit/dist_sub_scale_audit.md` (the defect) and OQ-076 (the author's verdict: correct it; the method is chosen after this prototype). **No method is chosen here.**

## 1. Consumers of the five layers that use `calculate_wgs84_isotropic_distance`

The function is called by `rasterize_linear_distance` (layers `grid`, `poi`, `poi_sensitivity`, `roads`; `grid_alignment/layers.py` lines 263, 299, 311) and by `align_rivers` (layer `rivers`, `vector_alignment.py` line 379). "Case" says whether the value enters the central case of the pipeline or only a sensitivity.

| Layer (raster) | Read by (phase, function) | What it produces with it | Case |
|---|---|---|---|
| `poi` (`<ISO>_poi_aligned.tif`, `dist_sub_km`) | F2b `siting_layers/physical_layers.py:67` (physical layer `dist_sub_km`, role `cost_driver`); F3 `land_eligibility/pipeline.py:375` (`_required_resources`), flag raster at `:614` and `:791`; F6 `lcoe_modeling/inputs.py:283-296` reads the column `dist_sub_km` of the candidate tables | F3 candidate tables `candidates_<tech>__{central,restrictive,permissive}`: `dist_sub_km` (mean over the eligible area of each 0.05-degree cell, D_sub of Group 3) and `dist_sub_capped_share`; F6: line length L = tortuosity_grid x D_sub in `C_inter = (c_line*tau_grid*D_sub + C_bay + c_road*tau_road*D_road) / P_ref` (`lcoe_modeling/kernel.py:8`) and, with a loss per km, the transmission efficiency (`connection.py:255`, zero in the central case, 0.0004 in the sensitivity); F2b sanity V-04 (`siting_layers/sanity.py:197-208`) | **Central case**, in the three land scenarios |
| `poi_sensitivity` (IND only, 132 kV) | none found in `src`: it is written by `grid_alignment/alignment.py:514-518` and declared in the schemas; no phase reads it | nothing downstream | Sensitivity only (and not wired to a consumer) |
| `roads` (`dist_road_km`) | F2b `physical_layers.py:68`; F3 `pipeline.py:375`; F5 `technical_potential/input_ranges.py:34,88` and `pipeline.py:753` (`DISTANCE_COLUMNS`, range of the inputs); F6 `lcoe_modeling/inputs.py:283-297` | F3 candidate column `dist_road_km`; F6 road term of `C_inter` (c_road x tau_road x D_road); overview figure `overview/figures.py:226` | **Central case** |
| `grid` (`dist_grid_km`, distance to the nearest line) | F2b `physical_layers.py:66`; F3 `pipeline.py:375`; F5 `input_ranges.py:34,88`; overview `figures.py:225`, `diagnostic.py:93,131` | F3 candidate column `dist_grid_km` (a range check in F5 and a figure); F6 reads only `dist_sub_km` and `dist_road_km`, so it does not enter the cost | Central tables, no cost; the thesis names a sensitivity with the distance to the nearest line instead of the substation (see below): I did not find it wired in `lcoe_modeling` |
| `rivers` (`<ISO>_rivers_aligned.tif`) | `overview/diagnostic.py:89,131` (figure "Distance to river"); F3 does not read this raster: its river corridor reads the river vectors (`land_eligibility/pipeline.py:568,756`, `fractions.py`) | a diagnostic figure only | Figure only |

How the thesis describes D (`docs/thesis/methods/group3_connection_degradation.tex`, lines 38-40 and 48-50):

> "Distances are computed with the same geodesic distance transform used for the other distance layers (Stage F2a), on the 0.01$^\circ$ grid, and aggregated to each 0.05$^\circ$ cell as the mean over its eligible area. The connection length is the distance corrected by a tortuosity factor: L_grid,i = tau_grid D_sub,i, L_road,i = tau_road D_road,i, where D_sub,i and D_road,i are the distances to the nearest eligible substation and to the nearest primary or secondary road."

and, at lines 55-58, "As a sensitivity, the substation distance is replaced by the distance to the nearest line of the predictive network layer (gridfinder combined with OSM)". `docs/METHODOLOGY.md` M-F2a-03 says the distance rasters "store the **uncapped geodesic distance**" and M-F2a-09 that `poi` is "the uncapped geodesic distance (the same distance transform as M-F2a-03, on the 0.01 degree grid)". The text says "geodesic"; the layer applies one isotropic scale per grid (`dist_sub_scale_audit.md`). The text will have to follow whichever method is chosen.

## 2. Other conversions from pixels to kilometres with a single latitude

Search over `src` for `wgs84_km_per_degree`, a latitude taken once (`lat_center`, `lat_mid`, `transform.f + transform.e x height/2`) and constants of kilometres or metres per degree. "(i)" = local scale, in a block of small extent; "(ii)" = scale of a whole grid or extent, the same defect as the distance layers. Longitude-scale error is `cos(phi) / cos(phi_ref) - 1`.

| Where | Latitude used and extent of the block | Class | Estimated maximum relative error | Reaches a result? |
|---|---|---|---|---|
| `grid_alignment/vector_alignment.py:165` (`calculate_wgs84_isotropic_distance`) | middle row of the whole grid (PRT 39.575, IND 21.8, BRA -14.225), the whole grid | **(ii)** | +-12 to +18 % by direction (`dist_sub_scale_audit.md`) | Yes: `poi`, `grid`, `roads`, `rivers` |
| `land_eligibility/fractions.py:227` (river corridor, `_corridor_shares`) | middle of a strip of `DEFAULT_STRIP_ROWS = 40` rows = 0.4 degree, strips anchored on the absolute lattice (`90 - (k0 + 0.5 x 40) x 0.01`); local metric frame with x scaled by `m_lon / m_lat`; buffer in metres | **(i)** | at the strip edge (0.2 degree from the middle): 0.32 % at 42.2 N (PRT), 0.25 % at 35.55 N (IND), 0.23 % at 33.75 S (BRA); the same relative error on the buffer width (for a buffer of 100 m, 0.3 m) | Yes (F3 eligible area), negligible |
| `land_eligibility/fractions.py:300` (settlement setbacks, `mask_setback_fractions`) | same strip: 40 rows, middle latitude; `distance_transform_edt(..., sampling=(dy_m, dx_m))` on sub-pixels, with a halo of rows (`pad_coarse`) and of sub-columns (`halo`) that covers the largest setback | **(i)** | same 0.32 / 0.25 / 0.23 %, relative to the setback (for 500 m: 1.6 m) | Yes (F3), negligible |
| `grid_alignment/poi.py:143` (`infer_voltage_from_lines`, tolerance 50 m) | latitude of the representative point of each substation; window of the size of the substation | **(i)** | about 0.007 % at 42 N (polygon of the order of 1 km) | Yes (voltage of untagged substations), negligible |
| `grid_alignment/raster_alignment.py:410, 587`; `grid_alignment/fabdem_slope.py:79`; `land_eligibility/cells.py:91`; `data_quality_audit/land_cover_tiles.py:45`; `overview/diagnostic.py:213` | one latitude **per row** (pixel areas and slope steps) | not a single latitude (exact per row) | none from this cause | Yes, correct |
| `overview/style.py:29` (hillshade) and `:86` (scale bar); `viz/mapstyle.py:178,184,962` (aspect, scale bar) | mid latitude of the extent drawn (whole country) | **(ii)**, display only | east-west scale at the edges of the extent: PRT +3.7 / -3.9 %, IND +6.6 / -12.4 %, BRA -14.2 / +2.7 % (the scale bar is right at the mid latitude by construction; the hillshade uses the same dx, dy for the whole picture) | No, figures only |
| `viz/display.py:29,60`; `climate_forcing/figures.py:34,197` | constant 111.32 km per degree, cosine at a mid latitude | **(ii)**, display only | same order as the row above | No (a figure estimate and a text note) |
| `siting_layers/sanity.py:103-104` (`bbox_diagonal_km`, V-04) | longitude scale at the latitude of the box nearest to the equator, deliberately the largest one | **(ii)**, an upper bound by design | overestimates the east-west extent by up to +7.9 % (PRT), more in IND and BRA | No: a sanity bound, never below the geodesic |

The strips of `fractions.py` already use the form "Euclidean distance with `sampling` in kilometres per strip of latitude, with a halo" (the prototype M2 below). Nothing else in `src` converts a distance transform with one latitude for a whole grid.

## 3. Prototype: three methods for the central `poi` layer of PRT, IND and BRA

**Methods** (the burnt pixels are the pixels of distance 0 of the stored layer `<ISO>_poi_aligned.tif`: each eligible substation burnt into its pixel and masked by the country mask, exactly the current selection rule; the prototype changes only the distance step).

- **M0**, the current method: `distance_transform_edt` in pixels on the whole grid times `sqrt(|a| x lon_km x |e| x lat_km)` at the middle row of the grid. My reimplementation reproduces the stored layer: maximum difference 0.0 km in the three countries.
- **M2**: `distance_transform_edt` with `sampling=(dy_km, dx_km)` by strips of 40 rows (0.4 degree) at the middle latitude of each strip, with a halo of rows that starts at 64 and doubles until every valid pixel of the strip is nearer than the edge of the window (nothing outside the window can then be nearer), up to the whole grid.
- **M3**: nearest burnt pixel centre by nearest neighbour in ECEF coordinates (`scipy.spatial.cKDTree`), then the WGS84 geodesic (`pyproj.Geod`) to it, by strips of 50 rows of the valid (in-country) pixels.

**Error.** Against the brute-force geodesic (the minimum over all burnt pixel centres of `pyproj.Geod.inv`) on the same 20,000 pixels per country as COMMAND 111: the central scenario, solar, same seed (20261109) and the same order of draws, so the sample is the same. Relative error on the pixels with a reference distance of at least 2 km (19,572 PRT, 19,819 IND, 19,902 BRA); absolute error on all 20,000. The fractions are those of the sample (equal allocation per 5-degree band), not weighted by band area as in COMMAND 111, so those of M0 differ by one or two points from that report (the P95 and the maximum agree with it: 14.50 % and 17.90 % in PRT).

**Time and memory.** Each method ran alone in its own child process, one at a time, nothing else of mine running. Time = wall seconds of the distance step (inputs loaded, result in memory); peak = peak working set of the child process (`psutil`, Windows) at the end, which includes the interpreter, numpy, scipy and pyproj and the result written to disk; "base" = the same measure after the masks were loaded and before the distance step. Cap: 1,536 MB (`config/memory_budget.json`).

### 3.1 Layer `poi`, central

| Country | Method | P95 relative error | Max relative error | P95 abs. error (km) | Max abs. error (km) | Pixels > 1 % | Pixels > 5 % | Time (s) | Peak (MB) | Base (MB) | Under 1,536 MB |
|---|---|---|---|---|---|---|---|---|---|---|---|
| PRT (280 burnt, 93,215 valid) | M0 | 14.50 % | 17.90 % | 2.90 | 5.75 | 94.7 % | 72.8 % | 0.01 | 73 | 68 | yes |
| PRT | M2 | 0.23 % | 0.33 % | 0.042 | 0.13 | 0 % | 0 % | 0.04 | 71 | 67 | yes |
| PRT | M3 | 4.5e-6 % | 5.9e-6 % | 8.6e-7 | 1.9e-6 | 0 % | 0 % | 0.18 | 70 | 67 | yes |
| IND (3,131 burnt, 2,779,362 valid) | M0 | 8.31 % | 16.59 % | 3.50 | 21.89 | 84.0 % | 11.3 % | 0.8 | 336 | 82 | yes |
| IND | M2 | 0.14 % | 0.44 % | 0.10 | 0.61 | 0 % | 0 % | 6.0 | 173 | 83 | yes |
| IND | M3 | 4.5e-6 % | 6.0e-6 % | 3.1e-6 | 7.6e-6 | 0 % | 0 % | 6.0 | 130 | 83 | yes |
| BRA (3,645 burnt, 7,100,454 valid) | M0 | 10.36 % | 17.84 % | 4.34 | 14.96 | 74.8 % | 14.3 % | 2.1 | 579 | 96 | yes |
| BRA | M2 | 0.11 % | 0.28 % | 0.054 | 0.96 | 0 % | 0 % | 34.4 | 437 | 96 | yes |
| BRA | M3 | 4.5e-6 % | 5.9e-6 % | 3.5e-6 | 2.9e-5 | 0 % | 0 % | 14.1 | 178 | 96 | yes |

Reading. M2 leaves 0.1 to 0.4 % (the scale changes by up to 0.3 % inside a 0.4-degree strip, plus the curvature of the path for the farthest pixels: the largest absolute error, 0.96 km, is at a pixel 557 km from the nearest substation, 0.17 %). M3 agrees with the brute-force geodesic to the rounding of the float32 raster (the reference is the same geodesic; the nearest neighbour in ECEF chord coincides with the nearest by geodesic in all 60,000 samples). The prototype does not include loading the vector, burning it or writing the GeoTIFF; the whole `poi` layer process peaked at 777 MB on BRA in the measured budget (`config/memory_budget.json`), a different measure (peak resident memory of the layer process) that contains those steps. The distance step of M0 alone already takes 483 MB above its base in BRA; M2 takes 341 MB and M3 82 MB.

### 3.2 Layer `roads` of BRA (dense lines), time and memory only

| Method | Burnt pixels (of 7,100,454 valid) | Time (s) | Peak (MB) | Base (MB) | Under 1,536 MB |
|---|---|---|---|---|---|
| M0 | 347,067 (4.9 %) | 1.6 | 579 | 96 | yes |
| M2 | 347,067 | 17.6 | 284 | 96 | yes |
| M3 | 347,067 | 23.9 | 204 | 96 | yes |

For `roads`, M2 takes 17.6 s against 34.4 s on `poi` and M3 takes 23.9 s against 14.1 s; I did not instrument the halo, so the reason is not measured (likely: with 347,067 burnt pixels spread over the country the windows of M2 stop growing early, while the tree of M3 has 347,067 points and 7.1 million pixels are queried). The whole `roads` layer process measured 887 MB in the budget file.

## 4. Where the 1,536 MB cap stands

Every method, on the two layers, stays under the cap: the largest peak of the distance step is 579 MB (M0, whole-grid transform, which is the current method), 437 MB for M2 and 204 MB for M3. The condition of item 5 of the command (no method respects the cap in BRA) did not occur, so no smaller strips were tried; the bottleneck of M2 is the window of the strips far from any substation, which grows to the whole grid (the 1,016 km maximum distance of BRA is about 900 rows), and the number of rows per strip and the starting halo are the two parameters that trade time for memory. The budget file measures whole layer processes, not the distance step, so a change of method would be followed by a new measurement of the layer in `memory_budget.json`.

## 5. What this prototype does not decide

- Which method (M2 or M3, or another) goes into the layer. Both remove the defect: P95 relative error 0.1 to 0.2 % (M2) or at the float32 rounding (M3), against 8 to 15 % (M0).
- Strip height and halo of M2; strip height of M3; whether `grid`, `roads` and `rivers` (same function) are corrected together.
- The effect on fingerprints, caches, the deferred content check and the rerun of F2a to F5 is in `dist_sub_scale_audit.md` section 6, and the validator check (a) of `validate_zzz_by_hand.py` (conformity with the method) would have to be rewritten to the method chosen.
- Whether the thesis sentence about a "geodesic distance transform" stays as it is (true for M3, true up to 0.4 % for M2).

Reproducibility: the masks, the samples and the brute-force references are in the scratch folder `scratchpad/proto` (`common.py`, `prep.py`, `child.py`, `evaluate.py`, `runall.sh`, `results.jsonl`), outside the repository.
