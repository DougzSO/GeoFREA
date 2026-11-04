# Group 3 audit (COMMAND 83)

Written for Douglas. Audit before any edit, executed in the main session (CLAUDE.md, delegation policy). Branch `feat/83-group3-connection-degradation`, cut from `main`.
Normative specification: `docs/thesis/methods/group3_connection_degradation.tex` (untracked until this command commits it).

## 1. Substations and lines today

| Item | Finding |
|---|---|
| Source | `raw/infrastructure_grid/<ISO3>/<ISO3>_grid_osm.geojson` (per country, EPSG:4326). `grid.gpkg` (gridfinder + OSM, 3.68 M lines, no voltage) is in `database/raw/infrastructure/grid/` and is read by no phase (OQ-063, `docs/data/grid_provenance.md`). |
| Features | LineString `power=line` and **Point** `power=substation` only. No substation polygon exists in the three files, so `representative_point` is a no-op today and is kept for polygons from a later extract. |
| Substation counts (raw) | PRT 502 (101 with a `voltage` tag), BRA 196 (73), IND 207 (31). |
| `voltage` tag | Preserved as an OSM property (string). Not read by any F1/F2a/F2b code: no source file under `src/` mentions `voltage` or `substation`. Lines: PRT 6,952 of 7,265 tagged; BRA 19,322 of 20,437; IND 27,578 of 29,789. |
| Multiple values and units | Separators seen: `;` (`60000;10000`), `_` (`138000_69000_23000`), `/` (`132000/133000`). Units seen: volts (`220000`) and kV (`220`, `440`); also `0` and `600`. The parser has to take the largest value, convert by magnitude and treat the rest as absent. |
| How the grid enters | F2a (`grid_alignment/alignment.py`, step `grid_distance`) rasterizes **every** feature (all voltages, lines and substations) after `load_vector_bbox`, ANDs it with the country mask, and writes `dist_grid` through `rasterize_linear_distance`. F2b copies it as `dist_grid_km`. |

## 2. Distances today

- **Method.** `calculate_wgs84_isotropic_distance`: `scipy.ndimage.distance_transform_edt` in pixel space, scaled to km with the WGS84 km-per-degree at the latitude of the grid centre. It is the "geodesic EDT" of the project (one scale per country, not a per-pixel geodesic). Group 3 reuses it, as specified.
- **Layers.** `dist_grid_km` (all OSM lines and substations, any voltage), `dist_road_km`. No `dist_substation`, no `dist_grid_line` (gridfinder).
- **Aggregation to the 0.05 degree cell.** F3 `aggregate_to_cells(..., resources=...)` takes the mean over the eligible area for every layer listed in `_required_resources` (`land_eligibility/pipeline.py:300`); columns `dist_grid_km`, `dist_road_km` of `CellRow`. A new layer needs one more name there, one more column and the layer in F2b.
- **Cap.** Distances are never truncated (OQ-040); `distance_cap_km` is only the threshold of a QC flag raster.
- **Neighbouring countries.** The mask is applied before the transform (`feature_mask & country_mask`): a feature outside the contiguous territory does not count, and the per-country OSM extract is country-scoped at the source. Rule for the POI layer: **substations of neighbouring countries are not used**, the same rule as lines and roads. Documented in METHODOLOGY.
- **Roads.** `dist_road_km` uses every class: GRIP4 (`GP_RTP` 1 to 5) for BRA and PRT; the IND OSM file (sample: motorway, trunk, primary, secondary, tertiary). No class filter exists. Specification: primary and secondary. **Adjustment:** road class filter in config (`road_classes`: GRIP4 `GP_RTP` 1 to 3, OSM `highway` motorway, trunk, primary, secondary; motorway and trunk are kept because they are higher classes of the same corridor). Needs F2a (`roads`) to run again for the three countries.
- **Wind CF rule.** Eligible-area mean, the rule the specification asks for `D_sub`.

## 3. F6 today

| Parameter | Unit | Semantics today |
|---|---|---|
| `grid_cost_usd_per_mw_km` | USD/(MW km) | `P * dist_grid * grid_cost`: per MW and km, on `dist_grid_km` of any voltage. |
| `substation_cost_usd_per_mw` | USD/MW | per MW, added to unit capital cost. |
| `road_cost_usd_per_km` | USD/km | `dist_road * road_cost`, not divided by capacity (so the cost per MW depends on the capacity of the cell). |
| `degradation_rate` | fraction/year | one scalar per country and technology, sampled; energy annuity `A_e(r, d, n)` of the kernel. |

All four are `null` in BRA, PRT and IND (F6 fails loud, OQ-001, OQ-019) and carry test values in ZZZ. The Group 3 unit costs are **per project** (USD/km, USD per bay, USD/km) divided by `P_ref`, a different unit from `USD/(MW km)`. They are **renamed** (`line_cost_per_km`, `bay_cost`, `road_cost_per_km`), not reused; the validator refuses the old names and reports the migration.
Kernel: `lcoe_block` factors the numerator into `(C x 3) @ (3 x S)` and the energy annuity depends on the sample only. A PV degradation by cell zone makes the annuity depend on the cell, so it becomes a table `(zones x S)` indexed per cell.

