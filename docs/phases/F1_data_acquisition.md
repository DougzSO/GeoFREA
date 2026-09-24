# F1 data_acquisition

Status: `built_pending_conformance`
Methodology items: M-F1-01 to M-F1-07, A-05, A-11

## Contract

Requires: configuration. Produces: layer registry artifact (`acquisition_registry`) with, per layer, paths, provenance, fetch status, source version, checksum.

## Conformance

| Item | Requirement | Current state | Status |
|---|---|---|---|
| M-F1-01 | Registry with provenance | Implemented for 14 legacy layers; `provenance` and computed `fetch_status` verified in `data_acquisition/schemas.py::AcquiredLayer.fetch_status` and `data_acquisition/phase.py::run_acquisition_phase()`, `phase.py::_LAYER_REGISTRY`, `phase.py::_LOCAL_PATH_HANDLERS` (cited by function name, not line number, since the file has grown past two prior line-number citations already — see `docs/_audit/2026-09_conformance_check.md` action 2) | pass |
| M-F1-02 | Active layer set | Seismic removed (F6-2, 2026-09-22): no `seismic`/`seismic_path` field remains in `_LAYER_REGISTRY`, `AuditInputs`, `GridAlignmentInputs`/`Result`, or `SuitabilityCriteriaInputs`; `criteria.seismic_percentile_low/high` removed from `config/parameters.json`. Biomass-only inputs still present (`CountryCriteriaParams.yield_by_land_cover`, `CriteriaParams.land_suitability`'s biomass column) — out of scope for this pass | fail |
| M-F1-03 | GWA Weibull A/k, air density, wind speed at 100/150/200 m | Implemented 2026-09-23 (task F1-2): `fetchers/wind.py::fetch_gwa_product()` fetches all 4 products x 3 heights; 12 registry entries per country (`wind` = wind-speed@100m, unchanged, plus 11 new `wind_speed_150m`/`_200m`, `weibull_a/k_100/150/200m`, `air_density_100/150/200m`), each with its own `source_sha256` (D-core-016). Real run for BRA, PRT, IND: 12/12 layers resolved for all three, no failures. No CRAEI counterpart exists to adapt — CRAEI excludes wind power from its own scope entirely (its D04, L07 decisions), confirmed by inventory (F1-1, 2026-09-23: zero wind/GWA references anywhere in CRAEI) — every line here is fresh, no A-11 header; the project's first real A-11 adaptation moves to the CMIP6 work of M-F1-04 (task F-3). Finding: `combined-Weibull-A`/`combined-Weibull-k` GeoTIFFs carry no embedded CRS at all (confirmed via `rasterio`: `crs=None`, no GCPs, no tags, for both BRA and PRT) — unlike `wind-speed`/`air-density`, which both declare EPSG:4326. Same transform/grid as the other two products, so almost certainly WGS84 in practice, but not assumed: F1b's audit correctly reports both as `[MISSING] ... Must pass either crs or epsg.` (a genuine inspection failure, M-F1b-02 non-blocking) rather than silently treating them as fine. | pass |
| M-F1-04 | CMIP6 monthly rsds/tas/sfcWind and daily tasmax/pr | Not present in GeoFREA (CRAEI has daily tasmax/pr/tas 2041-2070 only) | fail |
| M-F1-05 | ERA5 gust | Not present in GeoFREA | fail |
| M-F1-06 | GEM solar and wind trackers | Not present (GPPD power plants exist) | fail |
| M-F1-07 | GADM local-first with checksum | Implemented (F6-2, 2026-09-22): `fetchers/gadm.py::_local_database_level0()` checks `GEOFREA_SHARED_RAW_DIR/countries_borders/<gadm_dir>/gadm41_<ISO3>_0.shp` first (per `config/countries.yaml`'s new `gadm_dir`/`gadm_level0_sha256` fields), verifying sha256 before trusting it — no network call on a match. A mismatch raises `GadmChecksumMismatchError` (A-09 fail-loud), never a silent re-download. Only when the local database has no entry (or no recorded checksum) does it fall through to the pre-existing `GEOFREA_DATA_DIR` cache/network/NaturalEarth chain. `gadm_dir`/`gadm_level0_sha256` populated for BRA, PRT, IND (the three in-scope countries); other `countries.yaml` entries left null, matching that field's existing null convention. Tests: `tests/unit/test_fetchers_gadm.py::test_fetch_borders_local_database_hit_performs_no_network_call`, `::test_fetch_borders_local_database_checksum_mismatch_raises`, `::test_fetch_borders_local_database_absent_falls_back_and_fetches` | pass |
| A-05 | Country mappings in config | Corrected 2026-09-24 (ADJ-5): the prior "hardcoded dicts" evidence is stale — both `local_layers.py::_load_countries_config()` and `fetchers/hydrosheds.py::_get_hydrosheds_region()` load `config/countries.yaml` directly, with no hardcoded country dict remaining in either module (confirmed by reading both functions; `_COUNTRY_TO_REGION` survives only as a docstring reference explaining the design, never a live dict). Matches `docs/phases/core.md`'s A-05 row, which was already correct — this row was the one the code contradicted. | pass |

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
- **D-F1-014 — M-F1-03 implemented fresh; GWA registry now distinguishes 12 product/height entries (task F1-2, 2026-09-23).** `fetchers/wind.py::fetch_gwa_product()` generalizes `fetch_wind()`'s verified endpoint pattern to `combined-Weibull-A`, `combined-Weibull-k`, `air-density` at 100/150/200m (`GWA_PRODUCTS`/`GWA_HEIGHTS_M`), raising `GwaProductNotFoundError` on a missing product/height rather than returning `None` — a fetch failure fails that one layer only (existing per-layer isolation), never silently registers an absent layer (A-09). `phase.py` generates 11 new `_LayerSpec`/`_FETCHED_LAYER_HANDLERS` entries from the product x height matrix (`_GWA_EXTRA_LAYER_SPECS`), alongside the existing `wind` entry (= wind-speed@100m, contract unchanged — still the layer `grid_alignment`/`suitability_criteria` consume as the resource layer). Real run, all three countries: 12/12 GWA layers resolved, each with `source_sha256` populated (`_hash_layer_files()`, D-core-016). Volume added: BRA 4.68 GB, PRT 137 MB, IND 1.77 GB (6.53 GB new, 33 files; `raw/gwa/` total across all three now 7.06 GB). `data_quality_audit` wired to match: `AuditInputs` gained `weibull_a_path`/`weibull_k_path`/`air_density_path` (representative 100m file, same "inspect one file" precedent as `wind_paths`), `audit.py`'s `_UNACQUIRED_GWA_PRODUCTS` emptied (all 4 products now fetched) in favor of `_GWA_PRODUCT_RASTER_KEYS`, which routes them through the normal raster-inspection path instead of an unconditional `not_audited` entry.

## Layer quantities and units (confirmed 2026-09-24, ADJ-1)

Read-only cross-check, direct file/metadata reads (not re-derived from config) — full evidence and
per-country statistics in `docs/_audit/2026-09_layer_quantities.md`.

- **solar (PVOUT)**: kWh/kWp/day, confirmed via `PVOUT.tif.xml`'s own abstract text ("kWh/kWp") plus
  masked per-country statistics (BRA/PRT/IND means 4.25-4.28) consistent with a specific-yield band,
  not horizontal irradiation. Matches M-F1-02 and `config/audit.yaml`'s existing `solar.unit`.
- **elevation**: metres, EPSG:4326, 0.005 deg — BRA -45.5 to 6757.4 m, PRT -1.6 to 1971.5 m, IND
  -177.8 to 8479.0 m, all physically plausible for Copernicus DEM. Matches configured resolution.
- **population**: **counts per pixel, confirmed 2026-09-24 (ADJ-2)** — decided by summation, not
  inference: summing every valid pixel inside each country's real GADM polygon reproduces the
  country's 2020 reference population within 0.4-2.9% for BRA/PRT/IND; reading the same values as
  density instead undershoots by ~117-140x. Cross-checked: the 99.9th percentile converts to
  6,354/15,682/18,725 persons/km2 for BRA/PRT/IND respectively under the counts reading — plausible
  dense-urban values, nothing anomalous. Full evidence: `docs/_audit/2026-09_layer_quantities.md`
  §8. `config/audit.yaml` now carries a `population` entry (resolution, unit, sanity range), absent
  before this pass.
- **wind-speed / Weibull-A / Weibull-k / air-density**: m/s, m/s, dimensionless, kg/m³ respectively
  — all match M-F5-03's expectations; ranges physically plausible for BRA/PRT/IND at 100 m,
  including IND's thin-air minimum reflecting Himalayan altitude.
- **land_cover**: categorical ESA WorldCover 2020 legend; classes sampled ({0,10,20,30,40,50,60,80,90,95})
  are all legend-valid, matching the class keys `config/parameters.json`'s `yield_by_land_cover`
  tables already use. `excluded_classes[tech]` (M-F2b-01's E5) does not exist in configuration yet —
  F2b is not built (OQ-015 open) — so no legend-vs-exclusion-set mismatch is checkable today.
- **slope**: not an F1/F1b layer — confirmed no file exists to audit; derived later by
  `grid_alignment` from the DEM (D-F1b-004).

## Embedded-value sweep (ADJ-6, A-04/A-05/U-05, 2026-09-24)

Scoped to `src/geofrea/data_acquisition/` and `main.py`'s references to it, per the sweep's
stated boundary — `src/geofrea/suitability_criteria/` and `src/geofrea/core/` are explicitly
out of scope (owned by Stage H and not yet swept, respectively). Full classification table:
`docs/_audit/2026-09_embedded_values.md`.

- **Moved: none.** No embedded value in this module both (a) had an unambiguous kind-b/c
  destination and (b) an existing, loaded config key to move into. Every candidate below
  lacked one or the other.
- **Stayed, operational-setting candidates with no existing `settings.yaml` home (kind b, not
  moved):** per-request HTTP timeouts (`fetchers/gadm.py:211` 120s, `fetchers/hydrosheds.py:216`
  300s, `:247` 180s, `fetchers/power_plants.py:74` 60s, `fetchers/protected_planet.py:128` 60s,
  `fetchers/wind.py:126,180` 60s each); hashing budget (`phase.py::_HASH_BUDGET_S` 60s).
  `settings.yaml` has no `network`/`hashing` section today; adding one and wiring these in is
  future work, not owned by any milestone yet.
  **Hash chunk size single-sourced 2026-09-24 (ADJ-7):** the two-row inconsistency this sweep
  originally found (`phase.py::_HASH_CHUNK_BYTES` 1 MiB vs. `fetchers/gadm.py::_HASH_CHUNK_SIZE`
  8 MiB, same operation, unreconciled) is now one constant,
  `data_acquisition/schemas.py::HASH_CHUNK_BYTES = 8 MiB`, read by both call sites (`phase.py`'s
  and `fetchers/gadm.py`'s own `_sha256_file()`). Does not change any hash value — sha256 is
  chunk-size-invariant, confirmed by rehashing `config/parameters.json` at both the old (1 MiB)
  and new (8 MiB) chunk size and comparing digests (identical). This is the same value that
  moves into `settings.yaml`'s (not-yet-existing) hashing section once one is added — the
  `docs/_audit/2026-09_embedded_values.md` table's two chunk-size rows collapse into the one
  above when that happens, since there is now only one constant to move.
- **Stayed, scientific/methodological value without a source (kind d → OQ):**
  `local_layers.py::_MIN_OVERLAP_DEG2 = 1e-6` (deg², land-cover tile inclusion threshold) —
  **OQ-033** opened (`docs/OPEN_QUESTIONS.md`).
- **Stayed, country/technology mapping with no loader (kind c):** the technology tuple is in
  `data_quality_audit` (see that record), not here — noted for completeness since A-05's own
  country-mapping dicts in this module were the ADJ-3b correction (see A-05's conformance
  row above), not a new embedded-value finding.
- **Stayed, implementation constants (grouped, not itemized):** ~30 module-level constants
  across `data_acquisition/` and its `fetchers/` submodule — external API endpoints/URL
  templates, a pinned commit SHA (`fetchers/power_plants.py::PINNED_COMMIT_SHA`, reproducibility
  per A-12), the GWA product-code vocabulary and its three hub heights
  (`fetchers/wind.py::GWA_PRODUCTS`/`GWA_HEIGHTS_M`, already cited to M-F1-03 in their own
  comments), format strings/regexes for filename parsing, and internal dispatch dicts
  (`_FETCHED_LAYER_HANDLERS`, `_LOCAL_PATH_HANDLERS`, `_LAYER_REGISTRY`) whose single-source-
  of-truth status is itself an active decision (D-F1-003) — correct location, no move
  candidate.

## Known issues

- **OQ-024 resolved (2026-09-23) — `AcquiredLayer` now carries `source_sha256`.** See `docs/phases/core.md` D-core-016 for the full verdict (per-file hash computed at resolve time, null-for-cost rule, `layer_registry` schema bump to `"1.1"`). Every layer resolved by this phase is covered, not only wind.

- BRA rivers and roads run about 1.8x slower in full pipeline than in isolation; root cause unconfirmed. Not on the critical path because raster phases run once per country.
- Six corrupted BRA land-cover tiles in the local database; handled per tile.
- **Per-layer isolation implemented (2026-09-24, F2-4 Part A).** `run_acquisition_phase()`'s `_LAYER_REGISTRY` loop (`phase.py`) wraps each layer's resolution independently: a raised exception is recorded on that layer's own `AcquiredLayer` (`resolution_status="failed"`, `error_type`/`error_location`/`error_message`), and every other layer still resolves. `main.py::_data_acquisition_run` always registers the `layer_registry` artifact before deciding whether to raise `DataAcquisitionLayerFailedError` (naming the failed layers) — `Orchestrator.run()`'s exception handling now persists whatever artifacts a phase registered before raising (`orchestrator.py`, the `except Exception` branch), so A-02's registry records what succeeded even though A-09 still marks the phase `"failed"` and stops dependents. Downstream adapters (`data_acquisition/adapter.py`, `grid_alignment/adapter.py`, `suitability_criteria/adapter.py`) read every layer through `resolved_path()`/`resolved_paths()` (`data_acquisition/schemas.py`), which raise `LayerAcquisitionFailedError` naming the layer if `resolution_status == "failed"` — a failed layer can never be silently read as an absent/optional one. Tests: `tests/unit/test_data_acquisition_phase.py::test_partial_layer_failure_still_registers_layer_registry_with_the_failed_layer_named` and the four `..._records_failed_layer` tests; `tests/unit/test_data_acquisition_adapter.py::test_adapter_fails_loud_on_a_failed_layer_never_treats_it_as_absent`.
- **OQ-012 closed 2026-09-24 (F2-5) — IND wired into `config/countries.yaml`, `data_acquisition` succeeds.** All three sub-items resolved:
  - **GRIP4 region.** `Region_5_South_Asia` per `GEOFREA_SHARED_RAW_DIR/infrastructure/roads/regions_lookup.json`; on-disk directory is mislabeled `Region_5_Middle_East_Central_Asia` (naming defect in the shared read-only database, not GeoFREA's — renaming it is out of scope). `grip4_region_dir`/`grip4_region_file` in `config/countries.yaml` point at the real on-disk name with an explanatory comment, Douglas-authorized 2026-09-23.
  - **Land cover.** Geometry filter alone suffices — `resolve_land_cover_tiles()`'s polygon-overlap check against the real GADM IND polygon excludes exactly 28 of 91 tiles (confirmed both by a standalone live run, F2-1, and by the real `data_acquisition` run below); no negligible-but-nonzero sliver case like BRA's `N03W051` exists for IND, so no `excluded_land_cover_tiles` entry was needed.
  - **HydroSHEDS region — determined from the source, not assumed (F2-5 action 2).** Method: read `HydroRIVERS_TechDoc_v10.pdf` (on disk at `GEOFREA_SHARED_RAW_DIR/hydrology/rivers/` and bundled inside every `fetch_rivers()`-downloaded zip) rather than relying on memory or documentation not actually opened. Page 4 ("3.1 File name syntax") gives the definitive region table — `af`=Africa, `ar`=North American Arctic, `as`=**Central and South-East Asia**, `au`=Australia and Oceania, `eu`=Europe and Middle East, `gr`=Greenland, `na`=North America and Caribbean, `sa`=South America, `si`=Siberia — and Figure 2's map places all of India inside the single contiguous "Asia" region, with no overlap into "eu" or any neighboring region: not a coverage question needing a stop-and-report (only one candidate region contains India). `hydrosheds_region: "as"` set for IND in `config/countries.yaml`, with a comment citing this evidence; BRA (`sa`) and PRT (`eu`) unchanged.
  - **Prior F2-4 objection was correct and stands:** the field was never a no-op — HydroRIVERS genuinely is region-split at the source (`fetchers/hydrosheds.py`, confirmed live), so `hydrosheds_region` staying populated (now for all three in-scope countries) was the right call, not removal.
  - **IND `data_acquisition` run (run_id `78334d40...`, 2026-09-24): SUCCESS, 13 of 13 layers resolved.** `layers_failed: 0` in the registry summary. `rivers` fetched its `as` tile live (86.3 MB zip, `raw/hydrosheds/IND/HydroRIVERS_v10_as_shp.zip`) and extracted to 225,263 features (`HydroRIVERS_v10_as.shp`) — fetch+extract completed within `data_acquisition`'s ~63s total phase runtime (14:46:32–14:47:35), the rest of that phase runtime spent scanning 91 land_cover tiles and fetching `protected`. `land_cover`: 63 of 91 tiles registered (28 excluded, matching the geometry filter exactly). Every other layer (borders, admin1, elevation, population, grid, roads, wind, protected, solar, lakes, power_plants) resolved without error. `outputs/IND/manifest.json`'s `data_acquisition` entry is `status: "success"`; the `layer_registry` artifact is registered. **Not fixed/run this pass:** `data_quality_audit` correctly failed loud immediately after (`CountryParamsRequiredError`, D-core-013) — IND still has no `parameters.json` entry (the F2-2 objection: `technologies.solar.slope_threshold_deg` etc. cannot be assumed without a source) — a separate, already-flagged gap, not part of OQ-012.
- GWA API redirects without validating product or height; existence must be checked on the CDN response.
- **Unfiltered land_cover registry for BRA and PRT — resolved 2026-09-22 (FD4c rerun).** Originally found 2026-09-22 (audit FD3b1/FD3b2): the `data_acquisition` runs then on disk predated the geometry filter's effective exclusion (BRA 154/155 tiles registered, PRT 26/26). A `force_rerun` of `data_acquisition`+`data_quality_audit` for BRA and PRT against the current `config/countries.yaml` now produces a filtered registry matching the geometry check exactly: **BRA 112 of 155 tiles** (43 excluded: 42 zero-overlap + the manually-accepted `N03W051` sliver), **PRT 11 of 26 tiles** (15 zero-overlap, all via the geometry filter — PRT has no `excluded_land_cover_tiles` config entry). Confirmed against both countries' current `manifest.json`. Side effect: because `RunConfig.force_rerun` re-executes target_phases *and everything that transitively depends on them* (`orchestrator.py:589`), this same run also produced unrequested `grid_alignment` and `suitability_criteria` output for both countries — BRA's `grid_alignment` failed on the `population` reproject (see `docs/phases/F2a_grid_alignment.md` known issues) and its output was deleted as stale; PRT's `grid_alignment`/`suitability_criteria` completed and are kept, but labeled provisional (see `docs/phases/F2a_grid_alignment.md`, `docs/phases/F2b_siting_layers.md`).

## History

None.
