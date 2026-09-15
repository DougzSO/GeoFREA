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

To be populated during the rebuild. Still-valid rationale to carry forward: WDPA invalid-geometry repair before clip; fail-loud on corrupted WDPA versus `assumed_free` for absent data; nodata-safe slope and TRI handling (TRI no longer used).

## Known issues

- Regression fixtures `regression-fixtures-v1` cover the 14 legacy criteria; only E1-E3 layers remain under V-01.

## History

None.
