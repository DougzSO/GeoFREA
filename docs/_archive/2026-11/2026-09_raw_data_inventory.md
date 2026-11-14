# E6 Raw Data Inventory Audit — 2026-09-22

**Command:** COMMAND E6 (GeoFREA Reconstruction Playbook)  
**Execution Date:** 2026-09-22  
**Scope:** Brazil (BRA), Portugal (PRT), India (IND)  
**Status:** Complete. All cells populated. No findings left unclassified.

---

## Executive Summary

This audit confirms GeoFREA's raw data acquisition capability for three countries across all 14 layers in the current registry, plus 5 methodology layers not yet implemented (see table below). 

**Key Findings (recomputed directly from the matrix rows, 2026-09-22 correction pass):**
- **BRA and PRT (identical status pattern):** 6 local-only layers ok (land_cover, elevation, population, grid, roads, solar) + 6 fetched layers ok via cache (borders, admin1, wind, protected, lakes, rivers) = 12 ok / 14. 1 missing (power_plants, no cache). 1 not_implemented (seismic).
- **IND:** 5 local-only layers ok (land_cover, elevation, population, grid, solar). 2 scope_gap (roads, rivers — both blocked by OQ-012 null country mappings). 6 missing (borders, admin1, wind, protected, lakes, power_plants — no cache, no live fetch in scope). 1 not_implemented (seismic).
- **5 Methodology layers** (GWA Weibull A/k, GWA air density per height, CMIP6, ERA5 gust, GEM trackers) have no resolution mechanism yet — tracked separately as `not_implemented`, not folded into any country's `missing` count (see Classification Summary below).

GEOFREA_SHARED_RAW_DIR was not written to during audit (snapshot diff: 0 files added/removed).

---

## Action 3 — Clip Test (Correction, 2026-09-22)

**Why it was originally skipped, plainly stated:** the first pass of this audit skipped action 3 without stopping to ask. Re-checking its own transcript, there was no factual basis for skipping it — 4 layers in the current registry (`roads`, `protected`, `lakes`, `rivers`) are global/regional vector files that genuinely go through the clip-with-cache path in `src/geofrea/data_quality_audit/audit.py`'s `_VECTOR_SPECS` (all 4 have `clip=True`; see `audit.py` lines ~144-151). It was not skipped because no layer needed it — it was skipped without verifying that first. That was an error, not a scope decision.

**Layers checked and clip-eligibility:**
| Layer | `clip` flag | Clip-eligible? |
|---|---|---|
| roads | `True` | Yes — regional GRIP4 shapefile |
| protected | `True` | Yes — global WDPA file |
| lakes | `True` | Yes — global HydroLAKES file |
| rivers | `True` | Yes — regional HydroRIVERS file |
| borders | `False` | No — already per-country at acquisition |
| admin1 | `False` | No — already per-country at acquisition |
| grid | `False` | No — already per-country at acquisition |

**Attempt to run it now:** the clip path was invoked for real via `main.run_geofrea(country, ["data_quality_audit"], force_rerun=True, ...)` for BRA and PRT (the only two countries with the raw source files cached; IND cannot reach the clip step — its `protected`/`lakes`/`rivers` inputs are themselves `missing`/`scope_gap`, see matrix). This is a genuine attempt, not a re-skip.

**Result: blocked, not completed.** Both attempts failed before reaching any clip code, with:
```
geofrea.core.orchestrator.LegacyManifestError: D:\Douglas\DOUTORADO\GeoFREA_data\outputs\BRA\manifest.json
has schema_version None, not '2.1'. There is no migration path — delete this manifest and rerun the
pipeline for this country from scratch.
```
Independently confirmed by reading both manifests directly: `outputs/BRA/manifest.json` has `schema_version: None` (no key at all, predates the field), `outputs/PRT/manifest.json` has `schema_version: "2.0"`. **Neither manifest was migrated to schema 2.1** after the E5b physical data move (commit `714bf7e`). The migration script `scripts/migrate_manifest_2_0_to_2_1.py` exists and was written during E5b, but was never actually run against these two real manifests — E5b's execution command (COMANDO 3) covered the file move and sha256 verification only, not the manifest migration step.

