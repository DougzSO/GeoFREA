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

Still pending migration: WDPA invalid-geometry repair before clip (2026-09-11, not in the section-4 `METHODOLOGY_REVISION` list — a `bug`-type entry per the audit's section 2 axis — carry forward during the rebuild if still applicable).

## Known issues

- Regression fixtures `regression-fixtures-v1` cover the 14 legacy criteria; only E1-E3 layers remain under V-01.

## History

None.
