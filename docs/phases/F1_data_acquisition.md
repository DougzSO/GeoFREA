# F1 data_acquisition

Status: `built_pending_conformance`
Methodology items: M-F1-01 to M-F1-07, A-05, A-11

## Contract

Requires: configuration. Produces: layer registry artifact (`acquisition_registry`) with, per layer, paths, provenance, fetch status, source version, checksum.

## Conformance

| Item | Requirement | Current state | Status |
|---|---|---|---|
| M-F1-01 | Registry with provenance | Implemented for 14 legacy layers; `provenance` and computed `fetch_status` verified in `data_acquisition/schemas.py:AcquiredLayer` (fetch_status, lines 238-248) and `data_acquisition/phase.py:run_acquisition_phase` (`_LAYER_REGISTRY`, `_LOCAL_PATH_HANDLERS`, lines 255-387) | pass |
| M-F1-02 | Active layer set | Seismic layer still registered; biomass-only inputs present | fail |
| M-F1-03 | GWA Weibull A/k, air density, wind speed at 100/150/200 m | Only `wind-speed` at 100 m fetched | fail |
| M-F1-04 | CMIP6 monthly rsds/tas/sfcWind and daily tasmax/pr | Not present in GeoFREA (GEAR has daily tasmax/pr/tas 2041-2070 only) | fail |
| M-F1-05 | ERA5 gust | Not present in GeoFREA | fail |
| M-F1-06 | GEM solar and wind trackers | Not present (GPPD power plants exist) | fail |
| M-F1-07 | GADM local-first with checksum | Network download with NaturalEarth fallback | fail |
| A-05 | Country mappings in config | Dicts in `local_layers.py` and `fetchers/hydrosheds.py` | fail |

## Active implementation decisions

- **D-F1-001 — Acquisition contract before real fetch.** The layer-acquisition contract (registry shape, provenance/fetch_status fields) is established before implementing any real fetch logic, so fetchers are added against a fixed contract instead of growing ad hoc.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-08-24 - data_acquisition skeleton
- **D-F1-002 — Equal audit depth for vector layers.** The data-quality audit reports equivalent depth for vector layers as for rasters; vector data does not get a shallower audit just because it is not a raster.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-08-24 - vector layer audit depth
- **D-F1-003 — Single source of truth for path vs paths.** `MULTI_FILE_LAYER_NAMES` in `data_acquisition/schemas.py` is the only place deciding whether a layer resolves to `path` or `paths`; no second, independently editable flag exists elsewhere that could drift from it.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-08-24 - path/paths source-of-truth consolidation
- **D-F1-004 — IUCN category case normalization.** WDPA `IUCN_CAT` values are normalized for case before use, since unnormalized values fragment identical protected-area categories into spurious separate buckets.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-08-24 - IUCN category normalization fix
- **D-F1-005 — Layer-keyed audit summary.** `AuditSummary` is a discriminated, layer-keyed structure rather than a flat dict, avoiding duplication of detail already available in `AuditResult`.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-08-24 - AuditSummary refactor to layer-keyed dict
- **D-F1-006 — Real fetchers replace acquisition skeleton.** Power plants, wind, lakes, and rivers resolve through real, live-verified fetchers rather than always leaving `path=None`, establishing the pattern later fetchers and local resolvers follow.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-08-25 - real fetchers for power_plants/wind/lakes/rivers
- **D-F1-007 — Acquisition activation.** `data_acquisition` genuinely feeds `data_quality_audit`, so the `UnwiredPhasesError` placeholder guard is removed once real inputs exist.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-08-25 - data_acquisition activation
- **D-F1-008 — Spatial-index clip for large countries.** Country clipping (`clip_vector_to_country()`) uses an STRtree spatial index, geometry simplification, and threading to keep exact-intersection clipping tractable for geometrically large/complex countries (Brazil).
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-08-25 - clip_vector_to_country() exact-intersection bottleneck
- **D-F1-009 — Guard against clip-less country processing.** `ClipRequiresCountryGdfError` prevents `country_gdf=None` with `clip=True` from silently falling back to an unclipped path that can exhaust available memory.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-08-26 - country_gdf=None + clip=True: incidente de quase-OOM + guarda
- **D-F1-010 — Real GADM fetcher for borders and admin1.** Country borders and admin1 boundaries resolve through a real GADM 4.1 fetcher, closing the dependency that blocked a real `country_gdf` in production.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-08-26 - real fetcher for borders/admin1 (GADM 4.1)
- **D-F1-011 — Local-database resolution for pre-placed layers.** Elevation, population, transmission grid, and land cover resolve from files already present in the local database (`GEOFREA_RAW_DATA_DIR`) rather than inventing new fetch logic for sources GeoFREA already holds locally.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-09-08 - wire das 5 camadas restantes, Fase 1 (elevation/population/grid/land_cover)
- **D-F1-012 — GRIP4 replaces per-country OSM roads.** Roads resolve from a single regional GRIP4 file, clipped per-country downstream, replacing a per-country OSM download.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-09-08 - wire das 5 camadas restantes, Fase 2 (roads/GRIP4)

## Known issues

- BRA rivers and roads run about 1.8x slower in full pipeline than in isolation; root cause unconfirmed. Not on the critical path because raster phases run once per country.
- Six corrupted BRA land-cover tiles in the local database; handled per tile.
- GRIP4 `regions_lookup.json` diverges from shapefile region numbering outside BRA and PRT; blocks India (OQ-012).
- GWA API redirects without validating product or height; existence must be checked on the CDN response.

## History

None.