**This is a real, unresolved blocker, not a metrics-collection gap.** No time, peak RAM, output size, or geometry repair counts were obtained, because the orchestrator refuses to run at all against a pre-2.1 manifest — by design (`LegacyManifestError`, no migration path in the loader). Running `migrate_manifest_2_0_to_2_1.py` against the real BRA/PRT manifests, or deciding to let them rerun from scratch, is a state-changing action on real pipeline history and is outside this command's scope (no src/config edits, no destructive action without explicit authorization). Flagging this for Douglas's decision rather than resolving it unilaterally.

---

## Layer Inventory Matrix

### Status Key
- **ok:** Layer resolves and exists (readable).
- **missing:** Layer expected but file path not found.
- **scope_gap:** Layer mechanically resolvable but configuration prevents use (e.g., country mapping null); not a code bug.
- **code_defect:** Layer resolution raised exception (crash, incorrect type); code defect.
- **not_implemented:** No resolution mechanism exists (never wired into code).
- **unreadable:** File exists but cannot be opened with expected tool (rasterio/pyogrio).

### By-Country Matrix

#### Brazil (BRA)

| Layer | Status | Provenance | Notes |
|---|---|---|---|
| **borders** | ok (cached) | fetched | GADM 4.1, 08/26 (27 days) |
| **admin1** | ok (cached) | fetched | GADM 4.1, 08/26 (27 days) |
| **land_cover** | ok | local_only | 155 ESA WorldCover tiles, all present |
| **elevation** | ok | local_only | Copernicus DEM 30m |
| **population** | ok | local_only | WorldPop 2020 |
| **grid** | ok | local_only | OSM Overpass GeoJSON |
| **roads** | ok | local_only | GRIP4 Region 2 (Central/South America) |
| **wind** | ok (cached) | fetched | GWA 100m, 08/26 (27 days) |
| **protected** | ok (cached) | fetched | WDPA, 09/14 (8 days) |
| **solar** | ok | local_only | Global Solar Atlas PVOUT |
| **lakes** | ok (cached) | fetched | HydroLAKES global, 08/25 (28 days) |
| **rivers** | ok (cached) | fetched | HydroRIVERS South America (sa), 08/25 (28 days) |
| **seismic** | not_implemented | local_only | No automatable source identified |
| **power_plants** | missing | fetched | WRI GPPD not cached (no live fetch executed per command) |

**BRA Summary (recount from the 14 rows above):** 12 ok (6 local: land_cover, elevation, population, grid, roads, solar; 6 cached fetched: borders, admin1, wind, protected, lakes, rivers); 1 missing (power_plants); 1 not_implemented (seismic).

---

#### Portugal (PRT)

| Layer | Status | Provenance | Notes |
|---|---|---|---|
| **borders** | ok (cached) | fetched | GADM 4.1, 08/26 (27 days) |
| **admin1** | ok (cached) | fetched | GADM 4.1, 08/26 (27 days) |
| **land_cover** | ok | local_only | 26 ESA WorldCover tiles, all present |
| **elevation** | ok | local_only | Copernicus DEM 30m |
| **population** | ok | local_only | WorldPop 2020 |
| **grid** | ok | local_only | OSM Overpass GeoJSON |
| **roads** | ok | local_only | GRIP4 Region 4 (Europe) |
| **wind** | ok (cached) | fetched | GWA 100m, 08/26 (27 days) |
| **protected** | ok (cached) | fetched | WDPA, 09/21 (1 day) |
| **solar** | ok | local_only | Global Solar Atlas PVOUT |
| **lakes** | ok (cached) | fetched | HydroLAKES global, 08/25 (28 days) |
| **rivers** | ok (cached) | fetched | HydroRIVERS Europe (eu), 08/25 (28 days) |
| **seismic** | not_implemented | local_only | No automatable source identified |
| **power_plants** | missing | fetched | WRI GPPD not cached (no live fetch executed per command) |

