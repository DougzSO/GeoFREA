# Data Coverage Audit — 2026-09-22

> **Correction note (2026-09-22, this pass):** The original version of this document (auditor: "Claude Haiku 4.5 (Agent)", a low-effort subagent) got three things wrong or silently narrowed:
> 1. **Finding 3 (IND land cover)** claimed "no manual exclusion list required... no tiles outside India's bounding box detected" based on a bounding-box eyeball check. A real GADM-polygon intersection (reusing the codebase's own `resolve_land_cover_tiles()` / `_tile_bbox_from_filename()` in `src/geofrea/data_acquisition/local_layers.py:398-479`) shows **28 of 91 IND tiles have zero overlap with the real IND polygon**. This section is replaced below.
> 2. **Manifest status** was reported as `unknown` for both BRA and PRT even though `outputs/<ISO3>/manifest.json` records a real per-phase status. Replaced below with the actual values (BRA: `grid_alignment` = `failed`, `suitability_criteria` = `skipped_upstream_failed`; PRT: all phases `success`).
> 3. **GRIP4 (Finding 2)** proposed writing the on-disk directory name `Region_5_Middle_East_Central_Asia` into `config/countries.yaml` as if that were a resolution, while noting in the same paragraph that `regions_lookup.json` calls it `Region_5_South_Asia`. Keeping the on-disk name in config is the only workable action (renaming a directory GRIP4 fetchers may re-derive is riskier), but it is recorded here as an accepted **naming defect**, not a resolution — see the corrected Finding 2 and the naming table in the companion inventory document.
>
> Everything else in this document (the 90-cell status matrix, the raw database source inventory, the OQ-011/OQ-012/OQ-025 write-ups not named above) was re-checked against `config/countries.yaml`, the BRA/PRT manifests, and `local_layers.py` during this pass and left in place where it held up; only the three items above are changed.
>
> **Correction note (2026-09-22, FD3b1/FD3b2 pass).** The "28 of 91" finding above (and the companion inventory document's zero-overlap counts for BRA/PRT) is a geometric fact about the tile files and the GADM polygon — it does not describe what the completed BRA/PRT pipeline runs on disk actually consumed. Checked directly against the manifests: **PRT's `data_acquisition` land_cover artifact references all 26 tiles (0 excluded)**; **BRA's references 154 of 155 (only `S36W057` excluded, not the 42-tile geometry set)**. The `success`-status `grid_alignment`/`suitability_criteria` artifacts for both countries were built on these unfiltered/under-filtered mosaics — see "Manifest Status" below and the new `data_acquisition` stale rows in the companion inventory document's Action 4. Also corrected: Finding 2's "naming defect" framing understated it — `resolve_land_cover_tiles()` genuinely receives `country_gdf` at its real call site (`phase.py:182-184`), so the geometry filter *is* wired into production; it simply did not exclude anything in the runs currently on disk, most likely because those runs predate the current `config/countries.yaml` exclusion list (file mtime after the BRA manifest's last write).

**Audit Scope:** Complete layer x country data availability mapping for BRA, PRT, IND
**Execution Date:** 2026-09-22 (original); corrected 2026-09-22 (this pass)
**Status:** Complete. All 90 layer x country matrix cells (30 layers × 3 countries) populated with status and task/OQ mapping. Corrected sections below supersede the original text.

---

## Executive Summary

This audit maps every layer specified in METHODOLOGY M-F1-02 through M-F1-07 to its current location across Brazil, Portugal, and India. It identifies gaps and assigns each to an implementation task (F-1 through F-8, F1b, F7b, E1) or a new Open Question.

**Key Findings (corrected):**

- **In GEOFREA_DATA_DIR:** BRA/PRT each have 12 core layers accessible; IND has 7. See the per-layer location table in the companion inventory document (`2026-09_geofrea_data_inventory.md`, Action 3) for the actual absolute path opened at runtime and its `paths.py`/`local_layers.py` call site for each of the 36 (layer × country) cells — this replaces the `in_data`/`in_database_only` status column below, which marked `GEOFREA_SHARED_RAW_DIR` paths as `in_data` without distinguishing them from copies actually under `GEOFREA_DATA_DIR`.
- **In GEOFREA_SHARED_RAW_DIR (database-only):** IND has 5 layer sources (borders, admin1, protected_areas, lakes, rivers) cached but not yet copied to GEOFREA_DATA_DIR; BRA/PRT have no database-only entries for these five, but BOTH countries' land_cover, elevation, population, transmission_grid, roads, solar_pvout, and wind_speed_100m layers are read directly from `GEOFREA_SHARED_RAW_DIR` at runtime (see local-only resolvers in `src/geofrea/data_acquisition/local_layers.py`), not copied into `GEOFREA_DATA_DIR` at all under normal operation.
- **Fetchable:** GEM trackers (alternative: WRI GPPD). Fetcher exists in `power_plants.py`; live cache download not yet executed.
- **Absent—Not Implemented:** GWA Weibull A, Weibull k, air-density at all heights (100/150/200m); CMIP6 monthly and daily; ERA5 gust. These require new fetchers (MS-2 and MS-7).
- **IND land cover (corrected):** 91 tiles present on disk; **28 have zero geometric overlap with the real IND GADM polygon** and must not enter the F2a mosaic. See the corrected Finding 3.
- **OQ-012 Resolution:** GRIP4 region for IND is confirmed as `Region_5_South_Asia` per `regions_lookup.json`, though the on-disk directory is named `Region_5_Middle_East_Central_Asia`; HydroSHEDS region code for South Asia remains undefined (config: null).

**Matrix completion:** 90 cells, 100% populated.

---

## Required Layers (Action 1: Complete Layer Specification)

### Core 12 Layers (M-F1-02)

| # | Layer | Source | Expected Resolution | Version/Notes |
|---|---|---|---|---|
| 1 | borders (country) | GADM 4.1 | 1:10m vector | Level 0; local-first with checksum (M-F1-07) |
| 2 | admin1 (state/province) | GADM 4.1 | 1:10m vector | Level 1; same provenance as borders |
| 3 | protected_areas | WDPA via Protected Planet API v4 | 1:10m+ vector | IUCN category subset per M-F2b-01 |
| 4 | lakes | HydroSHEDS (HydroLAKES v10) | ~1:10m vector | Global dataset; clipped per country |
| 5 | rivers | HydroSHEDS (HydroRIVERS v10) | ~1:10m vector | Per-region shapefile; clipped per country |
| 6 | land_cover | ESA WorldCover 10m v100 | 10m raster (native 3x3°) | 2020 classification; per-country tiles. **Tiled source — see geometry check in the inventory doc.** |
| 7 | elevation | Copernicus DEM 30m | 30m raster (native 1x1°) | 2021+ release; geodesic slope derived |
| 8 | population | WorldPop 2020 | 100m raster (native) | Constrained UN-adjusted; per-country |
| 9 | transmission_grid | OSM Overpass GeoJSON | Vector, country-specific | Per-country extract; voltage optional (OQ-011) |
| 10 | roads | GRIP4 (Global Roads Inventory Project) | Vector, ~1:100k | Per-region shapefile; matched to country via lookup |
| 11 | solar_pvout | Global Solar Atlas long-term average | 0.05° raster | Daily kWh/kWp/day (M-F5-02 requirement) |
| 12 | wind_speed_100m | Global Wind Atlas (GWA) | 0.2° raster, 100m hub height | One height only; additional heights M-F1-03 |

(Wind Weibull/air-density heights, CMIP6, ERA5, and GEM trackers layers 13-30 are unchanged from the original audit and not repeated here; see git history of this file for that text if needed.)

---

## Layer × Country Status Matrix (Action 2)

Unchanged from the original pass for the 18 non-core-12 rows (wind Weibull/air-density/other heights, CMIP6, ERA5, GEM trackers) — those remain `absent`/`fetchable` as originally recorded, still mapped to tasks F-2/F-4/F-5/OQ-025. The core-12 rows are superseded by the per-layer, per-country, file:line table in `2026-09_geofrea_data_inventory.md` Action 3, which replaces the `in_data` status used here (that status conflated "readable at runtime from GEOFREA_SHARED_RAW_DIR" with "copied into GEOFREA_DATA_DIR").

---

## OQ-012 Investigation: India Data Wiring (Action 4)

### Finding 1: HydroSHEDS Region Code for South Asia

**Status:** unchanged — still pending. `IND.hydrosheds_region: null` in `config/countries.yaml`; HydroRIVERS v10 on disk is the global shapefile with no per-region split confirmed. Left open per the original recommendation: consult HydroSHEDS v10 documentation before setting a code.

---

### Finding 2: GRIP4 Region Mapping for India (corrected)

**Status:** DATA LOCATION CONFIRMED. Directory-name mismatch recorded as a **naming defect**, not resolved by config.

**Evidence:**

From `GEOFREA_SHARED_RAW_DIR/infrastructure/roads/regions_lookup.json`:
```
Region_5_South_Asia: [AFG, BGD, BTN, IND, IRN, NPL, PAK, LKA]
```

Directory actually on disk: `GEOFREA_SHARED_RAW_DIR/infrastructure/roads/Region_5_Middle_East_Central_Asia/` (contains `GRIP4_region5.shp` and siblings).

**Correction:** The original document proposed writing `grip4_region_dir: "Region_5_Middle_East_Central_Asia"` into `config/countries.yaml` and called this "resolved." That is a workaround, not a resolution — it makes the pipeline read the correct file, but the config value still names the wrong region and will mislead anyone reading `countries.yaml` without this note. It is recorded here, and in the naming table of the companion inventory document, as an accepted **naming defect**: the on-disk directory was mislabeled at some earlier point (by whoever laid out `GEOFREA_SHARED_RAW_DIR`, not by GeoFREA code), `regions_lookup.json` is authoritative and correct, and renaming the directory itself is out of scope for this audit (read-only location per `paths.py` `ensure_writable()`; `GEOFREA_SHARED_RAW_DIR` is never written to by GeoFREA — see `docs/METHODOLOGY.md` read-only locations list). No `src/`, `config/`, or data file is edited by this audit pass.

---

### Finding 3: Land Cover Tiles for India (corrected — supersedes the original "COMPLETE, no action required")

**Status:** ACTION REQUIRED before F2a mosaicking for IND.

**Method:** Reused the codebase's own geometry filter, `resolve_land_cover_tiles()` in `src/geofrea/data_acquisition/local_layers.py:398-479`, which intersects each tile's filename-derived bounding box (`_tile_bbox_from_filename()`, same file) against the real GADM country polygon (`country_geom.intersection(bbox).area < _MIN_OVERLAP_DEG2`, threshold `1e-6` deg², line 465) — not the country's own bounding box. Ran this against the real GADM level-0 IND polygon (`GEOFREA_SHARED_RAW_DIR/countries_borders/India/gadm41_IND_0.shp`) and the 91 tiles under `GEOFREA_SHARED_RAW_DIR/land_cover/India/`.

**Result:** **28 of 91 tiles have zero overlap** (intersection area exactly 0.0 deg²) with the real IND polygon. Full list, with each tile's distance in degrees to the IND polygon, in `2026-09_geofrea_data_inventory.md` Action 6 (Tile Geometry Check). Nearest zero-overlap tile: `ESA_WorldCover_10m_2020_v100_N15E093_Map.tif`, 0.064° from the border (Andaman/Nicobar-adjacent tile that just misses the mainland/island polygon at this bbox resolution). Farthest: `ESA_WorldCover_10m_2020_v100_N24E096_Map.tif` area, up to several degrees away in the Myanmar-border tiles.

**Correction of the withdrawn conclusion:** the original Finding 3 said "No tiles outside India's bounding box detected (consistent with the BRA audit's manual tile exclusion methodology)" and concluded "No manual exclusion list required for IND." Both statements are withdrawn. A bounding-box check cannot detect this — India's polygon has a highly non-rectangular border (the northeast states, the Andaman/Nicobar chain, the western Rajasthan/Pakistan border), so its bounding box is much larger than its territory, and 0.2°-3x3° WorldCover tiles that sit inside the bbox but outside the actual polygon (over Myanmar, Bangladesh, Pakistan, the Bay of Bengal, or the Arabian Sea) were never checked. This is the same class of error the BRA `excluded_land_cover_tiles` list in `config/countries.yaml` already exists to prevent for Brazil (42 of 155 BRA tiles, not the single `S36W057` tile the original inventory document's "Orphan File Examples" excerpt implied — see the corrected inventory document).

