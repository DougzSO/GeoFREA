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
| `grid_suitability` | Cost-driver distance, no normalization | rework |
| `road_suitability` | Cost-driver distance, no normalization | rework |
| `solar_resource` | PVOUT passthrough in kWh/kWp/day | rework |
| `wind_resource` | Weibull A/k and air density passthrough per height | rework |
| `river_biomass`, `lc_biomass`, `biomass_resource` | Removed (S-02) | remove |
| `seismic_suitability` | Removed (S-08) | remove |
| Percentile normalization per country | Removed (M-F2b-04) | remove |

## Active implementation decisions

- **D-F2b-001 — Riparian setback mechanism split across phases.** The riparian safety buffer is produced as a distance layer in `siting_layers` (F2b) and only promoted to a rigid exclusion in `land_eligibility` (F3); F2b itself does not exclude on it.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-09-11 - suitability_builder (Fase 3): mecanismo do buffer de segurança de rio
- **D-F2b-002 — WDPA absent versus corrupted.** `E1 protected` fails loudly on a present-but-corrupted WDPA file; `assumed_free` is used only for genuinely absent WDPA data, per M-F2b-05.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-09-11 - suitability_criteria: protected_areas distingue WDPA ausente de corrompido
- **D-F2b-003 — Nodata-safe terrain handling.** A pixel adjacent to nodata/NaN in the DEM never receives a corrupted terrain value; this nodata-safety pattern (originally applied to slope and the now-removed TRI term) carries forward to `E4 slope` in the rebuild.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-09-11 - suitability_criteria: TRI (terrain_score) não herda contaminação de NaN/nodata
- **D-F2b-004 — WDPA invalid-geometry repair moved to the shared clip path.** `compute_protected_areas()`'s own `make_valid()` repair (and `WdpaGeometryRepairReport`) was removed 2026-09-21; `core/geo_utils.py::clip_vector_to_country()` now repairs invalid geometries unconditionally for every caller (data_quality_audit included, not just this phase), returning the shared `GeometryRepairReport`. `compute_protected_areas()`'s `ProtectedResult` carries that report through; `SuitabilityCriteriaSummary.protected_wdpa_repair` replaces the old four flat `protected_wdpa_*` fields. V-01 regression (`test_protected_areas_footprint_matches_frozen`, PRT+BRA) confirmed max abs diff = 0.0 against the pre-refactor implementation. Carries forward into the F2b rebuild as-is (see History for the "pending migration" note this resolves).

## Known issues

- Regression fixtures `regression-fixtures-v1` cover the 14 legacy criteria; only E1-E3 layers remain under V-01.
- Parameters retired in H-2 (tier: null): criteria.slope_threshold_deg_solar, criteria.slope_threshold_deg_wind, criteria.slope_threshold_deg_biomass, criteria.road_max_dist_km, criteria.river_max_dist_biomass_km, criteria.grid_max_dist_km, criteria.normalization_min_percentile, criteria.normalization_max_percentile, criteria.seismic_percentile_low, criteria.seismic_percentile_high, criteria.linear_proximity_percentile_low, criteria.linear_proximity_percentile_high, criteria.terrain_slope_weight, criteria.terrain_tri_weight, criteria.tri_threshold_m, criteria.proximity_decay_sigma_km, criteria.proximity_smooth_sigma_px, criteria.proximity_plants_neutral_score, criteria.biomass_smooth_sigma, criteria.solar_pvout_weight, criteria.renewable_fuel_labels, criteria.protected_as_exclusion, criteria.land_suitability, countries.BRA.criteria.yield_by_land_cover, countries.PRT.criteria.yield_by_land_cover.

## History

- "Still pending migration: WDPA invalid-geometry repair before clip" (2026-09-11 note, carried in this record's Active implementation decisions) — resolved by D-F2b-004 (2026-09-21): the repair moved into the shared clip path rather than staying suitability_criteria-specific.
