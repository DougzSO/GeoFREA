# F2a grid_alignment

Status: `built_pending_conformance`
Methodology items: M-F2a-01 to M-F2a-04, V-01

## Contract

Requires: `acquisition_registry`. Produces: `aligned_layers` (COGs on the 0.01 degree grid, snapped for 0.05 degree nesting), distance rasters with `distance_capped` flags.

## Conformance

| Item | Requirement | Current state | Status |
|---|---|---|---|
| M-F2a-01 | 0.01 degree grid snapped for exact 5 x 5 nesting | Fixed 0.01 degree; snapping for nesting not verified | pending audit |
| M-F2a-02 | Geodesic distances, areas, and slope | Geodesic except `derive_slope_from_dem` (`KM_PER_DEG_LAT = 111.32`) | fail |
| M-F2a-03 | Distance cap as parameter with flag | `LINEAR_FEATURE_MAX_DIST_KM = 100.0` hardcoded, no flag | fail |
| M-F2a-04 | Per-height wind alignment, no cross-height combination | AHP combination code present (`WIND_AHP_MATRIX`) | fail |
| V-01 | Frozen parity for aligned rasters | Legacy-baseline parity; fixtures to refreeze after M-F2a-02 | fail |

## Active implementation decisions

To be populated by the records migration task (geodesy centralization, fixed resolution, unified distance cap).

## Known issues

- Adaptive resolution mode exists as opt-in; not used by the method.

## History

None.
