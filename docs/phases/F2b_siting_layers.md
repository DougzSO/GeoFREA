# F2b siting_layers

Status: `rework_required`
Methodology items: M-F2b-01 to M-F2b-05, V-01, U-06

## Contract

Requires: `aligned_layers`, parameters, technology registry, land-availability variants. Produces: `siting_layers` per technology: exclusion layers E1-E6 (binary COG), cost-driver layers (km), resource layers (physical units).

## Conformance

The current module `suitability_criteria` implements 14 normalized criteria for weighted overlay. Mapping to the rebuild:

| Current criterion | Rebuild role | Status |
|---|---|---|
| `protected_areas` | E1 protected | reuse (binary IUCN strict categories, WDPA geometry repair) |
| `lakes_exclusion` | E2 water | reuse |
| `river_solar`, `river_wind` | E3 riparian | reuse, parameter per technology |
| `terrain_score` | E4 slope (TRI term removed) | rework |
| (legacy F3 land-cover exclusions) | E5 land cover | new |
| `pop_suitability` | E6 population (binary threshold) | rework |
| `grid_suitability` | Cost-driver distance, no normalization | **built (H-4)**: `dist_grid_km` in `physical_layers.py`; the legacy function still exists until H-5/H-6 retire it |
| `road_suitability` | Cost-driver distance, no normalization | **built (H-4)**: `dist_road_km` in `physical_layers.py` |
| `solar_resource` | PVOUT passthrough in kWh/kWp/day | **built (H-4)**: `pvout_kwh_kwp_day` |
| `wind_resource` | Weibull A/k and air density passthrough per height | **built (H-4)**: `weibull_a/k_<h>m`, `air_density_<h>m` for 100/150/200 m |
| `river_biomass`, `lc_biomass`, `biomass_resource` | Removed (S-02), but see Known issues — regression test coverage for `lc_biomass`/`biomass_resource` has not actually been dropped | remove |
| `seismic_suitability` | Removed (S-08) | remove |
| Percentile normalization per country | **Still executing today — status corrected 2026-09-24 (ADJ-5), see Known issues** | rework (owned by H-2) |

## Active implementation decisions

- **D-F2b-001 — Riparian setback mechanism split across phases.** The riparian safety buffer is produced as a distance layer in `siting_layers` (F2b) and only promoted to a rigid exclusion in `land_eligibility` (F3); F2b itself does not exclude on it.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-09-11 - suitability_builder (Fase 3): mecanismo do buffer de segurança de rio
- **D-F2b-002 — WDPA absent versus corrupted.** `E1 protected` fails loudly on a present-but-corrupted WDPA file; `assumed_free` is used only for genuinely absent WDPA data, per M-F2b-05.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-09-11 - suitability_criteria: protected_areas distingue WDPA ausente de corrompido
- **D-F2b-003 — Nodata-safe terrain handling.** A pixel adjacent to nodata/NaN in the DEM never receives a corrupted terrain value; this nodata-safety pattern (originally applied to slope and the now-removed TRI term) carries forward to `E4 slope` in the rebuild.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-09-11 - suitability_criteria: TRI (terrain_score) não herda contaminação de NaN/nodata
- **D-F2b-004 — WDPA invalid-geometry repair moved to the shared clip path.** `compute_protected_areas()`'s own `make_valid()` repair (and `WdpaGeometryRepairReport`) was removed 2026-09-21; `core/geo_utils.py::clip_vector_to_country()` now repairs invalid geometries unconditionally for every caller (data_quality_audit included, not just this phase), returning the shared `GeometryRepairReport`. `compute_protected_areas()`'s `ProtectedResult` carries that report through; `SuitabilityCriteriaSummary.protected_wdpa_repair` replaces the old four flat `protected_wdpa_*` fields. V-01 regression (`test_protected_areas_footprint_matches_frozen`, PRT+BRA) confirmed max abs diff = 0.0 against the pre-refactor implementation. Carries forward into the F2b rebuild as-is (see History for the "pending migration" note this resolves).

