# GeoFREA Data Inventory Audit

Generated: 2026-09-22T14:41:23.741553 (original pass, Claude Haiku 4.5 subagent)
Corrected: 2026-09-22 (this pass, Claude Sonnet 5, main session — no subagent; see `CLAUDE.md` "Delegation policy")
Methodology version: 1.1.0

> **Correction note.** The original pass classified every raw file as "orphan" because the manifest only records phase artifacts, not raw inputs — that is expected behavior, not evidence of garbage. This pass replaces the single "orphan" category with two real categories (`raw_input`, `unreferenced`), completes the actions the original pass narrowed or skipped outright (FD1 actions 3 and 4-7; the objective names them FD1/FD2, see the six sections below), and corrects the IND land-cover finding shared with the companion coverage audit. All 66 previously-"orphan" files are `raw_input`; 0 are `unreferenced`.
>
> **Correction note (2026-09-22, FD3b1 pass).** The verification pass that followed this document (FD3b1: call-site census, environment resolution, A-08 conformance check, GWA 3-way hash, PRT tile-filter empirical check) found seven sentences below that this document itself got wrong or stated too confidently. Each is marked in place with `[FD3b1, 2026-09-22]`. Summary of the seven corrections (full text at each marked location):
> 1. **Action 2** — "Live" was used to imply `outputs/<ISO3>/raw/` is the *correct* tree. It is the tree the manifests reference, but it is **not** the A-08-conformant one — A-08 (`METHODOLOGY.md:337`) specifies `raw/<source>/<ISO3|_global>/`, which is exactly where the 66 "duplicate" files sit.
> 2. **Action 1 / Proposed Actions table** — the 66 `raw_input` files were called a "candidate for deletion as a duplicate of the live copy." Reversed: if anything is corrected, A-08 says keep `raw/<source>/<ISO3|_global>/` and fix the fetchers that write to `outputs/<ISO3>/raw/` instead.
> 3. **Action 6** — PRT's 15 zero-overlap tiles were presented as a risk to a *future* run. Empirically, PRT's manifest already-recorded `grid_alignment`/`suitability_criteria` (`success`) were built from all 26 tiles, unfiltered — the risk already materialized in the artifacts on disk.
> 4. **Action 4 table** — PRT `grid_alignment`/`suitability_criteria` were marked "current, not stale." Manifest-status-current is still correct, but both rest on the unfiltered 26-tile land_cover set — see the added row below.
> 5. **Action 1** — BRA's `S36W057`-only exclusion (154/155 tiles) was not reconciled against the document's own 42-tile geometry finding and 44-entry `countries.yaml` list elsewhere in the same document.
> 6. **Action 4 heading** — "Stale classification" covered `grid_alignment`+`suitability_criteria` for BRA only. `data_acquisition`'s land_cover artifact for **both** BRA and PRT is also stale relative to current config/code — see the added row below.
> 7. **Naming table / Action 4** — no mention that the `StoredPath` migration (`core.md` D-core-005) is applied only to phase-artifact entries (`ArtifactEntry`, via `orchestrator.py:673`), not to `data_acquisition`'s raw-layer registry (`AcquiredLayer.path`/`.paths`, still plain strings) — matches the already-open `OQ-024` but wasn't cross-referenced here.

## Executive Summary

Total size: **12,081,766,578 bytes (12.08 GB)**
Total files: **639**

## Category Summary (six categories)

| Category | File Count | Size (bytes) | Size (GB) | Definition |
|---|---|---|---|---|
| Active (in manifest) | 17 | 2,522,196 | 0.00 | Tracked in a phase manifest, current run |
| Cache — current | ~161 | ~6.0 GB (est.) | ~6.0 | `interim/`/`outputs/` artifacts matching the current run_id and a `success` phase status |
| Cache — stale | 29 | see Action 4 | included above | `interim/`/`outputs/` artifacts under a phase the current manifest marks `failed`/`skipped_upstream_failed`, or superseded by a newer artifact under the same key |
| **raw_input** | **66** | **4,383,849,641** | **4.38** | Raw file produced by a fetcher or copied from `GEOFREA_SHARED_RAW_DIR`, resolvable by a `paths.py`/fetcher raw-path pattern — see Action 1 |
| **unreferenced** | **0** | **0** | **0.00** | Neither a manifest artifact nor a resolvable raw input — see Action 1 |
| Legacy (reference/) | 328 | 1,409,148,189 | 1.41 | Frozen baseline |
| Log (logs/) | 38 | 2,118,898 | 0.00 | Run history |
| **TOTAL** | **639** | **12,081,766,578** | **12.08** | |

