# F1 data_acquisition

Status: `built_pending_conformance`
Methodology items: M-F1-01 to M-F1-07, A-05, A-11

## Contract

Requires: configuration. Produces: layer registry artifact (`acquisition_registry`) with, per layer, paths, provenance, fetch status, source version, checksum.

## Conformance

| Item | Requirement | Current state | Status |
|---|---|---|---|
| M-F1-01 | Registry with provenance | Implemented for 14 legacy layers; `provenance` and computed `fetch_status` verified in `data_acquisition/schemas.py:AcquiredLayer` (fetch_status, lines 238-248) and `data_acquisition/phase.py:run_acquisition_phase` (`_LAYER_REGISTRY`, `_LOCAL_PATH_HANDLERS`, lines 255-387) | pass |
| M-F1-02 | Active layer set | Seismic removed (F6-2, 2026-09-22): no `seismic`/`seismic_path` field remains in `_LAYER_REGISTRY`, `AuditInputs`, `GridAlignmentInputs`/`Result`, or `SuitabilityCriteriaInputs`; `criteria.seismic_percentile_low/high` removed from `config/parameters.json`. Biomass-only inputs still present (`CountryCriteriaParams.yield_by_land_cover`, `CriteriaParams.land_suitability`'s biomass column) — out of scope for this pass | fail |
| M-F1-03 | GWA Weibull A/k, air density, wind speed at 100/150/200 m | Only `wind-speed` at 100 m fetched | fail |
| M-F1-04 | CMIP6 monthly rsds/tas/sfcWind and daily tasmax/pr | Not present in GeoFREA (CRAEI has daily tasmax/pr/tas 2041-2070 only) | fail |
| M-F1-05 | ERA5 gust | Not present in GeoFREA | fail |
| M-F1-06 | GEM solar and wind trackers | Not present (GPPD power plants exist) | fail |
| M-F1-07 | GADM local-first with checksum | Implemented (F6-2, 2026-09-22): `fetchers/gadm.py::_local_database_level0()` checks `GEOFREA_SHARED_RAW_DIR/countries_borders/<gadm_dir>/gadm41_<ISO3>_0.shp` first (per `config/countries.yaml`'s new `gadm_dir`/`gadm_level0_sha256` fields), verifying sha256 before trusting it — no network call on a match. A mismatch raises `GadmChecksumMismatchError` (A-09 fail-loud), never a silent re-download. Only when the local database has no entry (or no recorded checksum) does it fall through to the pre-existing `GEOFREA_DATA_DIR` cache/network/NaturalEarth chain. `gadm_dir`/`gadm_level0_sha256` populated for BRA, PRT, IND (the three in-scope countries); other `countries.yaml` entries left null, matching that field's existing null convention. Tests: `tests/unit/test_fetchers_gadm.py::test_fetch_borders_local_database_hit_performs_no_network_call`, `::test_fetch_borders_local_database_checksum_mismatch_raises`, `::test_fetch_borders_local_database_absent_falls_back_and_fetches` | pass |
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
- **D-F1-011 — Local-database resolution for pre-placed layers.** Elevation, population, transmission grid, and land cover resolve from files already present in the local database (`GEOFREA_SHARED_RAW_DIR`) rather than inventing new fetch logic for sources GeoFREA already holds locally.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-09-08 - wire das 5 camadas restantes, Fase 1 (elevation/population/grid/land_cover)
- **D-F1-012 — GRIP4 replaces per-country OSM roads.** Roads resolve from a single regional GRIP4 file, clipped per-country downstream, replacing a per-country OSM download.
  Archive: docs/_archive/2026-09/DECISIONS.md 2026-09-08 - wire das 5 camadas restantes, Fase 2 (roads/GRIP4)
- **D-F1-013 — Seismic removed; GADM resolves local-first with checksum (F6-2, 2026-09-22).** Seismic hazard was excluded from scope by METHODOLOGY S-08 but still had a full end-to-end implementation (layer registry entry, alignment handler, `seismic_suitability` criterion, audit range check, config parameters) — removed entirely from `src/`, `tests/`, and `config/`, closing the M-F1-02 gap F6-1's audit found. GADM boundary resolution now checks `GEOFREA_SHARED_RAW_DIR/countries_borders/<gadm_dir>/` first (`config/countries.yaml`'s new `gadm_dir`/`gadm_level0_sha256` fields), verifying the recorded sha256 before trusting a local hit; a mismatch raises `GadmChecksumMismatchError` rather than silently re-fetching (A-09). Only a missing local entry falls through to the pre-existing `GEOFREA_DATA_DIR` cache/network/NaturalEarth chain, closing M-F1-07.

## Known issues

- BRA rivers and roads run about 1.8x slower in full pipeline than in isolation; root cause unconfirmed. Not on the critical path because raster phases run once per country.
- Six corrupted BRA land-cover tiles in the local database; handled per tile.
- GRIP4 `regions_lookup.json` diverges from shapefile region numbering outside BRA and PRT; blocks India (OQ-012).
- GWA API redirects without validating product or height; existence must be checked on the CDN response.
- **Unfiltered land_cover registry for BRA and PRT — resolved 2026-09-22 (FD4c rerun).** Originally found 2026-09-22 (audit FD3b1/FD3b2): the `data_acquisition` runs then on disk predated the geometry filter's effective exclusion (BRA 154/155 tiles registered, PRT 26/26). A `force_rerun` of `data_acquisition`+`data_quality_audit` for BRA and PRT against the current `config/countries.yaml` now produces a filtered registry matching the geometry check exactly: **BRA 112 of 155 tiles** (43 excluded: 42 zero-overlap + the manually-accepted `N03W051` sliver), **PRT 11 of 26 tiles** (15 zero-overlap, all via the geometry filter — PRT has no `excluded_land_cover_tiles` config entry). Confirmed against both countries' current `manifest.json`. Side effect: because `RunConfig.force_rerun` re-executes target_phases *and everything that transitively depends on them* (`orchestrator.py:589`), this same run also produced unrequested `grid_alignment` and `suitability_criteria` output for both countries — BRA's `grid_alignment` failed on the `population` reproject (see `docs/phases/F2a_grid_alignment.md` known issues) and its output was deleted as stale; PRT's `grid_alignment`/`suitability_criteria` completed and are kept, but labeled provisional (see `docs/phases/F2a_grid_alignment.md`, `docs/phases/F2b_siting_layers.md`).

## History

None.