- **D-F2b-005 — Cost-driver and resource layers are passthroughs in physical units (H-4, 2026-10-06).** `suitability_criteria/physical_layers.py::build_physical_layers()` writes 12 float32 GeoTIFFs from the aligned layers: `dist_grid_km`, `dist_road_km` (the uncapped F2a distances, OQ-040), `pvout_kwh_kwp_day`, and `weibull_a_<h>m` (m/s), `weibull_k_<h>m` (-), `air_density_<h>m` (kg/m3) for h = 100, 150, 200 (M-F2b-02/03). The only change to a value is that invalid pixels (non-finite or the source nodata) become `NODATA_FLOAT`; nothing is rescaled, clipped, normalized or weighted (M-F2b-04), and each file records `units` and `normalized=false` as tags. A missing required layer raises `MissingPhysicalLayerError` naming it (no silent skip). `wind_speed` is not an M-F2b-03 layer and is not written here. No CRAEI counterpart was found (no Weibull, PVOUT or distance-to-grid code in the baseline), so the module is new and carries no provenance header, which also corrects the unverified "CRAEI: ..." cell of the provenance map for M-F2b-02/03. Tests: `tests/unit/test_suitability_physical_layers.py` (4). Not done: wiring into `main.py` and the A-08 output location (`outputs/<ISO3>/siting_layers/layers/`), which belongs with H-5/H-6 together with retiring the legacy normalized criteria.

- **D-F2b-006 — H-5 and H-6 (COMMAND 16, 2026-10-08; sanity ranges per verdict 16b, 2026-10-09).** (a) H-5: before this change the overview had multi-panel figures only; one map per file did not exist for the exclusion and cost layers. `overview/layer_maps.py` (called by the `overview` phase) now writes, under `overview/figures/layers/` and named `<map>__na__na__na.png`: `dist_grid_km` and `dist_road_km` (F2b rasters), and for each technology the excluded share of the cell for E1 to E6 and the eligible share (F3 central cell table); `figures: all` draws 16 maps for two technologies, `summary` the two eligible-share maps, `none` nothing. (b) H-6, parity: V-01 covers F1, F2a and the E1 to E3 shares on ZZZ and passes. (c) H-6, sanity ranges (V-04): PVOUT keeps its `audit.yaml` range; the air density and the two distances take a **derived** range (`siting_layers/sanity.py`, declared in `audit.yaml` `derived_ranges`): density from the ISO 2533 standard atmosphere between the lowest and the highest elevation of the country's 30 m DEM tiles, plus the layer height, widened by a 5% quality-control tolerance on each side (D-F1b-015); distances from the bounding-box diagonal. Weibull A and k have no derivation and go to OQ-053. Result (`docs/_audit/2026-10_f2b_sanity.md`): 0 pixels outside in PRT, BRA and IND for PVOUT and the distances; 0 outside for the air density in BRA and IND (IND's lowest, 0.5165 kg/m3, is the standard atmosphere at about 8.1 km, the highest Himalayan terrain; the lowest density among IND wind candidate cells is 0.629 kg/m3, about 6.4 km, so no candidate cell lies in the thinnest air; which exclusion removes those cells was not examined); the 1 PRT pixel that the unwidened bound left outside (0.27% below it, Serra da Estrela, a climate warmer than the standard atmosphere) is inside the widened range, so PRT, BRA and IND have 0 pixels outside (verdict of 2026-10-09, D-F1b-015: the pixel passes by the rule of the 5% tolerance, not by an exception). The same ranges now make F5 raise on a candidate-cell value outside them (D-F5-019).

## Known issues

- **population unit is counts per pixel, not density (confirmed 2026-09-24, ADJ-2) — `E6 population`
  needs an explicit conversion this rebuild does not have yet.** `docs/_audit/2026-09_layer_quantities.md`
  §8 confirms by summation (national totals reproduced within 0.4-2.9% for BRA/PRT/IND) that the
  acquired WorldPop raster holds counts per pixel, while M-F2b-01's `pop_density_max[tech]` (OQ-003)
  is a threshold expressed in persons per km². No conversion from counts-per-pixel to persons/km2
  exists in the code today — it must divide each pixel's count by its own geodesic pixel area
  (`core/geodesy.py::wgs84_km_per_degree`, per M-F2a-02, not a flat degrees-to-km constant) before
  comparing against the threshold. This conversion is owned by H-3 (the same stage OQ-002 assigns
  `pop_density_max` consolidation to) — not implemented as part of this read-only pass.