## 4. gridfinder

`grid.gpkg` is in the local database (`database/raw/infrastructure/grid/`), outside `GEOFREA_DATA_DIR` and read by no phase. It enters at F2a, only for the sensitivity `poi_gridfinder_lines` (`D_grid_line`). The raw directory is read-only and nothing is written there; the clipped country extracts go to `GEOFREA_DATA_DIR` through the usual keyed clip cache.

## 5. Conflicts with the specification and decisions

| # | Finding | Decision |
|---|---|---|
| 1 | The POI layer, the road-class filter and `D_grid_line` need new F2a rasters (and an F2b layer and F3 column) for BRA, PRT and IND. | Not a stop: the command orders the code to be built and the run left ready (item 8). Nothing is run. Does not change F1 to F5 results: the new layers are added, `dist_grid_km` is kept for F5 and the maps. The road filter changes `dist_road_km`, which no F5 number uses. |
| 2 | Substations are points; no polygons. | `representative_point` implemented for polygons, covered by a test. |
| 3 | The per-country OSM extract has few substations (BRA 196, IND 207). With the threshold, fewer still. | Reported per country (section 6). The risk is real (L-049 OSM completeness); recorded in LIMITATIONS, the outcome is the specified one. |
| 4 | `references_group3_add.bib` is not on disk (searched `D:\Douglas`, nothing found; the `.tex` cites `cerc2022gna`, `ctuilIndicative2025`, `acer2023uic`, `aneelBPR`, `arderne2020`, `seel2023`, `karin2019`, `pvcz`, `jordan2022`, `hamilton2020`, `kim2025`, `straubmuck2025`, `irena2025costs2024`). | Pending for Douglas: send the file. Nothing is invented. |
| 5 | CLAUDE.md requires an explicit authorization for each commit, after the diff is presented; the command orders five commits and a push. | The work is committed in the five groups only after Douglas approves the diff; no push without it. Stated in the final report. |
| 6 | `pvcz` is not installed in `.venv`. | `pip install pvcz` as the command says (step 4). |
| 7 | ACER price year is unknown. | `price_year: null`, `status: "verify"`: accepted with a warning, as ordered. F6 still refuses on the three `to_be_sourced` costs. |

## 6. Substation counts per country (read from the OSM extracts, no heavy phase run)

Function `grid_alignment/poi.py:select_poi`, tolerance 50 m, thresholds BRA 138 kV, IND 220 kV, PRT 150 kV. Script outside the repository (scratchpad), reads the raw files only.

| Country | V_th (kV) | Total | With a usable tag | Inferred from lines | Excluded (no voltage) | Below V_th | **Eligible (POI points)** |
|---|---|---|---|---|---|---|---|
| BRA | 138 | 196 | 73 | 19 | 104 | 80 | **12** |
| IND | 220 | 207 | 29 | 10 | 168 | 35 | **4** |
| PRT | 150 | 502 | 100 | 11 | 391 | 108 | **3** |

(`with a usable tag` is below the raw count of tagged substations because a bare value such as `220`, `440` or `600` has no unit and is not guessed, and a value of `0` is ignored.)

## 7. Conflict that needs a decision from Douglas (stop on this item) — RESOLVED in COMMAND 84 (option 1: substations re-extracted as ways and relations; counts in `poi_counts_84.md`)

**The OSM extract cannot carry the POI layer as specified.** The specification takes the nearest eligible OSM substation, but the three extracts hold only substations mapped as nodes (502, 196 and 207 points; no polygon). In OSM most substations are mapped as closed ways, so the extracts are far from complete: the lines show it (PRT has 1,138 lines tagged 220 kV and 743 tagged 150 kV against 3 eligible substations). With 12, 4 and 3 eligible points, almost every cell of BRA, IND and PRT would be beyond 100 km (`long_distance`) and `D_sub` would measure the spacing of a handful of points, not the distance to the network. This is not a coding problem and it is not fixed by a parameter.

What was done: `select_poi` is implemented, tested and correct for any source (points or polygons). **Not done:** wiring `D_sub` into F2a, F2b and F3, nothing run. The options, for the verdict:

1. **Re-extract the substations as ways and relations** (Overpass or Geofabrik, `power=substation`, polygon centroid via `representative_point`, already supported) for the three countries. Faithful to the specification; needs a new raw acquisition outside `database/raw` (into `GEOFREA_DATA_DIR`) and an F1 change.
2. **Take line endpoints and junctions at or above V_th as pseudo-substations** from the same extract. Uses data already on disk; a methodological deviation from the `.tex` (a line end is not always a substation), so it is an open question until authorized.
3. **Keep the specification as written** and report that `D_sub` is dominated by data gaps; the three countries would then be mostly `long_distance`.

Everything else in COMMAND 83 does not depend on this and proceeds.