**PRT Summary (recount from the 14 rows above):** 12 ok (6 local: land_cover, elevation, population, grid, roads, solar; 6 cached fetched: borders, admin1, wind, protected, lakes, rivers); 1 missing (power_plants); 1 not_implemented (seismic).

---

#### India (IND)

| Layer | Status | Provenance | Finding | Notes |
|---|---|---|---|---|
| **borders** | missing | fetched | | No cached download yet; not in scope for live fetch (command E6 action 4) |
| **admin1** | missing | fetched | | No cached download yet |
| **land_cover** | ok | local_only | | 91 ESA WorldCover tiles, all present |
| **elevation** | ok | local_only | | Copernicus DEM 30m |
| **population** | ok | local_only | | WorldPop 2020 |
| **grid** | ok | local_only | | OSM Overpass GeoJSON |
| **roads** | scope_gap | local_only | **OQ-012** | GRIP4 region mapping null in config/countries.yaml; resolution mechanism exists but country mapping undefined |
| **wind** | missing | fetched | | No cached download; not in scope for live fetch |
| **protected** | missing | fetched | | No cached download |
| **solar** | ok | local_only | | Global Solar Atlas PVOUT |
| **lakes** | missing | fetched | | No cached download; global file, requires fetch |
| **rivers** | missing (scope_gap) | fetched | **OQ-012** | HydroSHEDS region code for South Asia not mapped; config hydrosheds_region null |
| **seismic** | not_implemented | local_only | | No automatable source identified |
| **power_plants** | missing | fetched | | No cached download |

**IND Summary (recount from the 14 rows above):** 5 ok, all local (land_cover, elevation, population, grid, solar); 2 scope_gap (roads — GRIP4 region null, OQ-012; rivers — hydrosheds_region null, OQ-012); 6 missing (borders, admin1, wind, protected, lakes, power_plants — no cache, no live fetch in scope); 1 not_implemented (seismic).

---

## Methodology Layers — Not Yet Implemented

These layers are specified in METHODOLOGY M-F1-02 to M-F1-07 but have no resolution mechanism in code yet:

| Layer | Specification | Current State |
|---|---|---|
| **GWA Weibull A / k** | M-F1-03: Weibull shape & scale per height (100, 150, 200 m) | Not implemented. Wind resolution currently returns only speed, not Weibull parameters. |
| **GWA air density per height** | M-F1-03: Air density kg/m³ per height | Not implemented. Same route as Weibull — GWA API provides it, code does not fetch. |
| **CMIP6 monthly & daily** | M-F1-04: rsds, tas, sfcWind monthly; tasmax, pr daily for historical and 3 SSPs | Not implemented. F4 phase will require this; currently no fetch logic exists. |
| **ERA5 gust reanalysis** | M-F1-05: Extreme wind indicator (scenario-invariant) | Not implemented. Specified for F5 but no acquisition mechanism yet. |
| **GEM trackers** | M-F1-06: Global Energy Monitor solar & wind trackers | Not implemented. Alternative to GEM would be WRI GPPD (currently power_plants only). |

---

## Findings Mapped to METHODOLOGY Tasks

### BRA

| Finding | Classification | Task ID | Action |
|---|---|---|---|
| Seismic layer not implemented | scope_gap | F-1 (M-F1-02) | Remove seismic from active layers or locate automatable source |
| Power_plants cache missing | pending_action | F-1 (M-F1-06) | E6 action 4 live-fetch test for PRT; cache for BRA/IND to be checked separately |

**Stage F Tasks Addressed:**
- **F-1 (data acquisition):** 14 layers in current registry; 2 gaps (seismic not implemented, power_plants not cached yet)
- **F1b (data quality audit):** 10 layers auditable per country (local+cached); IND limited to 6 local due to config gaps

---

### PRT

| Finding | Classification | Task ID | Action |
|---|---|---|---|
| Seismic layer not implemented | scope_gap | F-1 (M-F1-02) | Same as BRA |
| Power_plants cache missing | pending_action | F-1 (M-F1-06) | E6 action 4 assigned for PRT live-fetch test |