- **Regression fixtures refrozen (G-4, 2026-10-06).** The 14-criterion legacy suite was removed and V-01 now covers F1, F2a and E1-E3 on the ZZZ country (`docs/phases/F2a_grid_alignment.md` D-F2a-010). E3 is frozen as the river distance only; the riparian exclusion itself waits for H-3.
- Parameters retired in H-2 (tier: null): criteria.slope_threshold_deg_solar, criteria.slope_threshold_deg_wind, criteria.slope_threshold_deg_biomass, criteria.road_max_dist_km, criteria.river_max_dist_biomass_km, criteria.grid_max_dist_km, criteria.normalization_min_percentile, criteria.normalization_max_percentile, criteria.seismic_percentile_low, criteria.seismic_percentile_high, criteria.linear_proximity_percentile_low, criteria.linear_proximity_percentile_high, criteria.terrain_slope_weight, criteria.terrain_tri_weight, criteria.tri_threshold_m, criteria.proximity_decay_sigma_km, criteria.proximity_smooth_sigma_px, criteria.proximity_plants_neutral_score, criteria.biomass_smooth_sigma, criteria.solar_pvout_weight, criteria.renewable_fuel_labels, criteria.protected_as_exclusion, criteria.land_suitability, countries.BRA.criteria.yield_by_land_cover, countries.PRT.criteria.yield_by_land_cover.
- **`BiomassParams` (`core/schemas.py::BiomassParams`) added to H-2's retirement list (2026-09-24, ADJ-5).** Biomass is out of scope (S-02) and no `parameters.json` country entry has a `biomass` key under `technologies` for BRA, PRT, or IND — but the Pydantic schema class itself was not previously named on H-2's list, only the `criteria.biomass`-adjacent config fields above. Kept today per `tests/unit/test_config_loader.py`'s own comment, "for backward compatibility (`criteria.biomass` still exists)" — that compatibility reason disappears once H-2 removes the `criteria.biomass`-family fields listed above, at which point the class validates nothing real and should go with them.
- **Percentile normalization is still executing today, not removed — status corrected 2026-09-24 (ADJ-5).** `config/parameters.json` still carries `normalization_min_percentile`/`normalization_max_percentile` (on the H-2 retirement list above, not yet acted on). Direct evidence it is live: `docs/phases/core.md` D-core-018's ZZZ hand-check (2026-09-24) found `solar_resource`/`wind_resource` both reporting a degenerate uniform mean of exactly 0.500 — the documented signature of a min-max/percentile normalizer given a zero-variance input (ZZZ's PVOUT and wind-speed rasters are uniform constants by design), not of a physical-units passthrough as M-F2b-03/M-F2b-04 require. Owned by H-2, same as the rest of this list.
- **PRT's current `suitability_criteria` output is provisional (2026-09-22).** Produced by an unrequested force_rerun cascade (see `docs/phases/core.md`'s decision on the FD4c/FD4d/FD5 pass), not a deliberate F2b conformance run; overwritten once Stage H lands.
- **PRT's `suitability_criteria` manifest entry now reads `stale_upstream`, correcting a false `success` (2026-09-27, playbook COMMAND F2-5 Part B item 8).** Same root cause and same fix as F2a's equivalent entry (see `docs/phases/F2a_grid_alignment.md`): its recorded `layer_registry` lineage (`9cfac6fb88c45...`) is two `data_acquisition` reruns behind the current one (`f1-2-gwa-prt`). Backfilled by the same one-time script, to `invalidated_by="data_acquisition", invalidated_in_run="f1-2-gwa-prt"` — not rerun; H-2 rewrites this phase into `siting_layers` and is the point where PRT gets a real, fresh run instead of a resume.
- **A-08 output-location redirect owned here, under H-2 (2026-09-27, playbook COMMAND ADJ-8b).** `suitability_criteria`'s report already writes to `outputs/<ISO3>/suitability_criteria/reports/`, which is A-08-conformant (`suitability_criteria/report.py:98-100` — unlike F1b's `audit/` location, this phase already got that part right), and the current module has no `processed/`-writing call site of its own (only `data_quality_audit` and `grid_alignment` write there; `suitability_criteria` consumes `grid_alignment`'s finished `aligned_layers`, not raw vectors, so it never needed its own clip cache). Recorded here only so H-2's rebuild starts from a clean baseline: whatever `siting_layers` newly needs cached, it writes under `interim(iso3, layer)` from the start, not `processed/` — there is no existing `processed/` usage in this phase to migrate away from.

## History

- "Still pending migration: WDPA invalid-geometry repair before clip" (2026-09-11 note, carried in this record's Active implementation decisions) — resolved by D-F2b-004 (2026-09-21): the repair moved into the shared clip path rather than staying suitability_criteria-specific.
- 2026-10-08: H-5 maps and H-6 statistics (D-F2b-006).