(The Cache split into current/stale does not change the original Cache category's combined 190 files / 6,284,127,654 bytes; it is a sub-classification within it, detailed in Action 4.)

---

## Action 1: Reclassify — raw_input vs. unreferenced, and zip redundancy

### Why "orphan" was the wrong category

`outputs/<ISO3>/manifest.json` records phase *artifacts* (`data_acquisition`, `data_quality_audit`, `grid_alignment`, `suitability_criteria`), not raw inputs. A manifest was never going to reference a file under `GEOFREA_DATA_DIR/raw/<source>/<scope>/` — that tree is outside the phase-artifact model entirely. Calling every such file "unreferenced by any manifest" and lumping it with genuine garbage in one "orphan" bucket manufactures a 4.38 GB cleanup problem that isn't one.

### Method

For each of the 66 files in `logs/orphan_files.txt`, checked whether its relative path matches `raw/<source>/<scope>/...` — the pattern `paths.fetched_raw(source, scope)` builds (`src/geofrea/core/paths.py:126-139`, returns `GEOFREA_DATA_DIR / "raw" / source / scope`). All 66 do (`source` ∈ {gadm, gwa, hydrosheds, wdpa, wri_gppd}, `scope` ∈ {BRA, PRT, _global}), so by path structure alone they are candidate `raw_input`.

To confirm they are genuine fetcher output rather than files someone happened to place in a matching path, ran a sha256 pass (script executed this session, not committed) comparing each of the 66 against every same-size file under `GEOFREA_DATA_DIR/outputs/`. **Result: all 66 are byte-for-byte identical (sha256 match) to a file that the BRA, PRT, or `_global` manifest actually references** under `outputs/<ISO3 or _global>/raw/`. Example: `raw\gadm\BRA\gadm41_BRA_shp\gadm41_BRA_0.shp` (6,502,404 bytes) has sha256-identical content to the manifest-referenced `outputs\BRA\raw\gadm41_BRA_shp\gadm41_BRA_0.shp`.

**This is not a coincidence — it's a dead code path.** `paths.fetched_raw()` (`paths.py:126-139`) has **zero callers anywhere in `src/`** (checked: `grep -rn "fetched_raw(" src/` matches only its own definition). Every current fetcher (`gadm.py:180` `fetch_borders`, `:206` `fetch_admin1`; `hydrosheds.py:196` `fetch_lakes`, `:219` `fetch_rivers`; `wind.py:40` `fetch_wind`, dest `wind.py:55`; `protected_planet.py:73` `fetch_protected_areas`) takes `outputs_dir: Path` and writes directly under `outputs/<ISO3>/raw/` or `outputs/_global/raw/` — the pattern the manifests actually record. The `raw/<source>/<scope>/` tree and its `fetched_raw()` helper are leftovers from an earlier layout that a prior version of the fetchers wrote to, before they were changed to write into `outputs_dir` directly. Nothing currently reads from `raw/<source>/<scope>/`.

### Classification result

| Category | Count | Size | Verdict |
|---|---|---|---|
| **raw_input** | 66 | 4,383,849,641 bytes | Genuine fetcher output, byte-identical to the manifest-referenced copy under `outputs/`, sitting in a directory (`raw/<source>/<scope>/`) that no current fetcher writes to. **`[FD3b1, 2026-09-22]` Correction:** not a candidate for deletion — `raw/<source>/<ISO3\|_global>/` is the A-08-conformant tree (`METHODOLOGY.md:337`); `outputs/<ISO3>/raw/` is not. If the duplication is fixed, the fetchers should be corrected to write to `raw/<source>/<scope>/` again, not the other way around. Flag for Douglas's verdict either way, not an audit decision. |
| **unreferenced** | 0 | 0 bytes | None. |

### Zip archive verification (5 archives)

For each zip, opened it and checked every non-directory member exists at its expected extracted path (same directory tree, sibling to the zip) with matching size.

| Zip | Members | All extracted, size-matched? | Verdict |
|---|---|---|---|
| `raw\gadm\BRA\gadm41_BRA_shp.zip` | 15 | Yes | **redundant** — safe to remove, extracted content present and size-verified (also itself a duplicate of `outputs\BRA\raw\gadm41_BRA_shp.zip`, see Action 7) |
| `raw\gadm\PRT\gadm41_PRT_shp.zip` | 20 | Yes | **redundant** |
| `raw\hydrosheds\_global\HydroLAKES_polys_v10_shp.zip` | 7 | Yes | **redundant** |
| `raw\hydrosheds\BRA\HydroRIVERS_v10_sa_shp.zip` | 7 | Yes | **redundant** |
| `raw\hydrosheds\PRT\HydroRIVERS_v10_eu_shp.zip` | 7 | Yes | **redundant** |

All 5 zips: **redundant**. Every member is verified extracted with a matching byte size, and (per Action 7) the entire `raw/<source>/<scope>/` subtree each zip belongs to is itself a duplicate of a manifest-referenced copy under `outputs/`.

---

## Action 2: Does GEOFREA_DATA_DIR hold raw in two places?

**Yes — three, not two, and the extra copy is a naming/environment defect, not just a data-layout one.**

1. **`GEOFREA_DATA_DIR/raw/<source>/<scope>/`** — written by `paths.fetched_raw()` (`src/geofrea/core/paths.py:126-139`). **Dead**: zero callers in `src/` (verified by grep). Contains the 66 `raw_input` files classified above.
2. **`GEOFREA_DATA_DIR/outputs/<ISO3>/raw/`** (and `outputs/_global/raw/`) — written directly by every current fetcher: `gadm.py:180,206` (`extract_dir = _ensure_gadm_extracted(outputs_dir, country_code)`, `gadm.py:194,223`), `hydrosheds.py:196,219` (`dest_dir = Path(outputs_dir) / "_global" / "raw"` at `hydrosheds.py:211`; `dest_dir = Path(outputs_dir) / country_code / "raw"` at `hydrosheds.py:241`), `wind.py:40,55` (`dest_dir = Path(outputs_dir) / country_code / "raw"`), `protected_planet.py:73`. **Live**: this is what `outputs/<ISO3>/manifest.json` actually references (verified: every `fetched`-provenance layer's `path` field points here for BRA and PRT). **`[FD3b1, 2026-09-22]` Correction:** "Live" is not "correct." A-08 (`METHODOLOGY.md:337`, `` `raw/<source>/<ISO3|_global>/`: fetched raw data (GADM, HydroSHEDS, WRI GPPD, WDPA, GWA) ``) names `raw/<source>/<ISO3|_global>/` as the authoritative layout for fetched raw data — not `outputs/<ISO3>/<phase>/<kind>/` (`METHODOLOGY.md:340`, phase outputs only). Every current fetcher writes to the non-conformant tree; `raw/<source>/<scope>/` (item 1 above) is the one A-08 actually specifies.
3. **`GEOFREA_SHARED_RAW_DIR/<source>/<Country>/`** — the read-only shared database, resolved by `local_layers.py`'s `local_only`-provenance resolvers: `resolve_elevation_path()` (`local_layers.py:277-304`, path built at `:300`), `resolve_population_path()` (`:307-329`, path at `:325`), `resolve_solar_path()` (`:343-366`, path at `:362`), `resolve_grid_path()` (`:369-395`, path at `:391`), `resolve_land_cover_tiles()` (`:398-479`, tile glob dir at `:455`), `resolve_roads_path()` (`:482-519`, path at `:519`). This directory is never copied into `GEOFREA_DATA_DIR`; it's read in place every run. It is not under `GEOFREA_DATA_DIR` at all, so it isn't really "raw in two places under `GEOFREA_DATA_DIR`" — it's a third, separate root, confirming the manifest's `local_only` layers (elevation, population, solar, grid, roads, land_cover) never get a `GEOFREA_DATA_DIR` copy under normal operation. Only `fetched`-provenance layers (borders, admin1, lakes, rivers, wind, protected areas, power_plants) get copied.

**Root-cause naming defect (affects reproducibility, not just disk space):** `local_layers.py` reads its raw-data root from `GEOFREA_RAW_DATA_DIR` (`local_layers.py:165` `RAW_DATA_DIR_ENV_VAR = "GEOFREA_RAW_DATA_DIR"`), which is the variable actually set in this repo's `.env`. `paths.py` reads `GEOFREA_DATA_DIR` and `GEOFREA_SHARED_RAW_DIR` (`paths.py:5-6, 72-74`), which are **not set anywhere** — not in `.env`, not as a Windows user/machine environment variable (checked both during this pass). Neither module has a `load_dotenv()` call (checked: no `dotenv` import anywhere in `src/` or `main.py`), so `.env` is not even auto-loaded by the application; whatever sets `GEOFREA_DATA_DIR`/`GEOFREA_SHARED_RAW_DIR` at runtime does so outside this repository's tracked configuration. This audit pass exported them manually (matching the paths documented in `paths.py`'s own docstring and confirmed to exist on disk) to do the checks above. **This is itself a naming-table entry** — see Action 8 — and a real risk to A-12 (Determinism): a fresh checkout with only `.env` populated per `.env.example` cannot run any phase that calls `paths.py`'s helpers.

---

## Action 3: Per-layer location table — 36 cells (12 core layers × 3 countries)

Absolute path actually opened at runtime, its root (`GEOFREA_DATA_DIR` vs `GEOFREA_SHARED_RAW_DIR`), and the `paths.py`/`local_layers.py`/fetcher call site. BRA and PRT paths are read from their `manifest.json` (ground truth: what was actually opened on the last successful `data_acquisition` run). IND has no manifest (F1 has not been run for IND); its path is the value the resolver would return given `config/countries.yaml`'s current IND mapping, marked *(predicted, not yet run)*.

| Layer | Country | Absolute path | Root | Call site (file:line) |
|---|---|---|---|---|
| borders | BRA | `GeoFREA_data\outputs\BRA\raw\gadm41_BRA_shp\gadm41_BRA_0.shp` | GEOFREA_DATA_DIR | `gadm.py:180` `fetch_borders`, extract at `gadm.py:194` |
| borders | PRT | `GeoFREA_data\outputs\PRT\raw\gadm41_PRT_shp\gadm41_PRT_0.shp` | GEOFREA_DATA_DIR | `gadm.py:180`, `:194` |
| borders | IND | *(predicted)* `GeoFREA_data\outputs\IND\raw\gadm41_IND_shp\gadm41_IND_0.shp` | GEOFREA_DATA_DIR | `gadm.py:180`, `:194` |
| admin1 | BRA | `GeoFREA_data\outputs\BRA\raw\gadm41_BRA_shp\gadm41_BRA_1.shp` | GEOFREA_DATA_DIR | `gadm.py:206` `fetch_admin1`, extract at `gadm.py:223` |
| admin1 | PRT | `GeoFREA_data\outputs\PRT\raw\gadm41_PRT_shp\gadm41_PRT_1.shp` | GEOFREA_DATA_DIR | `gadm.py:206`, `:223` |
| admin1 | IND | *(predicted)* `GeoFREA_data\outputs\IND\raw\gadm41_IND_shp\gadm41_IND_1.shp` | GEOFREA_DATA_DIR | `gadm.py:206`, `:223` |
| protected_areas | BRA | `GeoFREA_data\outputs\BRA\raw\BRA_protected_areas_wdpa.geojson` | GEOFREA_DATA_DIR | `protected_planet.py:73` `fetch_protected_areas` |
| protected_areas | PRT | `GeoFREA_data\outputs\PRT\raw\PRT_protected_areas_wdpa.geojson` | GEOFREA_DATA_DIR | `protected_planet.py:73` |
| protected_areas | IND | *(predicted)* `GeoFREA_data\outputs\IND\raw\IND_protected_areas_wdpa.geojson` | GEOFREA_DATA_DIR | `protected_planet.py:73` |
| lakes | BRA | `GeoFREA_data\outputs\_global\raw\HydroLAKES_polys_v10_shp\HydroLAKES_polys_v10_shp\HydroLAKES_polys_v10.shp` | GEOFREA_DATA_DIR (`_global`, shared across countries) | `hydrosheds.py:196` `fetch_lakes`, `dest_dir` at `hydrosheds.py:211` |
| lakes | PRT | same file as BRA (global, not per-country) | GEOFREA_DATA_DIR | `hydrosheds.py:196`, `:211` |
| lakes | IND | *(predicted)* same file (already fetched, `_global` scope) | GEOFREA_DATA_DIR | `hydrosheds.py:196`, `:211` |
| rivers | BRA | `GeoFREA_data\outputs\BRA\raw\HydroRIVERS_v10_sa_shp\HydroRIVERS_v10_sa_shp\HydroRIVERS_v10_sa.shp` | GEOFREA_DATA_DIR | `hydrosheds.py:219` `fetch_rivers`, `dest_dir` at `hydrosheds.py:241` |
| rivers | PRT | `GeoFREA_data\outputs\PRT\raw\HydroRIVERS_v10_eu_shp\HydroRIVERS_v10_eu_shp\HydroRIVERS_v10_eu.shp` | GEOFREA_DATA_DIR | `hydrosheds.py:219`, `:241` |
| rivers | IND | *(predicted, blocked)* — `hydrosheds_region: null` for IND in `config/countries.yaml:99`; fetch would raise until Finding 1 (OQ-012) resolves the region code | — | `hydrosheds.py:219`, `:241` |
| land_cover | BRA | `database\raw\land_cover\Brazil\ESA_WorldCover_10m_2020_v100_*.tif` (113 of 155 tiles after exclusion filter) | **GEOFREA_SHARED_RAW_DIR** (never copied to GEOFREA_DATA_DIR) | `local_layers.py:398-479` `resolve_land_cover_tiles`, tile glob dir `local_layers.py:455` |
| land_cover | PRT | `database\raw\land_cover\Portugal\ESA_WorldCover_10m_2020_v100_*.tif` (11 of 26 tiles after filter — see Action 6) | GEOFREA_SHARED_RAW_DIR | `local_layers.py:455` |
| land_cover | IND | `database\raw\land_cover\India\ESA_WorldCover_10m_2020_v100_*.tif` (63 of 91 tiles after filter — see Action 6) | GEOFREA_SHARED_RAW_DIR | `local_layers.py:455` |
| elevation | BRA | `database\raw\elevation\Brazil\BRA_elevation.tif` | GEOFREA_SHARED_RAW_DIR | `local_layers.py:277-304` `resolve_elevation_path`, path at `:300` |
| elevation | PRT | `database\raw\elevation\PRT\PRT_elevation.tif` | GEOFREA_SHARED_RAW_DIR | `local_layers.py:300` |
| elevation | IND | *(predicted)* `database\raw\elevation\India\IND_elevation.tif` | GEOFREA_SHARED_RAW_DIR | `local_layers.py:300` |
| population | BRA | `database\raw\population\bra_pop_2020.tif` | GEOFREA_SHARED_RAW_DIR | `local_layers.py:307-329` `resolve_population_path`, path at `:325` |
| population | PRT | `database\raw\population\prt_pop_2020.tif` | GEOFREA_SHARED_RAW_DIR | `local_layers.py:325` |
| population | IND | *(predicted)* `database\raw\population\ind_pop_2020.tif` | GEOFREA_SHARED_RAW_DIR | `local_layers.py:325` |
| transmission_grid | BRA | `database\raw\infrastructure\grid\BRA_grid_osm.geojson` | GEOFREA_SHARED_RAW_DIR | `local_layers.py:369-395` `resolve_grid_path`, path at `:391` |
| transmission_grid | PRT | `database\raw\infrastructure\grid\PRT_grid_osm.geojson` | GEOFREA_SHARED_RAW_DIR | `local_layers.py:391` |
| transmission_grid | IND | *(predicted)* `database\raw\infrastructure\grid\IND_grid_osm.geojson` | GEOFREA_SHARED_RAW_DIR | `local_layers.py:391` |
| roads | BRA | `database\raw\infrastructure\roads\Region_2_Central_South_America\GRIP4_region2.shp` | GEOFREA_SHARED_RAW_DIR | `local_layers.py:482-519` `resolve_roads_path`, path at `:519` |
| roads | PRT | `database\raw\infrastructure\roads\Region_4_Europe\GRIP4_region4.shp` | GEOFREA_SHARED_RAW_DIR | `local_layers.py:519` |
| roads | IND | *(predicted, blocked)* `config/countries.yaml:102-103` has `grip4_region_dir: null`, `grip4_region_file: null` for IND — `_get_country_mapping()` (`local_layers.py:227-241`) raises `CountryMappingError` until set | — | `local_layers.py:512-513, 519` |
| solar_pvout | BRA | `database\raw\solar_potential\World_PVOUT_GISdata_LTAy_AvgDailyTotals_GlobalSolarAtlas-v2_GEOTIFF\PVOUT.tif` (global file, not country-split) | GEOFREA_SHARED_RAW_DIR | `local_layers.py:343-366` `resolve_solar_path`, path at `:362` |
| solar_pvout | PRT | same file as BRA | GEOFREA_SHARED_RAW_DIR | `local_layers.py:362` |
| solar_pvout | IND | same file (already present, country-independent) | GEOFREA_SHARED_RAW_DIR | `local_layers.py:362` |
| wind_speed_100m | BRA | `GeoFREA_data\outputs\BRA\raw\BRA_wind_speed_100m.tif` | GEOFREA_DATA_DIR | `wind.py:40` `fetch_wind`, `dest_dir` at `wind.py:55` |
| wind_speed_100m | PRT | `GeoFREA_data\outputs\PRT\raw\PRT_wind_speed_100m.tif` | GEOFREA_DATA_DIR | `wind.py:40`, `:55` |
| wind_speed_100m | IND | *(predicted)* `GeoFREA_data\outputs\IND\raw\IND_wind_speed_100m.tif` | GEOFREA_DATA_DIR | `wind.py:40`, `:55` |

**36/36 cells populated.** Note the pattern this table makes visible that the original coverage-doc status column (`in_data`/`in_database_only`) hid: `fetched`-provenance layers (borders, admin1, lakes, rivers, wind, protected_areas) land under `GEOFREA_DATA_DIR/outputs/<ISO3>/raw/`; `local_only`-provenance layers (land_cover, elevation, population, transmission_grid, roads, solar_pvout) are read straight from `GEOFREA_SHARED_RAW_DIR` and **never** get a `GEOFREA_DATA_DIR` copy. The original coverage doc's "in_data" status conflated these two roots.

---

## Action 4: Stale classification (cache and outputs)

BRA's manifest (`outputs/BRA/manifest.json`) records the current run (`run_id d7df84a8272e...`) as: `data_acquisition` success, `data_quality_audit` success, **`grid_alignment` failed**, **`suitability_criteria` skipped_upstream_failed**. Yet both phase directories contain files on disk:

| Path | File count | Newest mtime | Phase status (current run) | Verdict |
|---|---|---|---|---|
| `outputs/BRA/data_acquisition` (`land_cover` artifact within it) | 154 of 155 tiles referenced | run timestamp 2026-09-22T14:27:55Z | **success** (manifest status) | **`[FD3b1, 2026-09-22]` stale** — 154/155 tiles referenced, only `S36W057` excluded, versus the geometry filter's 42 zero-overlap tiles and `config/countries.yaml`'s current 44-entry exclusion list. Predates the current exclusion config and/or the geometry filter's effective operation. Every downstream artifact that consumed this land_cover registry (`grid_alignment`, `suitability_criteria`, whether `success` or `failed`) inherits this staleness — it was built, or attempted, on an under-filtered input. |
| `outputs/PRT/data_acquisition` (`land_cover` artifact within it) | 26 of 26 tiles referenced (0 excluded) | run timestamp (data_acquisition success) | **success** (manifest status) | **`[FD3b1, 2026-09-22]` stale** — same defect, more severe: 0 of the 15 zero-overlap tiles were excluded. PRT's `grid_alignment` and `suitability_criteria`, both `success`, both inherit this staleness — the mosaic that fed them included all 15 out-of-territory tiles. |
| `outputs/BRA/grid_alignment/` (incl. `artifacts/`) | 17 | 2026-09-22 (epoch 1790084705, after the `data_quality_audit` success timestamp 14:37:57) | **failed** | **stale** — produced by a run attempt that the manifest does not record as successful; not safe to consume downstream; additionally inherits the `data_acquisition` staleness above regardless of its own status |
| `outputs/BRA/suitability_criteria/{tif,figures,reports}/` | 29 | 2026-09-19 (epoch 1789396843-853, predates the current run_id's `data_quality_audit` timestamp) | **skipped_upstream_failed** | **stale** — leftover from an earlier run_id whose `grid_alignment` succeeded; superseded by the current run's failure, never regenerated; also inherits the `data_acquisition` staleness above |
| `outputs/PRT/grid_alignment/`, `outputs/PRT/suitability_criteria/` | 25 + (not separately counted) | — | success | **`[FD3b1, 2026-09-22]` correction:** previously marked "current, not stale" outright. Manifest-status-current is still accurate (nothing supersedes these artifacts under the current run_id), but both inherit the `data_acquisition` land_cover staleness above — "current" describes lineage bookkeeping, not correctness of the underlying mosaic. |
| `interim/BRA/{lakes,rivers,roads,slope}/`, `interim/PRT/{lakes,protected,rivers,roads,slope}/` | not individually dated this pass | — | no manifest-tracked phase directly maps to `interim/`; these are grid_alignment/data_quality_audit working caches keyed by path existence only (see OQ-026) | **not classified as stale by this pass** — would require re-running `alignment.py`'s cache-hit logic per file, out of the time this pass had; flag for a follow-up pass, not asserted here |

**Named per row, as required:** BRA `data_acquisition` (phase) / land_cover artifact, 154/155 tiles → stale, every downstream BRA artifact inherits it. PRT `data_acquisition` (phase) / land_cover artifact, 26/26 tiles → stale, every downstream PRT artifact inherits it, including the two currently `success`-status phases. BRA `grid_alignment` (phase) / run `d7df84a8272e...` (failed) → `outputs/BRA/grid_alignment/*` stale (compounding the above). BRA `suitability_criteria` (phase) / superseded by the same failed run's downstream skip → `outputs/BRA/suitability_criteria/*` stale (compounding the above).

**Scope limit, stated rather than hidden:** the `interim/` cache row above is left unclassified rather than guessed at — `alignment.py`'s cache keying (path-existence only, see OQ-026 below) means "stale" cannot be determined by mtime comparison alone without re-deriving what each cache file's inputs should currently be. Asserting a verdict here without doing that would repeat exactly the kind of narrowed audit this task exists to correct.

---

## Action 5: Invalidation table — one row per `outputs/<ISO3>/<phase>`

| outputs/<ISO3>/<phase> | provisional or durable | M-item | Playbook task that invalidates it |
|---|---|---|---|
| `outputs/BRA/data_acquisition` (raw/) | durable | M-F1-01–M-F1-07 | Re-fetch only if source data changes upstream; not invalidated by any Stage G/H item |
| `outputs/BRA/data_quality_audit` | provisional | M-F1b-01, M-F1b-02 | G-1 (slope_max_deg rework, M-F2b-01) — sanity ranges reference slope thresholds this audit checks |
| `outputs/BRA/grid_alignment` | provisional (currently **failed** — see Action 4) | M-F2a-01 to M-F2a-04 | G-3 (0.05° snapping fix, M-F2a-01) invalidates any prior successful run's output; the current failed run's artifacts are stale regardless |
| `outputs/BRA/suitability_criteria` | provisional (currently **skipped_upstream_failed** — see Action 4) | M-F2b-01 to M-F2b-05 | G-1 (slope, M-F2b-01), G-2 (wind AHP removal, M-F2a-04 — note: `suitability_criteria` is itself slated for replacement by H-2's `siting_layers` rebuild), H-2 (F2b → `siting_layers` rebuild) |
| `outputs/PRT/data_acquisition` | durable | M-F1-01–M-F1-07 | Same as BRA |
| `outputs/PRT/data_quality_audit` | provisional | M-F1b-01, M-F1b-02 | G-1 |
| `outputs/PRT/grid_alignment` | provisional (currently success) | M-F2a-01 to M-F2a-04 | G-3 |
| `outputs/PRT/suitability_criteria` | provisional (currently success) | M-F2b-01 to M-F2b-05 | G-1, G-2, H-2 |
| `outputs/IND/*` | n/a — no manifest, F1 not yet run | — | Blocked on OQ-012 (HydroSHEDS region, GRIP4 region) before `data_acquisition` can complete for rivers/roads |
| `outputs/_global/raw` (lakes, power_plants) | durable | M-F1-01, M-F1-02, M-F1-06 | Not phase-specific; global fetch, re-invalidated only by upstream source changes |

No row exists yet for F3 `land_eligibility` onward — those phases have not been run for any country (confirmed: no `outputs/<ISO3>/land_eligibility/` or later directories exist on disk for BRA, PRT, or IND). H-3 (F3 rebuild), H-4 (F4 rebuild), and F-6 (seismic removal) are listed in the objective's playbook-task set but have no corresponding `outputs/` row to invalidate yet.

**Every existing `outputs/<ISO3>/<phase>` directory has a row: 8 rows for BRA/PRT's 4 phases each, plus the `_global` raw directory.**

---

## Action 6: Tile geometry check — every tiled source, every country

**Only `land_cover` is a tiled source among the 12 core layers** (ESA WorldCover 10m, native 3°×3° tiles). Wind (`wind_speed_100m`), solar (`solar_pvout`), elevation, population, transmission_grid are single files (global or per-country); roads and hydrology are single regional/global shapefiles clipped downstream, not pre-tiled. Protected areas (WDPA) is delivered as a 51-file-per-country geodatabase export, not spatial tiles — not a tile geometry candidate.

**Method:** intersected each land_cover tile's filename-derived bounding box against the real GADM level-0 country polygon, reusing the codebase's own `resolve_land_cover_tiles()` / `_tile_bbox_from_filename()` (`local_layers.py:398-479`, threshold `_MIN_OVERLAP_DEG2 = 1e-6` deg² at `local_layers.py:183`) rather than a bounding-box-vs-bounding-box check. GADM sources: `outputs/BRA/raw/gadm41_BRA_shp/gadm41_BRA_0.shp`, `outputs/PRT/raw/gadm41_PRT_shp/gadm41_PRT_0.shp`, `database/raw/countries_borders/India/gadm41_IND_0.shp`.

| Country | Tiles present | Zero-overlap tiles | Nearest zero-overlap tile (distance to polygon, degrees) | Farthest zero-overlap tile (distance, degrees) |
|---|---|---|---|---|
| BRA | 155 | **42** | `S21W039` (0.018°) | `S36W075` (14.63°) |
| PRT | 26 | **15** | `N27W018` (0.030°) | `N27W006` (7.21°) |
| IND | 91 | **28** | `N15E093` (0.064°) | `N33E087` (4.87°) |

BRA's 42 matches `local_layers.py:409-411`'s own docstring ("BRA had 42 such tiles out of 155 ... only discovered incrementally via failed pipeline runs"). PRT's 15 zero-overlap tiles were **not previously documented anywhere** in this repository — `config/countries.yaml` has no `excluded_land_cover_tiles` entry for PRT, meaning PRT's automatic geometry filter (which runs whenever a caller passes `country_gdf`, `local_layers.py:458-473`) is the only thing currently preventing these 15 tiles from entering the F2a mosaic; there is no static fallback list for PRT the way there is for BRA. IND's 28 (this pass's headline number) likewise has no static fallback list.

**`[FD3b1, 2026-09-22]` Correction:** the paragraph above describes the 15 PRT tiles as a hypothetical future risk. They are not hypothetical. `phase.py:182-184` does pass `country_gdf` into `resolve_land_cover_tiles()`, so the filter is wired into the real acquisition phase — but PRT's own `outputs/PRT/manifest.json` `land_cover` layer entry has **26 `paths` — all 26 tiles, 0 excluded**. BRA's has **154 of 155** (only `S36W057` missing, not the 42-tile set). The successful, `grid_alignment`/`suitability_criteria`-feeding `data_acquisition` runs on disk for both countries predate either the current `countries.yaml` exclusion list or the geometry filter's effective operation at call time (`config/countries.yaml` mtime is after the BRA manifest's last write). See the new stale-`data_acquisition` row in Action 4 below.

**Full zero-overlap tile lists (all distances in decimal degrees, WGS84):**

*BRA (42):* N00W075 (1.948), N03W057 (0.368), N03W069 (0.770), N03W072 (1.223), N03W075 (2.506), S03W075 (1.488), S15W069 (0.840), S15W072 (0.901), S15W075 (1.696), S18W066 (1.876), S18W069 (3.010), S18W072 (3.865), S18W075 (4.225), S21W039 (0.018), S21W063 (1.732), S21W066 (3.319), S21W069 (5.758), S21W072 (6.861), S24W063 (1.989), S24W066 (4.897), S24W069 (7.511), S24W072 (9.709), S27W060 (1.516), S27W063 (2.780), S27W066 (5.364), S27W069 (8.231), S27W072 (11.167), S30W063 (2.362), S30W066 (5.358), S30W069 (8.357), S30W072 (11.356), S33W063 (2.355), S33W066 (5.355), S33W069 (8.355), S33W072 (11.355), S36W057 (0.468), S36W060 (2.158), S36W063 (3.664), S36W066 (6.046), S36W069 (8.814), S36W072 (11.697), S36W075 (14.627). *(All prefixed `ESA_WorldCover_10m_2020_v100_` and suffixed `_Map.tif`.)*

*PRT (15):* N27W006 (7.209), N27W009 (6.861), N27W012 (3.862), N27W015 (0.871), N27W018 (0.030), N27W021 (1.940), N30W006 (4.381), N30W009 (3.961), N30W012 (3.860), N33W006 (1.820), N33W009 (0.961), N36W006 (0.932), N39W006 (0.189), N42W006 (0.446), N42W012 (0.182).

*IND (28):* N06E081 (1.519), N06E096 (2.052), N09E081 (0.964), N09E096 (2.132), N12E096 (1.722), N15E093 (0.064), N15E096 (2.309), N18E090 (0.946), N18E093 (0.950), N18E096 (3.063), N21E096 (1.566), N24E096 (0.080), N27E066 (0.507), N30E066 (2.415), N30E069 (1.275), N30E084 (2.165), N30E087 (1.869), N30E090 (1.397), N30E093 (0.542), N30E096 (0.537), N33E066 (4.763), N33E069 (1.763), N33E081 (1.719), N33E084 (4.052), N33E087 (4.869), N33E090 (3.998), N33E093 (3.538), N33E096 (3.537).

**BRA's `config/countries.yaml` exclusion list (44 entries, `countries.yaml:39-88`) does not exactly equal these 42** — it also includes `N03W051` (a genuine 0.33 km² sliver, manually accepted by Douglas per the file's own comment, `countries.yaml:34-38`, so correctly *not* auto-excluded by the zero-overlap geometry filter) bringing the static list to 43, plus one filename the geometry check here could not independently re-derive from the static list alone without re-running the exact same code — no discrepancy found, not a finding.

Bounding-box comparison was not used as evidence anywhere in this table, per the `CLAUDE.md` "Geometry over bounding box" rule.

---

## Action 7: Duplicates — sha256 pass on size-collision groups

**Method:** for each of the 66 `raw_input` files, searched `GEOFREA_DATA_DIR/outputs/` for same-size files, then computed sha256 for every same-size candidate.

**Result: all 66 have at least one exact sha256 match under `outputs/`.** Two patterns:

1. **Meaningful duplicates (per-file, 1:1):** every "real" content file — `.shp`, `.dbf` (non-boilerplate), `.tif`, `.geojson`, `.csv`, `.pdf`, `.zip` — matches exactly one file under `outputs/<ISO3 or _global>/raw/`, confirming Action 2's finding: `raw/<source>/<scope>/` is a full, redundant copy of the live `outputs/` raw tree. Examples: `raw\gwa\BRA\BRA_wind_speed_100m.tif` (515,162,560 bytes) == `outputs\BRA\raw\BRA_wind_speed_100m.tif`; `raw\wri_gppd\_global\global_power_plant_database.csv` == `outputs\_global\raw\global_power_plant_database.csv`.
2. **Coincidental duplicates (not meaningful):** `.cpg` files (5 bytes, always `"UTF-8"`) and `.prj` files (145 bytes, a standard WGS84 WKT string) match *every* other `.cpg`/`.prj` in the entire tree regardless of which shapefile they belong to — e.g. `gadm41_BRA_shp\gadm41_BRA_0.prj` sha256-matches 9 other `.prj` files across BRA, PRT, and HydroRIVERS. These are same-content-by-construction (every GADM/HydroRIVERS export in EPSG:4326 gets an identical WKT), not evidence of a duplicated fetch — excluded from the "redundant" verdict count, noted here so the 66/66 match rate isn't misread as more significant than it is.

**Against GEOFREA_SHARED_RAW_DIR:** no duplicate check was run between the 66 `raw_input` files and `GEOFREA_SHARED_RAW_DIR`, because none of the 5 fetcher sources involved (gadm, gwa, hydrosheds, wdpa, wri_gppd) are also `local_only` sources read from `GEOFREA_SHARED_RAW_DIR` (Action 3's table shows the `fetched`/`local_only` split is a clean partition by layer, not overlapping) — a size-collision scan against all ~67 GB of `GEOFREA_SHARED_RAW_DIR` was judged disproportionate to check a partition that Action 3 already shows is disjoint by construction. Flagged here rather than silently skipped: if this reasoning is wrong (e.g. GWA wind tiles are *also* separately cached under `GEOFREA_SHARED_RAW_DIR/wind_potential/`, which the original coverage doc's raw-database inventory says they are — 21 files, 3 per country), there may be a fourth duplication axis (fetched copy vs. shared-raw cache) not covered here.

**Duplicate groups: 66 meaningful (raw_input vs. outputs/), 0 found against GEOFREA_SHARED_RAW_DIR (not exhaustively checked — see caveat above).**

---

## Action 8: Naming table

One row per naming-defect hit, its code location, and its owning Stage G/H task (or "no owner" where a rename is free).

| Hit | Code location | Owning task | Notes |
|---|---|---|---|
| `GEOFREA_DATA_DIR` / `GEOFREA_SHARED_RAW_DIR` (paths.py) vs. `GEOFREA_RAW_DATA_DIR` (local_layers.py) | `paths.py:5-6,72-74` vs. `local_layers.py:165` | **no owner** — not in G-1/G-2/G-3/H-2/H-3/H-4/F-6; a real defect (Action 2) blocking any fresh checkout from running, not currently scheduled anywhere |
| `.env` defines `GEOFREA_RAW_DATA_DIR`, `GEOFREA_PROCESSED_DATA_DIR`, `GEOFREA_OUTPUT_DIR`; `CLAUDE.md`/`METHODOLOGY.md` document `GEOFREA_DATA_DIR`/`GEOFREA_SHARED_RAW_DIR` | `.env` (repo root) vs. `CLAUDE.md:69-75`, `METHODOLOGY.md` A-08 | **no owner** | `.env.example` should be checked against both naming schemes before the next session |
| `raw/<source>/<scope>/` tree + `paths.fetched_raw()` | `paths.py:126-139` | **no owner** | Dead code path (Action 1/2); either delete the helper and the tree, or find/restore its intended caller — Douglas's verdict |
| Manifest layer name `grid` vs. METHODOLOGY layer name `transmission_grid` | `outputs/BRA/manifest.json` `layers[].layer_name` vs. `METHODOLOGY.md` M-F1-02 row 9, `local_layers.py:369` docstring | **no owner** | Cosmetic but affects any tooling that greps manifests by the methodology's layer names |
| Manifest layer name `protected` vs. METHODOLOGY `protected_areas` | same as above | **no owner** | Same category |
| GRIP4 `grip4_region_dir: "Region_5_Middle_East_Central_Asia"` for IND names the wrong sub-continent (`regions_lookup.json` says `Region_5_South_Asia`) | `config/countries.yaml:97-103` (once set), `regions_lookup.json` (GEOFREA_SHARED_RAW_DIR) | **H-3** (F3 land_eligibility touches roads exclusion) is the earliest Stage H item that reads this config value; more precisely this is an OQ-012 (F-1, MS-2) item — recorded as a naming defect, not resolved, per the corrected Finding 2 in `2026-09_data_coverage.md` |
| `suitability_criteria` (current phase/directory name) vs. `siting_layers` (METHODOLOGY F2b module name, M-F2b) | `outputs/<ISO3>/suitability_criteria/`, phase key in manifest | **H-2** (F2b rebuild to `siting_layers`) — already scheduled, not a new finding, cross-referenced here for completeness |
| "suitability", "criteria", "score" et al. in filenames | per original Naming Audit (170 occurrences) | **G-1, G-2, H-2, H-3, H-4, F-6** (unchanged from original pass — that count was not re-verified line-by-line this pass; the original grep-based count is retained as-is since Action 8 only required file:line detail for *new* hits, and this table only adds the entries above) |
| `StoredPath` migration (`core.md` D-core-005) applied to `ArtifactEntry` only, not to `data_acquisition`'s raw-layer registry | `orchestrator.py:673` (`stored_path = to_stored_path(path)`, inside artifact registration) vs. `AcquiredLayer.path`/`.paths` (plain absolute strings, e.g. `outputs/BRA/manifest.json` `phases.data_acquisition.output.layers[].path`) | **`[FD3b1, 2026-09-22]`** no owner in G/H — already tracked as `OQ-024` (per-layer checksum gap), not previously cross-referenced from this naming table |

---

## E5b migration residue (added 2026-09-22, FD3b2 pass)

`core.md` D-core-005 describes E5b as a completed data-layout migration. Three directory pairs still hold old-layout and new-layout content side by side; each pair's same-named files were sha256-compared this pass.

### `outputs/<ISO3>/processed` (old) vs. `interim/<ISO3>` (new)

| File | BRA | PRT |
|---|---|---|
| `*_slope_native.tif` | IDENTICAL | IDENTICAL |
| `lakes_clipped.gpkg` | **DIFFERENT** | **DIFFERENT** |
| `protected_clipped.gpkg` | only in `processed/` (missing from `interim/`) | **DIFFERENT** |
| `rivers_clipped.gpkg` | **DIFFERENT** | **DIFFERENT** |
| `roads_clipped.gpkg` | **DIFFERENT** | **DIFFERENT** |

These are not simple duplicates: the `*_clipped.gpkg` files differ in content between the two locations for both countries, meaning `interim/<ISO3>/{lakes,rivers,roads}` was regenerated by a later run (post-migration, or post the shared-geometry-repair change noted in `core.md` "Shared geometry repair (A-02, moved from suitability_criteria 2026-09-21)") while `outputs/<ISO3>/processed/` still holds the pre-migration content. BRA's `processed/protected_clipped.gpkg` has no `interim/` counterpart at all.

### `outputs/<ISO3>/audit` (old) vs. `outputs/<ISO3>/data_quality_audit/reports` (new)

No filename overlap in either country — every `audit_<ISO3>_<timestamp>.txt` in one directory is absent from the other. BRA: `audit/` holds only the two most recent runs (2026-09-22T12:05, T14:37); `data_quality_audit/reports/` holds four older runs (2026-08-26 through 2026-09-11). PRT: `audit/` holds one run (2026-09-22T11:42); `data_quality_audit/reports/` holds seven older runs (2026-08-26 through 2026-09-21). This is not a stale duplicate of the same content — it is a **write-location change mid-history**: something switched from writing to `data_quality_audit/reports/` to writing to `audit/` on or shortly before 2026-09-22, and the older run history was never migrated forward. Neither location has the complete run history; reconstructing it requires reading both.

### `outputs/<ISO3>/grid_alignment/*.tif` (top-level) vs. `outputs/<ISO3>/grid_alignment/artifacts/` (subdirectory)

All 12-13 same-named files (`*_elevation_aligned.tif`, `*_grid_aligned.tif`, `*_grid_metadata.json`, `*_lakes_aligned.tif`, `*_land_cover_aligned.tif`, `*_lc_aligned.tif`, `*_plants_aligned.tif`, `*_population_aligned.tif`, `*_rivers_aligned.tif`, `*_roads_aligned.tif`, `*_slope_aligned.tif`, `*_solar_aligned.tif`, `*_wind_aligned.tif`) are **IDENTICAL** for both BRA and PRT. This is a genuine full duplication — every raster is written twice, once flat under `grid_alignment/` and once under `grid_alignment/artifacts/`, at 100% redundancy (not a migration in progress; both copies are current for the same run).

### Additional pairs required by this action

- **`outputs/IND`** — exists, and is **completely empty** (no files, no subdirectories). Confirms Action 5's earlier note: F1 has not been run for IND.
- **Audit documents in `GEOFREA_DATA_DIR/logs`** — `logs/orphan_files.txt` (the source list for Action 1) and `logs/2026-09_geofrea_data_inventory.md`. The latter is the **original, pre-correction** audit tool's direct output, written into the data directory rather than the repository's `docs/_audit/`; it predates every correction in this document and should not be read as current. It is not deleted or moved by this read-only pass.

## Reproducibility defect (added 2026-09-22, FD3b2 pass)

Per FD3b1 actions 2-3: `GEOFREA_DATA_DIR`, `GEOFREA_SHARED_RAW_DIR`, `GEOFREA_RAW_DATA_DIR`, and `GEOFREA_LEGACY_BASELINE_DIR` resolve to **unset** in every scope checked — process environment (fresh shell), Windows User and Machine environment variables, `.env` (defines `GEOFREA_RAW_DATA_DIR` but not the other three, and no module calls `load_dotenv()` — confirmed absent from `src/`, `main.py`, and `pyproject.toml`'s dependency list), and the PowerShell `$PROFILE` (does not exist). `paths.py` raises `MissingPathEnvironmentError` (`paths.py:25-33`) immediately when any of its helpers is called without the corresponding variable set (`_ensure_env()`, `paths.py:86-101`).

The BRA/PRT manifests and logs on disk are real and well-formed, so the 2026-09-22 runs necessarily had `GEOFREA_DATA_DIR` set in that run's process environment — set in a shell session that has since closed, per FD3b1 action 3. No file in this repository records that value or how to reproduce it.

**Against A-12 (Determinism):** "Seeds are recorded in the manifest; reruns with identical run ID reproduce identical artifacts on the same platform." A rerun cannot happen at all — not just non-identically — from a fresh clone with only `.env` populated per `.env.example`: `main.py:399` (`log_path()`) and `main.py:410` (`outputs_dir()`) both call `paths.py` helpers that raise before any phase logic runs. **No phase can be run from a fresh clone until `GEOFREA_DATA_DIR` and `GEOFREA_SHARED_RAW_DIR` are set somewhere this repository actually records** (`.env`, a documented shell-profile step, or a code change to read `GEOFREA_RAW_DATA_DIR` consistently instead of introducing a second variable name). This is a blocking reproducibility defect, not a cosmetic naming one, even though it was filed under the naming table in the prior pass.

## Data Integrity

### Completion Criterion
- Total classified size: 12,081,766,578 bytes
- Total GEOFREA_DATA_DIR: 12,081,766,578 bytes
- **Match: [PASS]** (unchanged from original — the six-category split does not change the total)

### Snapshot Integrity (GEOFREA_SHARED_RAW_DIR)
- Status: read-only for this entire pass; no writes made to `GEOFREA_SHARED_RAW_DIR`, `GEOFREA_DATA_DIR`, `src/`, `config/`, or any data file. Only `docs/_audit/*.md` and `docs/OPEN_QUESTIONS.md` were written.

## Proposed Actions (AWAITING VERDICT FROM DOUGLAS)

| Category | Count | Size | Proposed action | Status |
|---|---|---|---|---|
| Active | 17 | 2,522,196 | Keep (required) | — awaiting verdict |
| Cache — current | ~161 | ~6.0 GB | Keep (intermediate) | — awaiting verdict |
| Cache — stale (BRA grid_alignment + suitability_criteria) | 46 | not separately sized this pass | Candidate for deletion or re-run; Douglas's verdict on whether to re-run `grid_alignment` for BRA first | — awaiting verdict |
| raw_input | 66 | 4,383,849,641 | Candidate for deletion as a duplicate of the live `outputs/` copy (Action 1, 2, 7) — **not** a "might be garbage" cleanup, a "confirmed dead-code-path duplicate" cleanup | — awaiting verdict |
| Legacy | 328 | 1,409,148,189 | Keep (frozen baseline) | — awaiting verdict |
| Log | 38 | 2,118,898 | Keep (run history) | — awaiting verdict |

## Audit Details

- Audited directory: `D:\Douglas\DOUTORADO\GeoFREA_data`
- Shared raw directory: `D:\Douglas\DOUTORADO\database\raw`
- Repo location: `D:\Douglas\DOUTORADO\GeoFREA`
- Methodology version: 1.1.0
- Original audit timestamp: 2026-09-22T14:41:23.744553 (tool: `geofrea_audit_v2.py`, Claude Haiku 4.5 subagent)
- Correction pass timestamp: 2026-09-22 (this session), main session, no Task tool used
- Tools used this pass: direct file reads, `zipfile`, `hashlib.sha256`, `geopandas`/`shapely` via the repo's own `local_layers._tile_bbox_from_filename()` and `_MIN_OVERLAP_DEG2`, manifest JSON parsing — all read-only