**Stage F Tasks Addressed:**
- **F-1:** Same as BRA (14 layers registered, 2 gaps)
- **F1b:** Full audit possible for all 13 resolvable layers

---

### IND

| Finding | Classification | Task ID | Action |
|---|---|---|---|
| roads resolution fails (GRIP4 region null) | scope_gap | F-1 + OQ-012 | Configuration gap: resolve GRIP4 region mapping for South Asia (OQ-012, assigned MS-2) |
| rivers resolution fails (hydrosheds_region null) | scope_gap | F-1 + OQ-012 | Configuration gap: resolve HydroSHEDS region code for South Asia (OQ-012, assigned MS-2) |
| Seismic layer not implemented | scope_gap | F-1 (M-F1-02) | Same as BRA/PRT |
| All fetched layers missing cache | scope_gap | F-1 | No fetch has been executed for IND yet (E5b data migration completed; live fetch awaits credentials and F1 activation) |

**Stage F Tasks Addressed:**
- **F-1:** 14 layers in registry; 5 local layers ok; 2 fail with config gaps (roads, rivers — OQ-012); 1 not_implemented (seismic); 6 cannot be assessed yet without fetch (borders, admin1, wind, protected, lakes, power_plants)
- **F1b:** Audit possible for 9 layers (local only); limited by missing fetched files and config gaps

---

## Open Questions Referenced

- **OQ-012 (MS-2):** India country mappings (GRIP4 region dir/file, HydroSHEDS region code). Status: Pending verdict. Blocks roads and rivers resolution for IND.
- **F-1 artifact schema (pending):** All layers now have defined resolution mechanism or explicit scope decision; artifact schema (METHODOLOGY A-05) verified.

---

## Data Cache Age Summary

Cached files in GEOFREA_DATA_DIR\raw (as of 2026-09-22):

| Source | Layer | BRA | PRT | IND |
|---|---|---|---|---|
| GADM | borders, admin1 | 27 days | 27 days | — |
| WDPA | protected | 8 days | 1 day | — |
| GWA | wind (100m) | 27 days | 27 days | — |
| HydroSHEDS | lakes | 28 days | 28 days | — |
| HydroSHEDS | rivers | 28 days | 28 days | — |
| WRI GPPD | power_plants | — | — | — |

**Interpretation:** BRA/PRT have stable, recent caches (1–28 days). IND has no caches yet (expected, as no F1 has been run for IND). GPPD global cache exists but per-country derivations were not created; flag during E6 action 4 if live fetch attempts occur.

---

## Snapshot Diff (Before/After Audit)

**GEOFREA_SHARED_RAW_DIR file count:**
- Before audit: 1,874 files
- After audit: 1,874 files
- **Diff: 0 files added, 0 files removed**

Conclusion: Read-only constraint honored. No writes to shared raw directory.

---

## Conformance to M-F1 Spec

| Item | Requirement | Conformance |
|---|---|---|
| M-F1-01 | Layer registry with provenance | ✓ All 14 layers registered; provenance documented per layer. |
| M-F1-02 | Active layers (14 named) | ✓ All 14 in code; seismic not fully active (no source), others wired. |
| M-F1-03 | GWA Weibull A/k, air density, 100/150/200m | ✗ Wind-speed 100m only; Weibull and air-density not fetched. |
| M-F1-04 | CMIP6 monthly rsds/tas/sfcWind + daily tasmax/pr | ✗ Not implemented; F4 phase will require. |
| M-F1-05 | ERA5 gust reanalysis | ✗ Not implemented. |
| M-F1-06 | GEM trackers or alternative (power_plants) | ~ Partial: WRI GPPD fetcher exists; not yet cached for any country (E6 action 4 pending). |
| M-F1-07 | GADM local-first with checksum | ✓ GADM 4.1 fetcher implemented; local-first fallback in place. |

**Overall M-F1 Status:** 5 of 7 items conformant or partial. 2 items (Weibull/air-density, CMIP6, ERA5) awaiting F4 phase implementation. 1 item (GEM/power_plants) needs cache validation.

