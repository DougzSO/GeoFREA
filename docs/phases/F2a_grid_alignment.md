# F2a grid_alignment

Status: `built_pending_conformance`
Methodology items: M-F2a-01 to M-F2a-04, V-01

## Contract

Requires: `acquisition_registry`. Produces: `aligned_layers` (COGs on the 0.01 degree grid, snapped for 0.05 degree nesting), distance rasters with `distance_capped` flags.

## Conformance

| Item | Requirement | Current state | Status |
|---|---|---|---|
| M-F2a-01 | 0.01 degree grid snapped for exact 5 x 5 nesting | Fixed 0.01 degree confirmed; `grid_alignment/reference_grid.py:build_reference_grid` (lines 56-64) snaps bounds only to 0.01 degree multiples (`floor`/`ceil` by `resolution_deg`), never to 0.05 degree multiples, and does not assert `width`/`height` are multiples of 5 | fail |
| M-F2a-02 | Geodesic distances, areas, and slope | Geodesic except `derive_slope_from_dem` (`KM_PER_DEG_LAT = 111.32`) | fail |
| M-F2a-03 | Distance cap as parameter with flag | `LINEAR_FEATURE_MAX_DIST_KM = 100.0` hardcoded, no flag | fail |
| M-F2a-04 | Per-height wind alignment, no cross-height combination | AHP combination code present (`WIND_AHP_MATRIX`) | fail |
| V-01 | Frozen parity for aligned rasters | Legacy-baseline parity; fixtures to refreeze after M-F2a-02 | fail |
| CONVENTIONS | no duplicated defaults | Pydantic schema defaults duplicate settings.yaml values in ResolutionsConfig/AdaptiveResolutionConfig/GeospatialConfig/SettingsFile | fail |

## Active implementation decisions

- **D-F2a-001 — Legacy grid_alignment ported with targeted revisions.** `grid_alignment` preserves the legacy's validated scientific logic where applicable, with specific, individually justified revisions (geodesy centralization, resolution fixed, distance cap) rather than a full rewrite or an unreviewed port.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-09-08 - grid_alignment (Fase 2a) portado do legado
- **D-F2a-002 — Bowring centralization, unified distance cap, fixed resolution.** Bowring geodesic calculations are centralized in `core/geodesy.py`; grid/road/river distance search uses one unified cap rather than a different value per feature (to be exposed as `distance_cap_km` per M-F2a-03, not the current hardcoded constant). The 0.01 degree fixed (non-adaptive) resolution is implemented; snapping bounds so 0.05 degree cells nest exactly (5 x 5 pixels) is not implemented — this decision is **partially conformant** with M-F2a-01 as written (see the M-F2a-01 conformance row and the TODO under Known issues). The fourth verdict of this same entry (retaining the wind AHP combination matrix) is retired — see `docs/_audit/2026-09_records.md` migration report, invalidated by M-F2a-04.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-09-09 - Passo 4: os 4 veredictos metodológicos de grid_alignment
- **D-F2a-003 — Fail-loud on corrupted land-cover tiles.** `mosaic_land_cover` fails loudly when a tile overlapping the country is corrupted, rather than silently absorbing an integrity failure of a file that is present.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-09-11 - grid_alignment: mosaic_land_cover fail-loud em tile corrompido

## Known issues

- **Known issue (CONVENTIONS, fail — see conformance row):** Adaptive resolution mode and its defaults (target_pixels, min_deg, max_deg, suitability) are removed in playbook task G-3; fields become absent, not required. Deferred by Douglas on 2026-09-21.
- Adaptive resolution mode exists as opt-in; not used by the method.
- **TODO (M-F2a-01, fail — see conformance row, evidence `grid_alignment/reference_grid.py:build_reference_grid` lines 56-64):** `build_reference_grid()` snaps `minx`/`miny`/`maxx`/`maxy` to 0.01 degree multiples only; it must instead snap them to 0.05 degree multiples before generating the 0.01 degree grid, so every 0.05 degree cell nests exactly on 5 x 5 pixels. Add a test asserting `width % 5 == 0 and height % 5 == 0` for the resulting `GridContext`.

## History

None.