**Required action (not performed by this audit — read-only):** `config/countries.yaml`'s `IND` entry currently has no `excluded_land_cover_tiles` key. Per `local_layers.py:398-479`, the geometry filter runs automatically whenever `country_gdf` is passed by the caller, so IND does not strictly need a static exclusion list the way BRA's fallback list exists — but BRA's fallback list also carries one manually-accepted sliver tile (`N03W051`, real but negligible overlap) that the geometry filter deliberately does not auto-exclude. IND has no equivalent manual review yet. Douglas should decide, when F1 is run for IND, whether the automatic geometry filter alone is sufficient or whether any IND tile needs the same manual-judgment treatment as BRA's `N03W051`.

---

### Finding 4: IND Population Data

Unchanged from the original: `GEOFREA_SHARED_RAW_DIR/population/ind_pop_2020.tif` present, ready for F2b.

---

### Finding 5: IND Transmission Grid Data

Unchanged from the original: `GEOFREA_SHARED_RAW_DIR/infrastructure/grid/IND_grid_osm.geojson` present, ready for F2b. OQ-011 (voltage filtering) still applies.

---

### OQ-012 Summary Table (corrected)

| Item | Status | Finding | Action |
|---|---|---|---|
| **HydroSHEDS region code** | PENDING | unchanged | Consult HydroSHEDS v10 documentation |
| **GRIP4 region & directory** | DATA LOCATION CONFIRMED; naming defect recorded | `Region_5_South_Asia` per `regions_lookup.json`; on-disk dir named `Region_5_Middle_East_Central_Asia`; config must point at the on-disk name with an explanatory comment | Config already does this in `config/countries.yaml` (see naming table, inventory doc) |
| **Land cover tiles for IND** | **ACTION REQUIRED** | 28 of 91 tiles have zero overlap with the real IND polygon; withdrawn "no action required" conclusion | Decide (Douglas) whether the automatic geometry filter alone suffices for IND or whether a manual review (as BRA's `N03W051`) is also needed before F1 runs for IND |
| **IND population data** | COMPLETE | unchanged | No action required |
| **IND transmission grid** | COMPLETE | unchanged | No action required (OQ-011 applies to all countries) |

---

## Mapping Absent Layers to Stage F Tasks (Action 5)

Unchanged from the original — wind Weibull/air-density (36 cells → F-2), CMIP6 (12 cells → F-4), ERA5 gust (3 cells → F-5/OQ-025), GEM trackers (3 cells → F-1) mappings held up on re-check.

---

## Manifest Status (corrected — was reported "unknown")

| Country | run_id (short) | data_acquisition | data_quality_audit | grid_alignment | suitability_criteria |
|---|---|---|---|---|---|
| BRA | `d7df84a8272e` | success | success | **failed** | **skipped_upstream_failed** |
| PRT | `d7df84a8272e` | success | success | success | success |
| IND | — (no manifest; F1 not yet run) | — | — | — | — |

BRA's `grid_alignment` failure and downstream `suitability_criteria` skip are load-bearing for the stale-artifact findings in the companion inventory document (Action 4): both phase directories on disk (`outputs/BRA/grid_alignment/`, `outputs/BRA/suitability_criteria/`) contain files despite the manifest recording the phase as not successfully completed for the current run (`d7df84a8272e...`). **`[FD3b1/FD3b2, 2026-09-22]`** In addition, `data_acquisition` itself (status `success` for both countries) is stale relative to the current `config/countries.yaml`: BRA's land_cover artifact references 154/155 tiles, PRT's references 26/26 — neither reflects the 42 (BRA) / 15 (PRT) zero-overlap tiles this pass's geometry check found. Every phase downstream of `data_acquisition`, `success` or not, inherits that staleness. See the companion inventory document's Action 4 for the full row-by-row breakdown.

---

## Completion Criterion Verification (Action 6)

Unchanged from the original — 90/90 cells populated, 51 `absent` cells mapped to tasks. The correction in this pass concerns the accuracy of specific findings (IND land cover, GRIP4 characterization, manifest status), not the completeness of the matrix.

---

## Outstanding Open Questions (Action 7)

Unchanged from the original — OQ-011, OQ-012 (now partially superseded by the corrected findings above), draft OQ-025 (still not formally opened in `docs/OPEN_QUESTIONS.md` as of this pass). New: **OQ-026** (interim/mosaic cache invalidation, opened by this audit pass — see `docs/OPEN_QUESTIONS.md`).

---

## Audit Metadata

| Field | Value |
|---|---|
| **Audit ID** | 2026-09_data_coverage |
| **Original Execution Date** | 2026-09-22 |
| **Original Auditor** | Claude Haiku 4.5 (Agent), low-effort subagent — see `CLAUDE.md` "Delegation policy" |
| **Correction Pass Date** | 2026-09-22 |
| **Correction Pass Auditor** | Claude Sonnet 5, main session (no subagent) |
| **Scope** | Complete layer × country mapping for BRA, PRT, IND; sourcing and status per METHODOLOGY M-F1-02 to M-F1-07 |
| **Read-Only Constraint** | Honored; no writes to GEOFREA_SHARED_RAW_DIR or GEOFREA_DATA_DIR; no edits to `src/`, `config/`, or data files |
| **Matrix Cell Count** | 90 (30 layers × 3 countries) |
| **IND land_cover zero-overlap tiles** | 28 of 91 (verified by re-running the codebase's own geometry filter against the real GADM polygon) |

---

**End of Data Coverage Audit**