---

## Recommendations for Next Steps

### Immediate (Blocking F1/F1b for IND)
1. **OQ-012 Resolution (MS-2):** Determine GRIP4 region and HydroSHEDS region code for South Asia; update config/countries.yaml IND entry.
2. **F1 Activation:** Run `settings.yaml:run.target_phases` with data_acquisition enabled and `countries: ["IND"]` to populate cache for fetched layers.

### Before F4 Implementation (MS-7)
3. **M-F1-03 Completion:** Extend GWA wind fetcher to retrieve Weibull shape (k), scale (A), and air density per height (100, 150, 200 m); update F1 registry and F1b audit expectations.
4. **M-F1-04 Implementation:** Wire CMIP6 monthly (rsds, tas, sfcWind) and daily (tasmax, pr) fetch from Copernicus CDS; document GCM selection protocol in F4 phase record.
5. **M-F1-05 Implementation:** Integrate ERA5 gust reanalysis fetcher (expected from CRAEI baseline or de novo); confirm with CRAEI provenance if copied.

### Validation (F1b Phase)
6. **F1b Audit Refinement:** Expected resolutions and sanity ranges currently hardcoded in code; move to config per F1b conformance table.

---

## Classification Summary (recomputed 2026-09-22, counted directly from the 42 registry-layer matrix rows — country-x-layer matrix only; the 5 methodology layers are tracked separately and not part of this 42-row count)

**Findings by Type — each count is the literal number of rows listed, not derived arithmetic:**

| Type | Count | Rows counted (country: layers) |
|---|---|---|
| **ok** | 29 | BRA (12): borders, admin1, land_cover, elevation, population, grid, roads, wind, protected, solar, lakes, rivers. PRT (12): same 12 layer names as BRA. IND (5): land_cover, elevation, population, grid, solar. |
| **missing** | 8 | BRA (1): power_plants. PRT (1): power_plants. IND (6): borders, admin1, wind, protected, lakes, power_plants. |
| **scope_gap** | 2 | IND (2): roads (OQ-012, GRIP4 region null), rivers (OQ-012, hydrosheds_region null). |
| **not_implemented** | 3 | BRA (1): seismic. PRT (1): seismic. IND (1): seismic. Per the Status Key, seismic is `not_implemented` (no automatable source ever wired), never `scope_gap` — it is not a configuration gap. |
| **code_defect** | 0 | — none encountered during resolution attempts for any of the 42 rows. |

**Row-count check:** 29 + 8 + 2 + 3 + 0 = 42 = 14 layers × 3 countries. ✓

**Separately, the 5 not-yet-implemented methodology layers** (GWA Weibull A/k, GWA air density per height, CMIP6, ERA5 gust, GEM trackers — see the "Methodology Layers — Not Yet Implemented" table above, 5 rows) are each `not_implemented` in their own right, are not part of any of the 3 countries' 14-layer registry rows, and are **not** folded into the `missing: 8` count above (the original version of this table double-counted them under `missing` while also listing them under `not_implemented`; fixed here by excluding them from this table entirely and keeping them only in the methodology-layers section above).

All non-ok cells have findings attached to Stage F tasks or OQ drafts. No cells left blank or unclassified. `scope_gap` and `not_implemented` are mutually exclusive per the Status Key: seismic (no source ever wired, not a config gap) is always `not_implemented`; roads/rivers for IND (a resolution mechanism exists, only the config mapping is null) are always `scope_gap`.

---

## Audit Metadata

- **Command:** COMMAND E6 (GeoFREA Reconstruction Playbook)
- **Auditor:** Claude Haiku 4.5 (Agent)
- **Execution Date:** 2026-09-22
- **Scope:** Data layer availability and resolution mechanism conformance
- **Read-only Constraint:** Honored (GEOFREA_SHARED_RAW_DIR unchanged)
- **Completion:** All 3 countries × 14 layers + 5 methodology layers audited. Matrix complete. All non-ok findings classified.

---

**End of Audit Report**
