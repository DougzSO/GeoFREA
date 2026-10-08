# Systematic review of code, artifacts and documents against METHODOLOGY 6.0.0

Date: 2026-10-08. Scope: read-only audit before any decision of the 7.0.0. Nothing but this report was edited. All `file:line` references were resolved by script against the working tree at the time of writing (commit `2f2481e` plus uncommitted work listed by `git status`); where a reference is an absence, the report says what was searched.

## 0. Completion checks (printed by the generating script)

- IDs extracted from `docs/METHODOLOGY.md` by regex (`M-F*`, `M-E1-*`, `U-*`, `A-*`, `V-*`): **93**.
- IDs in the table of section 1: **93**. The two sets are equal (checked by `assert`).
- Status counts: implemented 36, partial 19, contradicts 3, absent 35.
- Occurrences of the O&M names (section 4): `opex_fixed_frac` 6, `opex_fixed_pct_of_capex` 31, `opex_fixed_frac_of_capex` 0.
- Every F3 `ran_with_issues` has a cause (section 2.4).

Method and its limits. Status definitions: *implemented* = code and at least one piece of evidence match the item's text; *partial* = part of the text is implemented or the item is implemented with a documented gap; *absent* = no code exists (for F5 to F8 the package is an empty `__init__.py`); *contradicts* = the code does something the text says it does not (or the reverse). There is no `Implements:` marker for most items (A-13 itself is only partly followed), so the evidence is the module or function that does the work, found by reading, not by the marker alone. I did not run the code to produce this table; behavior claims rest on reading and on the earlier runs recorded in section 2. Counts of items that are absent are dominated by F5 to F8 (35 of 93).

## 1. METHODOLOGY items against the code

| ID | Line | Status | Evidence | Note |
|---|---|---|---|---|
| M-F1-01 | 153 | implemented | `src/geofrea/data_acquisition/phase.py:321`; `src/geofrea/data_acquisition/schemas.py:80` | Registry with `provenance` and computed `fetch_status`. |
| M-F1-02 | 154 | implemented | `src/geofrea/data_acquisition/phase.py:382` | Active layers registered. Plants: GEM only (see M-F1-06). |
| M-F1-03 | 155 | implemented | `src/geofrea/data_acquisition/phase.py:166`; `src/geofrea/data_acquisition/adapter.py:136` | GWA products at 100/150/200 m. |
| M-F1-04 | 156 | implemented | `src/geofrea/data_acquisition/fetchers/cmip6.py:3`; `src/geofrea/data_acquisition/cmip6_registry.py:1` | Resource channel acquired; daily tasmax/pr only for the ISIMIP3b counterparts (2071-2100 not on disk, see S-05 note). |
| M-F1-05 | 157 | implemented | `src/geofrea/data_acquisition/fetchers/era5.py:1`; `src/geofrea/climate_forcing/hazards.py:148` | ERA5 gust, annual maximum of fg10. |
| M-F1-06 | 158 | implemented | `src/geofrea/data_acquisition/fetchers/gem_trackers.py:1` | GEM pinned by sha256 and clipped; used only for validation (tests scan for imports, V-06). |
| M-F1-07 | 159 | implemented | `src/geofrea/data_acquisition/fetchers/gadm.py:74`; `src/geofrea/data_acquisition/schemas.py:221` | Local-first with checksum, network as fallback. |
| M-F1b-01 | 163 | implemented | `src/geofrea/data_quality_audit/audit.py:16` | Audit of every active layer; ranges come from `config/audit.yaml`. |
| M-F1b-02 | 164 | partial | `main.py:542`; `src/geofrea/core/orchestrator.py:5` | Findings never stop a run, but `siting_layers`, `land_eligibility` and `climate_forcing` now require the `audit_report` artifact, so an audit that fails to run stops them. The DAG drawing in section 4.1 still says F1b blocks nothing. |
| M-F2a-01 | 168 | implemented | `src/geofrea/grid_alignment/reference_grid.py:51` | 0.01 degree grid snapped to the 0.05 degree lattice. |
| M-F2a-02 | 169 | implemented | `src/geofrea/grid_alignment/raster_alignment.py:28`; `src/geofrea/land_eligibility/cells.py:78` | Geodesic distances, areas and slope spacing. |
| M-F2a-03 | 170 | implemented | `src/geofrea/grid_alignment/alignment.py:122`; `src/geofrea/grid_alignment/schemas.py:28` | Uncapped distances plus flag rasters. |
| M-F2a-04 | 171 | implemented | `src/geofrea/grid_alignment/alignment.py:385` | Wind aligned per height. |
| M-F2a-05 | 172 | implemented | `src/geofrea/grid_alignment/alignment.py:430` | Population summed (D-F2a-014). |
| M-F2b-01 | 176 | contradicts | `src/geofrea/land_eligibility/eligibility.py:89`; `src/geofrea/land_eligibility/eligibility.py:72` | Text says layers are binary and E4 is a threshold; code makes E4 and E5 shares (M-F3-01, 6.0.0). The line 'E5 is 0 or 1 ... until class shares replace it' is stale, and `forest_excluded (U-06)` is now a level of `excluded_classes`. |
| M-F2b-02 | 184 | implemented | `src/geofrea/suitability_criteria/physical_layers.py:1` | Distance layers passed through in physical units by `siting_layers`. |
| M-F2b-03 | 185 | implemented | `src/geofrea/suitability_criteria/physical_layers.py:1` | PVOUT and Weibull/air density layers. |
| M-F2b-04 | 186 | implemented | `src/geofrea/suitability_criteria/physical_layers.py:1` | No normalization. |
| M-F2b-06 | 187 | partial | `src/geofrea/land_eligibility/parameters.py:25`; `config/experiments.yaml:149` | Ranges are declared and validated, but only the nominal set is used (`nominal_set`, `pipeline.py`); no consumer reads low/high except the riparian and discharge grids. |
| M-F2b-05 | 188 | partial | `src/geofrea/grid_alignment/raster_alignment.py:577`; `src/geofrea/data_acquisition/fetchers/protected_planet.py:155`; `src/geofrea/land_eligibility/fractions.py:56` | Integrity failures raise (WDPA pages, land-cover tiles, DEM tiles). But F3 treats an absent protected-area, lake or river file as zero share without recording `assumed_free` in the artifact metadata (the label exists only in the legacy `suitability_criteria` code). |
| M-F2a-06 | 192 | contradicts | `src/geofrea/grid_alignment/raster_alignment.py:546`; `src/geofrea/grid_alignment/raster_alignment.py:513` | The code has two modes: exact blocks, and counting by sample centre when the tile pixel is not a whole fraction of the grid pixel (IND tiles, D-F2a-015 addendum). The text says anything else is an error. Also listed under the F3 heading instead of F2a. |
| M-F2a-07 | 193 | implemented | `src/geofrea/grid_alignment/raster_alignment.py:396`; `src/geofrea/data_acquisition/fetchers/copernicus_dem30.py:94` | 30 m slope bins from Copernicus GLO-30. Listed under the F3 heading instead of F2a. |
| M-F3-01 | 194 | implemented | `src/geofrea/land_eligibility/eligibility.py:137` | Share per pixel; E1-E3 sub-pixel, E4/E5 shares, E6 binary. |
| M-F3-02 | 195 | partial | `src/geofrea/land_eligibility/pipeline.py:289` | Only the central set is computed; there is no loop over variants (the `land_variants` block is empty and unread). |
| M-F3-03 | 196 | implemented | `src/geofrea/land_eligibility/cells.py:124` | 5 x 5 aggregation, weighted means, flag shares. |
| M-F3-04 | 203 | implemented | `src/geofrea/land_eligibility/cells.py:192` | Candidate filter by minimum area. |
| M-F3-05 | 204 | partial | `src/geofrea/land_eligibility/pipeline.py:8`; `src/geofrea/land_eligibility/pipeline.py:204` | Candidate parquet, pixel and cell rasters and dominant-exclusion raster exist; they are plain tiled GeoTIFF, not COG; no Pydantic table schema or `schema_version` on the parquet files. |
| M-F3-06 | 205 | implemented | `src/geofrea/land_eligibility/pipeline.py:9` | 0.1 degree table; V-07 reruns of F5-F7 are absent. |
| M-F4-01 | 209 | implemented | `src/geofrea/climate_forcing/members.py:1` | 36 members + reference. |
| M-F4-02 | 210 | implemented | `scripts/gcm_selection_spread.py:1`; `config/experiments.yaml:29` | Protocol run once (D-F4-012); 6 GCMs, IPSL exception flagged. |
| M-F4-03 | 216 | implemented | `src/geofrea/climate_forcing/change_factors.py:1` | 3 x 3 neighbourhood ratio for wind. |
| M-F4-04 | 221 | implemented | `src/geofrea/climate_forcing/forcing.py:1`; `src/geofrea/climate_forcing/change_factors.py:1` | Bilinear interpolation to cell centres. |
| M-F4-05 | 222 | implemented | `src/geofrea/climate_forcing/hazards.py:68` | Hazard context for the members with a hazard channel (window 2041-2070 only). |
| M-F4-06 | 226 | implemented | `src/geofrea/climate_forcing/forcing.py:245`; `src/geofrea/climate_forcing/pipeline.py:45` | Four outputs written. |
| M-F4-07 | 227 | implemented | `src/geofrea/climate_forcing/forcing.py:217` | Mask and consumer check exist; F5 does not exist yet to call it. |
| M-F5-01 | 231 | absent | `src/geofrea/technical_potential/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F5-02 | 232 | absent | `src/geofrea/technical_potential/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F5-03 | 235 | absent | `src/geofrea/technical_potential/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F5-04 | 241 | absent | `src/geofrea/technical_potential/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F5-05 | 242 | absent | `src/geofrea/technical_potential/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F5-06 | 243 | absent | `src/geofrea/technical_potential/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F6-01 | 247 | absent | `src/geofrea/lcoe_modeling/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F6-02 | 254 | absent | `src/geofrea/lcoe_modeling/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F6-03 | 255 | absent | `src/geofrea/lcoe_modeling/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F6-04 | 256 | absent | `src/geofrea/lcoe_modeling/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F6-05 | 257 | absent | `src/geofrea/lcoe_modeling/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F6-06 | 258 | absent | `src/geofrea/lcoe_modeling/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F7-01 | 264 | absent | `src/geofrea/robustness_analysis/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F7-02 | 265 | absent | `src/geofrea/robustness_analysis/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F7-03 | 266 | absent | `src/geofrea/robustness_analysis/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F7-04 | 267 | absent | `src/geofrea/robustness_analysis/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F7-05 | 268 | absent | `src/geofrea/robustness_analysis/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F7-06 | 269 | absent | `src/geofrea/robustness_analysis/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F7-07 | 270 | absent | `src/geofrea/robustness_analysis/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F7-08 | 275 | absent | `src/geofrea/robustness_analysis/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F7-09 | 276 | absent | `src/geofrea/robustness_analysis/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F7-10 | 277 | absent | `src/geofrea/robustness_analysis/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F7-11 | 278 | absent | `src/geofrea/robustness_analysis/__init__.py` (0 bytes) | Specification only; package empty. |
| M-F7b-01 | 282 | absent | `src/geofrea/external_validation/__init__.py` (0 bytes) | No F7b code (only its input, the GEM layer, exists: M-F1-06). |
| M-F7b-02 | 283 | absent | `src/geofrea/external_validation/__init__.py` (0 bytes) | No F7b code (only its input, the GEM layer, exists: M-F1-06). |
| M-F7b-03 | 284 | absent | `src/geofrea/external_validation/__init__.py` (0 bytes) | No F7b code (only its input, the GEM layer, exists: M-F1-06). |
| M-F7b-04 | 285 | absent | `src/geofrea/external_validation/__init__.py` (0 bytes) | No F7b code (only its input, the GEM layer, exists: M-F1-06). |
| M-F8-01 | 289 | absent | `src/geofrea/results_synthesis/__init__.py` (0 bytes) | Package empty. |
| M-F8-02 | 290 | absent | `src/geofrea/results_synthesis/__init__.py` (0 bytes) | Package empty. |
| M-E1-01 | 294 | absent | `src/geofrea/explorer/__init__.py` (0 bytes) | Package empty. Text also predates the sampled land ranges (OQ-049). |
| U-01 | 300 | absent | `src/geofrea/lcoe_modeling/__init__.py` (0 bytes) | No F6/F7 code, so no factorial of members and samples. |
| U-02 | 301 | absent | no match for /latin|qmc|sobol|LatinHypercube/ in `src/` | No sampler anywhere in `src/`; only `sampler:` keys in `config/experiments.yaml`. |
| U-03 | 302 | partial | `config/experiments.yaml:76`; `config/technologies.yaml:39` | Names are declared; no `range` exists for any of them (0 of 73 `parameters.json` entries have one) and no loader of `experiments.yaml` enforces it. Some keys have no value (degradation, grid/substation/road cost, gamma, eta_loss) and `opex_fixed_frac` is not the name used in `parameters.json`. |
| U-04 | 303 | absent | no match for /jaccard|convergence/ in `src/` | No convergence code. |
| U-05 | 304 | partial | `src/geofrea/core/schemas.py:49`; `src/geofrea/core/schemas.py:81` | Schema exists; no entry populates `range`; `min <= value <= max` is not validated; the load-time check that every uncertain parameter has a range has no code. |
| U-06 | 327 | contradicts | `config/experiments.yaml:117`; `config/experiments.yaml:149` | `strict`/`lenient` are empty, unread, and superseded in intent by the ranges of M-F2b-06 (OQ-049). |
| U-07 | 328 | partial | `src/geofrea/core/schemas.py:62`; `tests/unit/test_synthetic_value_separation.py:4` | `tier` is a field and synthetic values are separated; the rule that an unsourced methodological value is never used is a process rule, not enforced in code. |
| A-01 | 337 | implemented | `src/geofrea/core/orchestrator.py:5`; `main.py:504` | DAG validated at startup. |
| A-02 | 338 | implemented | `src/geofrea/core/orchestrator.py:15`; `src/geofrea/core/orchestrator.py:203` | Manifest records path, hash, schema version, phase, run id. It does not record the METHODOLOGY version (only inside the run-id hash). |
| A-03 | 339 | partial | `config/settings.yaml:63`; `src/geofrea/core/orchestrator.py:46` | Targets, rerun and staleness work. `run.technologies` is declared but no loader validates it against `technologies.yaml`, and F3 reads technologies from `land_availability`. |
| A-04 | 340 | partial | `src/geofrea/core/schemas.py:288`; `config/technologies.yaml:10` | Registry file and schema exist; `technologies.yaml` has no loader, and hub heights, IEC rule and CF model keys are null or unused. |
| A-05 | 341 | implemented | `tests/unit/test_iso3_literals.py:48` | Test present. |
| A-06 | 342 | partial | `tests/regression/v01_run.py:50`; `scripts/generate_zzz_fixture.py:267` | The ZZZ fixture runs F1 and F2a in CI (V-01); F3 is tested on a separate synthetic world; no F4-F7 (the spec says F1-F7). PROGRESS says 'done' and 'F1-F2b'. |
| A-07 | 343 | partial | `src/geofrea/land_eligibility/pipeline.py:204` | Rasters are tiled GeoTIFF, not COG; parquet tables carry no `schema_version`; run ID is the hash of config, methodology and commit. |
| A-08 | 344 | implemented | `src/geofrea/core/paths.py:176`; `src/geofrea/core/paths.py:144` | Layout under `GEOFREA_DATA_DIR`. PROGRESS still says A-08 'fails'. |
| A-09 | 354 | implemented | `src/geofrea/climate_forcing/external_inputs.py:1`; `src/geofrea/land_eligibility/pipeline.py:69` | Fail-loud applied across phases; exceptions noted under M-F2b-05. |
| A-10 | 355 | absent | no match for /max_batch_gb/ in `src/` | No `memory` key in `config/settings.yaml` and no batching code. |
| A-11 | 356 | implemented | `src/geofrea/climate_forcing/change_factors.py:4`; `src/geofrea/climate_forcing/hazards.py:13` | Provenance headers present. PROGRESS says A-11 'not_started'. |
| A-12 | 357 | partial | `.env.example:2`; `src/geofrea/core/orchestrator.py:203` | Environment declared and loaded; run id is deterministic; no seeds are recorded in the manifest (no sampler exists). Reruns with the same run id are not verified for byte identity. |
| A-13 | 358 | partial | `src/geofrea/climate_forcing/hazards.py:68`; `src/geofrea/data_acquisition/fetchers/cmip6.py:3` | `Implements:` docstrings exist in F1 and F4 only (a handful of functions); F2a, F3 and core cite items in module docstrings, not per function. |
| V-01 | 364 | implemented | `scripts/freeze_v01_fixtures.py:24`; `tests/regression/test_v01_frozen.py:24` | Frozen fixtures for F1/F2a layers, E1, E2; E3 frozen as the river-distance raster. |
| V-02 | 365 | partial | `tests/unit/test_core_geodesy.py:37`; `tests/unit/test_grid_alignment_slope_derivation.py:49` | Geodesic-area and slope tests exist; CRF/LCOE closed forms, Weibull CF, PVOUT units and power-law interpolation have no tests (no F5/F6 code). |
| V-03 | 366 | partial | `src/geofrea/land_eligibility/pipeline.py:350` | Only F3 invariants (eligible <= cell area, totals); regret, SR and capacity invariants need F5-F7. |
| V-04 | 367 | partial | `config/audit.yaml:3`; `src/geofrea/data_quality_audit/audit.py:16` | Ranges reported by F1b; the 'raise in F5' half has no code. |
| V-05 | 368 | absent | no match for /convergence/ in `src/` | Needs U-04. |
| V-06 | 369 | implemented | `tests/unit/test_gem_trackers.py:20`; `src/geofrea/data_acquisition/fetchers/gem_trackers.py:1` | Tests scan `src/` for GEM imports and the config for plant references. |
| V-07 | 370 | partial | `src/geofrea/land_eligibility/pipeline.py:9` | 0.1 degree table exists; F5-F7 reruns and side-by-side statistics are absent. |
| V-08 | 371 | partial | `scripts/generate_zzz_fixture.py:267`; `tests/regression/v01_run.py:32` | Synthetic end to end covers F1 and F2a only. |

Reading the table:

- **Contradictions (3):** M-F2a-06 (text says anything but an exact block count is an error; code counts by sample centre for IND), M-F2b-01 (text still describes binary layers, E5 as a point sample and `forest_excluded`), U-06 (strict/lenient variants superseded by the ranges of M-F2b-06 and unread by any code).
- **Partial items worth a decision in the 7.0.0:** M-F1b-02 (audit now gates three phases), M-F2b-05 (F3 treats an absent protected-area, lake or river file as zero share without recording it), M-F2b-06 and M-F3-02 (ranges and variants are declared but only the nominal set runs), U-03 and U-05 (names and schema exist, no range is populated, no loader enforces anything), A-03/A-04 (`technologies.yaml` and `run.technologies` have no loader).
- **Absent items are all downstream of F4** except U-02, U-04, V-05 (no sampler or convergence code, needed by F6) and A-10 (no batching, needed by F6/F7).

## 2. Artifacts per country

### 2.1 Reading the manifests

`outputs/<ISO3>/manifest.json` (schema 2.2) holds, per artifact: key, path, sha256, size, mtime, schema version, producing phase and run id. It holds no METHODOLOGY version and no parameter values; the version only enters the run-id hash, so it cannot be recovered from the manifest. Consequence for the 7.0.0: nothing in the artifacts says which methodology version produced them. The tables below list, per phase, the status, the times and every registered artifact with its modification date and schema version (the manifest's own fields).

Findings visible in the manifests:

- Each country keeps a stale legacy entry `suitability_criteria` with status `skipped_upstream_failed` (the phase is registered but outside the default run).
- The IND manifest has `dirty: true` (its last run used a working tree with uncommitted changes); BRA and PRT have `dirty: false` and share run id `d7df84a8272e`.
- Each country has 38 or 39 artifacts; `land_eligibility`, `overview`, `external_inputs` and the F4 phases are present for all three.

### 2.2 Per-country manifests

### BRA

Manifest schema 2.2, last run id `d7df84a8272e`, `dirty` = False. No METHODOLOGY version is stored in the manifest (it only enters the run-id hash), so the recorded version cannot be read back.

| Phase | Status | Started (UTC) | Finished (UTC) | Artifacts (key: path, modified UTC, schema) |
|---|---|---|---|---|
| data_acquisition | success | 2026-10-06T23:02 | 2026-10-06T23:05 | 1: layer_registry: `outputs/BRA/artifacts/layer_registry.json`, 2026-10-06 23:05, v1.1 |
| data_quality_audit | success | 2026-10-07T13:36 | 2026-10-07T14:23 | 1: audit_report: `outputs/BRA/artifacts/audit_report.json`, 2026-10-07 14:23, v2.1 |
| grid_alignment | success | 2026-10-08T00:18 | 2026-10-08T01:53 | 27: aligned/elevation: `outputs/BRA/grid_alignment/artifacts/BRA_elevation_aligned.tif`, 2026-10-06 14:55, v1.0<br>aligned/grid: `outputs/BRA/grid_alignment/artifacts/BRA_grid_aligned.tif`, 2026-10-06 22:26, v1.0<br>aligned/grid_distance_capped: `outputs/BRA/grid_alignment/artifacts/BRA_grid_aligned_capped.tif`, 2026-10-06 22:26, v1.0<br>aligned/lakes: `outputs/BRA/grid_alignment/artifacts/BRA_lakes_aligned.tif`, 2026-10-06 22:35, v1.0<br>aligned/land_cover: `outputs/BRA/grid_alignment/artifacts/BRA_land_cover_aligned.tif`, 2026-10-06 22:24, v1.0<br>aligned/land_cover_counts: `outputs/BRA/grid_alignment/artifacts/BRA_land_cover_counts_aligned.tif`, 2026-10-07 22:58, v1.0<br>aligned/population: `outputs/BRA/grid_alignment/artifacts/BRA_population_aligned.tif`, 2026-10-07 20:03, v1.0<br>aligned/rivers: `outputs/BRA/grid_alignment/artifacts/BRA_rivers_aligned.tif`, 2026-10-06 22:49, v1.0<br>aligned/rivers_distance_capped: `outputs/BRA/grid_alignment/artifacts/BRA_rivers_aligned_capped.tif`, 2026-10-06 22:49, v1.0<br>aligned/roads: `outputs/BRA/grid_alignment/artifacts/BRA_roads_aligned.tif`, 2026-10-06 22:35, v1.0<br>aligned/roads_distance_capped: `outputs/BRA/grid_alignment/artifacts/BRA_roads_aligned_capped.tif`, 2026-10-06 22:35, v1.0<br>aligned/slope: `outputs/BRA/grid_alignment/artifacts/BRA_slope_aligned.tif`, 2026-10-06 14:55, v1.0<br>aligned/slope_counts: `outputs/BRA/grid_alignment/artifacts/BRA_slope_counts_aligned.tif`, 2026-10-08 01:53, v1.0<br>aligned/solar: `outputs/BRA/grid_alignment/artifacts/BRA_solar_aligned.tif`, 2026-10-06 14:56, v1.0<br>aligned/wind_air_density_100m: `outputs/BRA/grid_alignment/artifacts/BRA_wind_air_density_100m_aligned.tif`, 2026-10-06 22:14, v1.0<br>aligned/wind_air_density_150m: `outputs/BRA/grid_alignment/artifacts/BRA_wind_air_density_150m_aligned.tif`, 2026-10-06 22:14, v1.0<br>aligned/wind_air_density_200m: `outputs/BRA/grid_alignment/artifacts/BRA_wind_air_density_200m_aligned.tif`, 2026-10-06 22:14, v1.0<br>aligned/wind_weibull_a_100m: `outputs/BRA/grid_alignment/artifacts/BRA_wind_weibull_a_100m_aligned.tif`, 2026-10-06 22:12, v1.0<br>aligned/wind_weibull_a_150m: `outputs/BRA/grid_alignment/artifacts/BRA_wind_weibull_a_150m_aligned.tif`, 2026-10-06 22:13, v1.0<br>aligned/wind_weibull_a_200m: `outputs/BRA/grid_alignment/artifacts/BRA_wind_weibull_a_200m_aligned.tif`, 2026-10-06 22:13, v1.0<br>aligned/wind_weibull_k_100m: `outputs/BRA/grid_alignment/artifacts/BRA_wind_weibull_k_100m_aligned.tif`, 2026-10-06 22:13, v1.0<br>aligned/wind_weibull_k_150m: `outputs/BRA/grid_alignment/artifacts/BRA_wind_weibull_k_150m_aligned.tif`, 2026-10-06 22:13, v1.0<br>aligned/wind_weibull_k_200m: `outputs/BRA/grid_alignment/artifacts/BRA_wind_weibull_k_200m_aligned.tif`, 2026-10-06 22:14, v1.0<br>aligned/wind_wind_speed_100m: `outputs/BRA/grid_alignment/artifacts/BRA_wind_wind_speed_100m_aligned.tif`, 2026-10-06 14:56, v1.0<br>aligned/wind_wind_speed_150m: `outputs/BRA/grid_alignment/artifacts/BRA_wind_wind_speed_150m_aligned.tif`, 2026-10-06 14:56, v1.0<br>aligned/wind_wind_speed_200m: `outputs/BRA/grid_alignment/artifacts/BRA_wind_wind_speed_200m_aligned.tif`, 2026-10-06 14:56, v1.0<br>aligned_rasters: `outputs/BRA/artifacts/aligned_rasters.json`, 2026-10-08 01:53, v1.0 |
| suitability_criteria | skipped_upstream_failed | 2026-10-06T14:56 | 2026-10-06T14:56 | 0: none |
| climate_forcing | success | 2026-10-08T10:47 | 2026-10-08T10:50 | 3: forcing: `outputs/BRA/climate_forcing/artifacts/forcing.parquet`, 2026-10-08 10:50, v1.0<br>forcing_masked: `outputs/BRA/climate_forcing/artifacts/forcing_masked.parquet`, 2026-10-08 10:50, v1.0<br>members: `outputs/BRA/climate_forcing/artifacts/members.yaml`, 2026-10-08 10:50, v1.0 |
| climate_maps | success | 2026-10-08T10:50 | 2026-10-08T10:51 | 1: climate_maps: `outputs/BRA/artifacts/climate_maps.json`, 2026-10-08 10:51, v1.0 |
| hazard_context | success | 2026-10-08T10:51 | 2026-10-08T10:54 | 1: hazard_context: `outputs/BRA/climate_forcing/artifacts/hazard_context.parquet`, 2026-10-08 10:54, v1.0 |
| siting_layers | success | 2026-10-08T01:53 | 2026-10-08T01:54 | 1: siting_layers: `outputs/BRA/artifacts/siting_layers.json`, 2026-10-08 01:54, v1.0 |
| external_inputs | success | 2026-10-07T17:25 | 2026-10-07T17:25 | 1: external_inputs: `outputs/BRA/artifacts/external_inputs.json`, 2026-10-07 17:25, v1.0 |
| overview | success | 2026-10-08T10:54 | 2026-10-08T10:58 | 1: overview: `outputs/BRA/artifacts/overview.json`, 2026-10-08 10:58, v1.0 |
| land_eligibility | success | 2026-10-08T02:46 | 2026-10-08T02:58 | 1: land_eligibility: `outputs/BRA/artifacts/land_eligibility.json`, 2026-10-08 02:58, v1.0 |

### PRT

Manifest schema 2.2, last run id `d7df84a8272e`, `dirty` = False. No METHODOLOGY version is stored in the manifest (it only enters the run-id hash), so the recorded version cannot be read back.

| Phase | Status | Started (UTC) | Finished (UTC) | Artifacts (key: path, modified UTC, schema) |
|---|---|---|---|---|
| data_acquisition | success | 2026-10-06T10:50 | 2026-10-06T10:51 | 1: layer_registry: `outputs/PRT/artifacts/layer_registry.json`, 2026-10-06 10:51, v1.1 |
| data_quality_audit | success | 2026-10-07T13:20 | 2026-10-07T13:23 | 1: audit_report: `outputs/PRT/artifacts/audit_report.json`, 2026-10-07 13:23, v2.1 |
| grid_alignment | success | 2026-10-07T22:19 | 2026-10-07T22:21 | 27: aligned/elevation: `outputs/PRT/grid_alignment/artifacts/PRT_elevation_aligned.tif`, 2026-10-06 14:55, v1.0<br>aligned/grid: `outputs/PRT/grid_alignment/artifacts/PRT_grid_aligned.tif`, 2026-10-06 19:49, v1.0<br>aligned/grid_distance_capped: `outputs/PRT/grid_alignment/artifacts/PRT_grid_aligned_capped.tif`, 2026-10-06 19:49, v1.0<br>aligned/lakes: `outputs/PRT/grid_alignment/artifacts/PRT_lakes_aligned.tif`, 2026-10-06 19:51, v1.0<br>aligned/land_cover: `outputs/PRT/grid_alignment/artifacts/PRT_land_cover_aligned.tif`, 2026-10-06 19:49, v1.0<br>aligned/land_cover_counts: `outputs/PRT/grid_alignment/artifacts/PRT_land_cover_counts_aligned.tif`, 2026-10-07 22:00, v1.0<br>aligned/population: `outputs/PRT/grid_alignment/artifacts/PRT_population_aligned.tif`, 2026-10-07 19:10, v1.0<br>aligned/rivers: `outputs/PRT/grid_alignment/artifacts/PRT_rivers_aligned.tif`, 2026-10-06 19:51, v1.0<br>aligned/rivers_distance_capped: `outputs/PRT/grid_alignment/artifacts/PRT_rivers_aligned_capped.tif`, 2026-10-06 19:51, v1.0<br>aligned/roads: `outputs/PRT/grid_alignment/artifacts/PRT_roads_aligned.tif`, 2026-10-06 19:50, v1.0<br>aligned/roads_distance_capped: `outputs/PRT/grid_alignment/artifacts/PRT_roads_aligned_capped.tif`, 2026-10-06 19:50, v1.0<br>aligned/slope: `outputs/PRT/grid_alignment/artifacts/PRT_slope_aligned.tif`, 2026-10-06 14:55, v1.0<br>aligned/slope_counts: `outputs/PRT/grid_alignment/artifacts/PRT_slope_counts_aligned.tif`, 2026-10-07 22:21, v1.0<br>aligned/solar: `outputs/PRT/grid_alignment/artifacts/PRT_solar_aligned.tif`, 2026-10-06 14:55, v1.0<br>aligned/wind_air_density_100m: `outputs/PRT/grid_alignment/artifacts/PRT_wind_air_density_100m_aligned.tif`, 2026-10-06 19:49, v1.0<br>aligned/wind_air_density_150m: `outputs/PRT/grid_alignment/artifacts/PRT_wind_air_density_150m_aligned.tif`, 2026-10-06 19:49, v1.0<br>aligned/wind_air_density_200m: `outputs/PRT/grid_alignment/artifacts/PRT_wind_air_density_200m_aligned.tif`, 2026-10-06 19:49, v1.0<br>aligned/wind_weibull_a_100m: `outputs/PRT/grid_alignment/artifacts/PRT_wind_weibull_a_100m_aligned.tif`, 2026-10-06 19:49, v1.0<br>aligned/wind_weibull_a_150m: `outputs/PRT/grid_alignment/artifacts/PRT_wind_weibull_a_150m_aligned.tif`, 2026-10-06 19:49, v1.0<br>aligned/wind_weibull_a_200m: `outputs/PRT/grid_alignment/artifacts/PRT_wind_weibull_a_200m_aligned.tif`, 2026-10-06 19:49, v1.0<br>aligned/wind_weibull_k_100m: `outputs/PRT/grid_alignment/artifacts/PRT_wind_weibull_k_100m_aligned.tif`, 2026-10-06 19:49, v1.0<br>aligned/wind_weibull_k_150m: `outputs/PRT/grid_alignment/artifacts/PRT_wind_weibull_k_150m_aligned.tif`, 2026-10-06 19:49, v1.0<br>aligned/wind_weibull_k_200m: `outputs/PRT/grid_alignment/artifacts/PRT_wind_weibull_k_200m_aligned.tif`, 2026-10-06 19:49, v1.0<br>aligned/wind_wind_speed_100m: `outputs/PRT/grid_alignment/artifacts/PRT_wind_wind_speed_100m_aligned.tif`, 2026-10-06 14:55, v1.0<br>aligned/wind_wind_speed_150m: `outputs/PRT/grid_alignment/artifacts/PRT_wind_wind_speed_150m_aligned.tif`, 2026-10-06 14:55, v1.0<br>aligned/wind_wind_speed_200m: `outputs/PRT/grid_alignment/artifacts/PRT_wind_wind_speed_200m_aligned.tif`, 2026-10-06 14:55, v1.0<br>aligned_rasters: `outputs/PRT/artifacts/aligned_rasters.json`, 2026-10-07 22:21, v1.0 |
| suitability_criteria | skipped_upstream_failed | 2026-10-06T14:55 | 2026-10-06T14:55 | 1: suitability_criteria_result: `outputs/PRT/artifacts/suitability_criteria_result.json`, 2026-09-28 00:34, v1.0 |
| climate_forcing | success | 2026-10-07T22:24 | 2026-10-07T22:27 | 3: forcing: `outputs/PRT/climate_forcing/artifacts/forcing.parquet`, 2026-10-07 22:27, v1.0<br>forcing_masked: `outputs/PRT/climate_forcing/artifacts/forcing_masked.parquet`, 2026-10-07 22:27, v1.0<br>members: `outputs/PRT/climate_forcing/artifacts/members.yaml`, 2026-10-07 22:27, v1.0 |
| climate_maps | success | 2026-10-08T02:59 | 2026-10-08T02:59 | 1: climate_maps: `outputs/PRT/artifacts/climate_maps.json`, 2026-10-08 02:59, v1.0 |
| hazard_context | success | 2026-10-07T22:27 | 2026-10-07T22:28 | 1: hazard_context: `outputs/PRT/climate_forcing/artifacts/hazard_context.parquet`, 2026-10-07 22:28, v1.0 |
| siting_layers | success | 2026-10-07T22:21 | 2026-10-07T22:21 | 1: siting_layers: `outputs/PRT/artifacts/siting_layers.json`, 2026-10-07 22:21, v1.0 |
| external_inputs | success | 2026-10-07T17:25 | 2026-10-07T17:25 | 1: external_inputs: `outputs/PRT/artifacts/external_inputs.json`, 2026-10-07 17:25, v1.0 |
| overview | success | 2026-10-08T02:59 | 2026-10-08T03:00 | 1: overview: `outputs/PRT/artifacts/overview.json`, 2026-10-08 03:00, v1.0 |
| land_eligibility | success | 2026-10-07T22:21 | 2026-10-07T22:21 | 1: land_eligibility: `outputs/PRT/artifacts/land_eligibility.json`, 2026-10-07 22:21, v1.0 |

### IND

Manifest schema 2.2, last run id `ea7960a45284`, `dirty` = True. No METHODOLOGY version is stored in the manifest (it only enters the run-id hash), so the recorded version cannot be read back.

| Phase | Status | Started (UTC) | Finished (UTC) | Artifacts (key: path, modified UTC, schema) |
|---|---|---|---|---|
| data_acquisition | success | 2026-10-06T22:47 | 2026-10-06T22:48 | 1: layer_registry: `outputs/IND/artifacts/layer_registry.json`, 2026-10-06 22:48, v1.1 |
| data_quality_audit | success | 2026-10-08T01:20 | 2026-10-08T01:24 | 1: audit_report: `outputs/IND/artifacts/audit_report.json`, 2026-10-08 01:24, v2.1 |
| grid_alignment | success | 2026-10-07T23:01 | 2026-10-07T23:55 | 27: aligned/elevation: `outputs/IND/grid_alignment/artifacts/IND_elevation_aligned.tif`, 2026-10-06 14:57, v1.0<br>aligned/grid: `outputs/IND/grid_alignment/artifacts/IND_grid_aligned.tif`, 2026-10-06 21:04, v1.0<br>aligned/grid_distance_capped: `outputs/IND/grid_alignment/artifacts/IND_grid_aligned_capped.tif`, 2026-10-06 21:04, v1.0<br>aligned/lakes: `outputs/IND/grid_alignment/artifacts/IND_lakes_aligned.tif`, 2026-10-06 21:04, v1.0<br>aligned/land_cover: `outputs/IND/grid_alignment/artifacts/IND_land_cover_aligned.tif`, 2026-10-06 21:02, v1.0<br>aligned/land_cover_counts: `outputs/IND/grid_alignment/artifacts/IND_land_cover_counts_aligned.tif`, 2026-10-07 23:02, v1.0<br>aligned/population: `outputs/IND/grid_alignment/artifacts/IND_population_aligned.tif`, 2026-10-07 19:24, v1.0<br>aligned/rivers: `outputs/IND/grid_alignment/artifacts/IND_rivers_aligned.tif`, 2026-10-06 21:09, v1.0<br>aligned/rivers_distance_capped: `outputs/IND/grid_alignment/artifacts/IND_rivers_aligned_capped.tif`, 2026-10-06 21:09, v1.0<br>aligned/roads: `outputs/IND/grid_alignment/artifacts/IND_roads_aligned.tif`, 2026-10-06 23:02, v1.0<br>aligned/roads_distance_capped: `outputs/IND/grid_alignment/artifacts/IND_roads_aligned_capped.tif`, 2026-10-06 23:02, v1.0<br>aligned/slope: `outputs/IND/grid_alignment/artifacts/IND_slope_aligned.tif`, 2026-10-06 14:57, v1.0<br>aligned/slope_counts: `outputs/IND/grid_alignment/artifacts/IND_slope_counts_aligned.tif`, 2026-10-07 23:55, v1.0<br>aligned/solar: `outputs/IND/grid_alignment/artifacts/IND_solar_aligned.tif`, 2026-10-06 14:57, v1.0<br>aligned/wind_air_density_100m: `outputs/IND/grid_alignment/artifacts/IND_wind_air_density_100m_aligned.tif`, 2026-10-06 21:02, v1.0<br>aligned/wind_air_density_150m: `outputs/IND/grid_alignment/artifacts/IND_wind_air_density_150m_aligned.tif`, 2026-10-06 21:02, v1.0<br>aligned/wind_air_density_200m: `outputs/IND/grid_alignment/artifacts/IND_wind_air_density_200m_aligned.tif`, 2026-10-06 21:02, v1.0<br>aligned/wind_weibull_a_100m: `outputs/IND/grid_alignment/artifacts/IND_wind_weibull_a_100m_aligned.tif`, 2026-10-06 21:01, v1.0<br>aligned/wind_weibull_a_150m: `outputs/IND/grid_alignment/artifacts/IND_wind_weibull_a_150m_aligned.tif`, 2026-10-06 21:01, v1.0<br>aligned/wind_weibull_a_200m: `outputs/IND/grid_alignment/artifacts/IND_wind_weibull_a_200m_aligned.tif`, 2026-10-06 21:01, v1.0<br>aligned/wind_weibull_k_100m: `outputs/IND/grid_alignment/artifacts/IND_wind_weibull_k_100m_aligned.tif`, 2026-10-06 21:02, v1.0<br>aligned/wind_weibull_k_150m: `outputs/IND/grid_alignment/artifacts/IND_wind_weibull_k_150m_aligned.tif`, 2026-10-06 21:02, v1.0<br>aligned/wind_weibull_k_200m: `outputs/IND/grid_alignment/artifacts/IND_wind_weibull_k_200m_aligned.tif`, 2026-10-06 21:02, v1.0<br>aligned/wind_wind_speed_100m: `outputs/IND/grid_alignment/artifacts/IND_wind_wind_speed_100m_aligned.tif`, 2026-10-06 14:57, v1.0<br>aligned/wind_wind_speed_150m: `outputs/IND/grid_alignment/artifacts/IND_wind_wind_speed_150m_aligned.tif`, 2026-10-06 14:58, v1.0<br>aligned/wind_wind_speed_200m: `outputs/IND/grid_alignment/artifacts/IND_wind_wind_speed_200m_aligned.tif`, 2026-10-06 14:58, v1.0<br>aligned_rasters: `outputs/IND/artifacts/aligned_rasters.json`, 2026-10-07 23:55, v1.0 |
| suitability_criteria | skipped_upstream_failed | 2026-10-06T14:58 | 2026-10-06T14:58 | 0: none |
| climate_forcing | success | 2026-10-08T03:00 | 2026-10-08T10:43 | 3: forcing: `outputs/IND/climate_forcing/artifacts/forcing.parquet`, 2026-10-08 10:43, v1.0<br>forcing_masked: `outputs/IND/climate_forcing/artifacts/forcing_masked.parquet`, 2026-10-08 10:43, v1.0<br>members: `outputs/IND/climate_forcing/artifacts/members.yaml`, 2026-10-08 10:43, v1.0 |
| climate_maps | success | 2026-10-08T10:43 | 2026-10-08T10:43 | 1: climate_maps: `outputs/IND/artifacts/climate_maps.json`, 2026-10-08 10:43, v1.0 |
| hazard_context | success | 2026-10-08T10:43 | 2026-10-08T10:45 | 1: hazard_context: `outputs/IND/climate_forcing/artifacts/hazard_context.parquet`, 2026-10-08 10:45, v1.0 |
| siting_layers | success | 2026-10-08T01:24 | 2026-10-08T01:25 | 1: siting_layers: `outputs/IND/artifacts/siting_layers.json`, 2026-10-08 01:25, v1.0 |
| external_inputs | success | 2026-10-07T17:25 | 2026-10-07T17:25 | 1: external_inputs: `outputs/IND/artifacts/external_inputs.json`, 2026-10-07 17:25, v1.0 |
| overview | success | 2026-10-08T10:45 | 2026-10-08T10:47 | 1: overview: `outputs/IND/artifacts/overview.json`, 2026-10-08 10:47, v1.0 |
| land_eligibility | success | 2026-10-08T01:25 | 2026-10-08T01:37 | 1: land_eligibility: `outputs/IND/artifacts/land_eligibility.json`, 2026-10-08 01:37, v1.0 |


### 2.3 What the manifest does not list

The F3 outputs sit under `outputs/<ISO3>/land_eligibility/artifacts/` (cells, candidates, 0.1 degree tables, four rasters per technology) and the summary `outputs/<ISO3>/artifacts/land_eligibility.json`. The new aligned layers `<ISO3>_land_cover_counts_aligned.tif` and `<ISO3>_slope_counts_aligned.tif` are registered by F2a. The 30 m DEM and the 10 m IND land-cover tiles are raw inputs under `GeoFREA_data/raw/` with their own `manifest.json` (sha256), outside the pipeline manifest.

### 2.4 Causes of every F3 `ran_with_issues`

`docs/PROGRESS.json` marks F3 `ran_with_issues` for BRA, PRT and IND. The label is manual: the manifest records `land_eligibility` as `success` with no error for all three, and the latest logs (`GeoFREA_data/logs/<ISO3>/9f039d84...log`) hold no warning or error from F3 for PRT and BRA; the IND log holds one earlier failed attempt (below). The only warnings are the F4 ERA5 notes: 137 IND and 130 BRA cells with a native cell more than 0.25 degree away. The causes therefore come from the phase record `docs/phases/F3_land_eligibility.md` (D-F3-006) and `docs/OPEN_QUESTIONS.md`:

| Country | Cause of the label | Source |
|---|---|---|
| PRT | E3 excludes 24.5% of the land because every stream counts (OQ-046); density range 150-300 and solar slope upper end 15 degrees are unsourced (OQ-047, OQ-049); E4 now uses 30 m slope, whose threshold basis is unknown (D-F2a-016) | D-F3-006; OQ-046, OQ-047, OQ-049 |
| BRA | Same E3 (29.4%) and unsourced ranges; E1 is 31.0% under the any-designation rule (conservative choice, OQ-048); E4 for solar went from 0.6% to 16.2% with the 30 m slope; 6 corrupted WorldCover tiles lie outside the mainland and are skipped by their bounds (docstring of `mosaic_land_cover`, `src/geofrea/grid_alignment/raster_alignment.py`) | D-F3-006; `raster_alignment.py` |
| IND | E6 excludes 53.2% at 200 persons/km2 (OQ-047); E5 excludes 79.8% for solar (cropland excluded); the F3 run used land-cover tiles of about 100 m (D-F2a-015 addendum) and the 10 m replacement is downloaded but not yet applied; the last run was `dirty`; one earlier attempt failed on 2026-10-07 20:56 because the WDPA file was moved aside during the re-download (log line `Phase 'land_eligibility' [IND] FAILED`), later reruns succeeded | D-F3-006; log; manifest |

Common cause for all three: the label cannot clear until OQ-046 to OQ-049 are decided and the F3 conformance check (V-01 to V-03 on real data) is done; the label also predates the 2026-10-08 fixes, so it should be reviewed rather than carried over.

## 3. Outdated text

Each item gives the text, where it is, and the later decision that contradicts it.

### 3a. LIMITATIONS L-201 to L-209

| Entry | Text (excerpt) | Why it is outdated |
|---|---|---|
| L-201 (`docs/LIMITATIONS.md:45`) | \| L-201 \| countries.BRA.technologies.solar.slope_threshold_deg \| 5.0 degrees \| single case study; pending OQ-002 \| \| | The field `slope_threshold_deg` was removed from `parameters.json` on 2026-10-08 (D-F1b-014); OQ-002 was resolved on 2026-10-07; solar slope is now `land_availability` 10 (range 10-15). |
| L-202 (`docs/LIMITATIONS.md:46`) | \| L-202 \| countries.BRA.technologies.wind.slope_threshold_deg \| 8.5 degrees \| calibrated without primary source; pend... | Same field removed; OQ-003 resolved; wind slope is now 16.7 degrees (range 10.2-30), sourced. |
| L-203 (`docs/LIMITATIONS.md:47`) | \| L-203 \| countries.BRA.technologies.wind.opex_fixed_pct_of_capex \| 0.0077 fraction/year \| O&M of another technology;... | Still current (BRA wind O&M uses the solar O&M figure; OQ-016 open). Only the field-name question of section 4 applies. |
| L-204 (`docs/LIMITATIONS.md:48`) | \| L-204 \| countries.BRA.criteria.terrain_slope_threshold_deg \| 12.0 degrees \| legacy inheritance without primary sour... | `terrain_slope_threshold_deg` was removed from `parameters.json` (2026-10-08); the legacy terrain score now takes the highest nominal slope maximum from `land_availability`; OQ-002 resolved. |
| L-205 (`docs/LIMITATIONS.md:49`) | \| L-205 \| countries.PRT.technologies.solar.slope_threshold_deg \| 5.0 degrees \| single case study; pending OQ-002 \| \| | Same as L-201 for PRT. |
| L-206 (`docs/LIMITATIONS.md:50`) | \| L-206 \| countries.PRT.technologies.wind.slope_threshold_deg \| 8.5 degrees \| calibrated without primary source; pend... | Same as L-202 for PRT. |
| L-207 (`docs/LIMITATIONS.md:51`) | \| L-207 \| countries.PRT.criteria.terrain_slope_threshold_deg \| 10.0 degrees \| legacy inheritance without primary sour... | Same as L-204 for PRT. |
| L-208 (`docs/LIMITATIONS.md:52`) | \| L-208 \| criteria.river_safety_buffer_km \| 0.5 km \| calibrated without primary source; pending OQ-003 \| \| | The legacy `criteria.river_safety_buffer_km` (0.5) still exists in `parameters.json`, but F3 no longer reads it: the setback is `land_availability` 0.5 km (0.25-1.0) and the discharge parameter; OQ-003 was resolved. |
| L-209 (`docs/LIMITATIONS.md:53`) | \| L-209 \| criteria.pop_density_threshold \| 200.0 persons/km2 \| calibrated without primary source; pending OQ-003 \| \| | The legacy `criteria.pop_density_threshold` (200) still exists, but F3 reads `land_availability` (200, range 150-300, OQ-047); OQ-003 was resolved. |

### 3b. PROGRESS: milestone status against phase status

- `docs/PROGRESS.json:12`: {"id": "MS-5", "title": "F3 land_eligibility", "status": "not_started"}. MS-5 (F3) is `not_started`, `current_milestone` is MS-5, and phase F3 is `built_pending_conformance` with results for three countries (D-F3-006). The milestone gate is 'candidate tables for three countries and two technologies', which exists.
- `docs/PROGRESS.json:13`: {"id": "MS-6", "title": "Parameter research (OQ-001 to OQ-023)", "status": "not_started"}. MS-6 (parameter research, OQ-001 to OQ-023) is `not_started`, but OQ-002, OQ-003, OQ-015, OQ-044 and OQ-045 were resolved on 2026-10-07 (`docs/_audit/2026-10_f3_parameter_research.md`) and the solar slope research was done on 2026-10-08. METHODOLOGY section 12 says MS-6 runs in parallel with MS-4 and MS-5.
- `docs/PROGRESS.json:11`: {"id": "MS-4", "title": "F2b rebuild as siting_layers", "status": "in_progress"}. MS-4 (F2b) is `in_progress` while F3 (which MS-5 follows) already runs on its output; the gate 'exclusion parity E1-E3; sanity ranges pass for three countries' is not marked.
- `docs/PROGRESS.json:14`: {"id": "MS-7", "title": "F4 climate_forcing", "status": "in_progress"}. MS-7 (F4) is `in_progress` although J-1 to J-5 are done and the forcing exists for three countries; consistent with phase F4 `in_progress`, so only the wording of the gate ('forcing tables for the selected ensemble') needs checking.
- `docs/PROGRESS.json:26` (summary of `core`): says 'A-08 and A-13 fail', 'A-10/A-11 not_started', 'A-06 ... ZZZ runs F1-F2b'. Against the code: A-08 is implemented (`core/paths.py`), A-11 is implemented (provenance headers in `climate_forcing/change_factors.py`), A-06 covers F1 and F2a only (`tests/regression/v01_run.py`), and A-12 is called 'done' although no seeds are recorded.
- F2a and F3 phase statuses were updated on 2026-10-08, but the per-country F3 label (`ran_with_issues`) was not (section 2.4).

### 3c. M-F2b-01, M-F2a-06 and M-F2a-07 against M-F3-01 and the 6.0.0 changelog

- `docs/METHODOLOGY.md:176`: header of M-F2b-01 says 'Exclusion layers per technology (binary, 1 = excluded)'. M-F3-01 (6.0.0) defines E1-E5 as shares and E6 as binary.
- `docs/METHODOLOGY.md:180`: 'E5 is 0 or 1 at the pixel's land-cover sample until class shares replace it'. They replaced it in 6.0.0 (M-F2a-06, D-F2a-015).
- `docs/METHODOLOGY.md:181`: 'E4 slope: slope above `slope_max_deg[tech]`' reads as a threshold on a pixel value; M-F3-01 makes E4 the share of 30 m samples above the maximum (M-F2a-07).
- `docs/METHODOLOGY.md:182`: '`forest_excluded` (land-availability variant, U-06)'. In `config/experiments.yaml` the solar levels are now `cropland_excluded` / `cropland_allowed` and the wind levels `forest_excluded` / `forest_allowed`; the parameter is `excluded_classes`, a named-level parameter of M-F2b-06, not a U-06 variant.
- `docs/METHODOLOGY.md:192` and `:193`: M-F2a-06 and M-F2a-07 sit under the heading `### F3 land_eligibility` (`docs/METHODOLOGY.md:190`) but belong to F2a (their ID prefix and `grid_alignment` code). M-F2b-06 (`:187`) is also listed before M-F2b-05 (`:188`).
- `docs/METHODOLOGY.md:192`: 'anything else is an error'. The code has a centre-count mode for tiles that are not a whole fraction of the grid pixel (IND, D-F2a-015 addendum).

### 3d. U-06 (strict/lenient) against M-F2b-06 and OQ-049

- `docs/METHODOLOGY.md:327`: 'Land-availability variants.** `central`, `strict`, `lenient` exclusion parameter sets declared in `experiments.yaml`. `central` feeds F4-F7. Variants feed T-R2 and E1 only.'. M-F2b-06 (`:187`) declares the parameters as ranges and states that it announces the replacement of variants; `docs/OPEN_QUESTIONS.md` OQ-049 awaits the verdict; `config/experiments.yaml:117` keeps empty `central`, `strict`, `lenient` entries that no code reads (the comment at line 148 says so).
- `docs/METHODOLOGY.md:195`: M-F3-02 ('for every variant declared in `experiments.yaml` (U-06)') still speaks of variants.
- `docs/METHODOLOGY.md:243`: M-F5-06 ('country aggregates per member and land-availability variant') still speaks of variants.
- `docs/METHODOLOGY.md:294`: M-E1-01 ('adjustable only across precomputed variants') still speaks of variants.
- `docs/METHODOLOGY.md:398`: T-R2 ('land-availability variants') still speaks of variants.
- `docs/METHODOLOGY.md:382`: section 9 ('land variants' as content of `experiments.yaml`) still speaks of variants.

### 3e. RO3 and S-04 against D-F4-012

- `docs/METHODOLOGY.md:84`: '\| S-04 \| Climate models \| CMIP6 GCM ensemble, minimum GFDL-ESM4 and MIROC6, target four to six models selected by protocol M-F4-02. \|'. `docs/phases/F4_climate_forcing.md:35` (D-F4-012, decided 2026-10-06): six GCMs (GFDL-ESM4, MIROC6, ACCESS-CM2, IPSL-CM6A-LR, CNRM-CM6-1, MRI-ESM2-0), 36 members.
- **Not a contradiction.** Six is inside 'four to six' and GFDL-ESM4 and MIROC6 are in the set; the text is only stale in naming no models and in calling six a 'target'. RO3 says 'a CMIP6 GCM ensemble' without a size and does not conflict. The 'two GCMs' mentioned in the discussion of the draft summary comes from the thesis proposal, not from METHODOLOGY. The new `docs/PROJECT_SUMMARY.md` says '6-GCM', consistent with D-F4-012.

### 3f. Other text contradicted by a later decision

1. `docs/METHODOLOGY.md:115` (DAG, section 4.1): 'F1  data_acquisition ──> F1b data_quality_audit            (report, blocks nothing)'. `main.py` makes `siting_layers`, `land_eligibility` and `climate_forcing` require `audit_report` (`main.py` PhaseSpecs), so an audit that does not run stops them.
2. `docs/METHODOLOGY.md:117` (DAG): 'F1 + F3 (cell grid) ──> F4 climate_forcing'. In code F4 requires `aligned_rasters`, `audit_report` and `external_inputs`, not F3; the phases `external_inputs`, `hazard_context`, `climate_maps` and `overview` appear in neither the DAG nor the phase table of section 4.2.
3. `docs/METHODOLOGY.md:85` (S-05): the 2071-2100 window as a sensitivity member. No ISIMIP3b 2071-2100 hazard data exist on `D:` (`docs/_audit/2026-10_disk_and_data_inventory.md`); the 18 members of that window have a resource row and no hazard row (D-F4-002, D-F4-004). The text does not say so.
4. `config/experiments.yaml:284`: '# OQ-009: Per-technology CF_min'. CF_min belongs to OQ-008 (`docs/OPEN_QUESTIONS.md`); OQ-009 is the GCM ensemble, decided.
5. `config/experiments.yaml:280`: 'top_k_capacity_gw: null  # Pending OQ-021 (capacity approach)'. The capacity target of the top-k sensitivity is OQ-010; OQ-021 is the top-k percentage.
6. `config/technologies.yaml:95` and the next line. Hub height is part of OQ-005; OQ-019 is the degradation range. `docs/_audit/2026-09_embedded_values.md` repeats the wrong reference (historical).
7. `config/experiments.yaml:74` (header of `uncertain_parameters`): 'validated at load'. No loader reads `experiments.yaml`; there is no validation (see U-03, U-05).
8. `docs/METHODOLOGY.md:379` (section 9): `parameters.json` schema U-05. The legacy `criteria` block (21 entries) is used only by the retired `suitability_criteria` phase; the slope entries were removed on 2026-10-08.
9. `docs/METHODOLOGY.md:302` (U-03): names `opex_fixed_frac`. `parameters.json` uses `opex_fixed_pct_of_capex` (section 4).
10. `docs/PROJECT_SUMMARY.md:29`: 'Land-availability parameters are declared as central values with sourced ranges (M-F2b-06, U-06)'. U-06 is the strict/lenient item (3d); ranges are not all sourced (density, discharge and the solar slope upper end are flagged unsourced). The paragraph also says 'Every main result is reported as a central value with a range', which no METHODOLOGY item states.

## 4. The three O&M names

Counts use a word-boundary match over the repository (excluding `.git`, caches, rasters, tables and images); the name `opex_fixed_frac` is not matched inside `opex_fixed_frac_of_capex`.

| Name | Occurrences | Files |
|---|---|---|
| `opex_fixed_frac` | 6 | `config/experiments.yaml` (1); `config/technologies.yaml` (2); `docs/METHODOLOGY.md` (2); `docs/_audit/2026-10_parameter_inventory_for_ranges.md` (1) |
| `opex_fixed_pct_of_capex` | 31 | `config/parameters.json` (11); `docs/LIMITATIONS.md` (1); `docs/_archive/2026-09/DECISIONS.md` (2); `docs/_audit/2026-09_parameters.md` (7); `docs/phases/F1b_data_quality_audit.md` (1); `src/geofrea/core/schemas.py` (3); `tests/unit/test_config_loader.py` (1); `tests/unit/test_schemas.py` (5) |
| `opex_fixed_frac_of_capex` | 0 | none |

Notes: the 11 occurrences in `config/parameters.json` are 8 field names (4 countries x 2 technologies, including the ZZZ fixture) plus 3 mentions in notes; `opex_fixed_frac_of_capex`, the name chosen in the earlier draft of the summary, no longer appears anywhere (the new `PROJECT_SUMMARY.md` holds no decisions). The two occurrences of `opex_fixed_frac` in `docs/METHODOLOGY.md` are the LCOE formula (M-F6-01) and U-03.

## 5. Parameter inventory (U-03 set plus the F5 to F7 settings)

Proxy flag: a value borrowed from another quantity, technology, region or aggregation level. Tiers are those recorded in `config/parameters.json` (1 = primary source specific to country and technology; 2 = transferred with rationale; 3 = author judgment or weak). 'No range' means `range` is null (0 of 73 entries have one) and no `low`/`high` exists. `verified` is the file's own flag.

| Parameter | Central value | Range | Tier | Source | Open question | Proxy |
|---|---|---|---|---|---|---|
| `capex_usd_per_kw`, solar | PRT 823, BRA 672, IND 691 | none | PRT 2, BRA 1, IND 3 (IND unverified) | IRENA 2025 Table 3.1 (Europe weighted average for PRT, Brazil-specific for BRA); IRENA Table S1 global 2024 average for IND | OQ-017 (CAPEX ranges at commissioning year) | PRT regional, IND global |
| `capex_usd_per_kw`, wind | PRT 976, BRA 976, IND 1041 | none | PRT 2, BRA 2, IND 3 (IND unverified) | IRENA 2025 global average figure (PRT, BRA); Table S1 global 2024 average (IND) | OQ-017 | yes: a global figure used for all three |
| `opex_fixed_pct_of_capex` (U-03 calls it `opex_fixed_frac`), solar | PRT 0.0092, BRA 0.0112, IND 0.0109 | none | PRT 2, BRA 2, IND 3 | IRENA 2025 Fig 3.5 global total O&M 7.54 USD/kW/yr divided by each country's CAPEX | OQ-016 (variable OPEX and the BRA wind proxy) | yes: global O&M over a country CAPEX; total O&M stored as the fixed share |
| `opex_fixed_pct_of_capex`, wind | PRT 0.0348, BRA 0.0077, IND 0.0072 | none | PRT 2, BRA 3, IND 3 | PRT: about 34 USD/kW/yr read off IRENA Fig 2.9 (chart precision caveat); BRA and IND: the SOLAR total O&M figure divided by the wind CAPEX | OQ-016; L-203 | yes: BRA and IND use another technology's O&M (4.5 times below PRT) |
| `opex_variable_usd_per_kwh` | null (pending_research) for all | none | none | IRENA reports one total O&M figure | OQ-016 | n/a |
| `discount_rate`, solar | PRT 0.042, BRA 0.077, IND 0.0708 | none | PRT 2, BRA 2, IND 3 (IND unverified) | IRENA cost-of-capital benchmark tool: Europe average (PRT), South America average (BRA); IND from a secondary summary of the 2023 survey | OQ-022 | PRT and BRA: regional averages, not country values |
| `discount_rate`, wind | PRT 0.037, BRA 0.077, IND 0.0838 | none | PRT 2, BRA 2, IND 3 (IND unverified) | same as solar | OQ-022 | PRT and BRA: regional averages |
| `discount_rate_increment` | 0.0 for all | none | 2 | benchmark-tool methodology (already a final technology value) | none | no (structural, not in U-03) |
| `lifetime_years` | 25 for all (ZZZ 20) | none | 2 | IRENA lifetime table, global | OQ-018 (commissioning year and lifetime ranges) | yes: one global value for every country |
| `degradation_rate` | absent from `parameters.json` | none | none | lead: Jordan and Kurtz (2013), listed in METHODOLOGY references | OQ-019 | n/a |
| `grid_cost_usd_per_mw_km` | absent | none | none | leads and a 3x source conflict in `docs/_audit/2026-10_distance_connection_cost_evidence.md` | OQ-001, OQ-041, L-019 | n/a |
| `substation_cost_usd_per_mw` | absent | none | none | none recorded | OQ-001 | n/a |
| `road_cost_usd_per_km` | absent | none | none | none recorded | OQ-001 | n/a |
| `gamma` (solar) | absent | none | none | none recorded | OQ-023 | n/a |
| `eta_loss` (wind) | absent | none | none | none recorded | OQ-005 | n/a |
| `PD` (power density) | absent | none | none | none recorded | OQ-004 | n/a |
| `LUF` (land-utilization factor) | absent | none | none | none recorded | OQ-004 | n/a |
| Hub height per country | null for PRT, BRA, IND (`config/technologies.yaml`) | none | none | none | OQ-005 (the YAML comments cite OQ-019) | n/a |
| IEC power curves and class rule | `iec_class_rule: null`; no curve stored | none | none | none | OQ-005 | n/a |
| `CF_min` (feasibility) | not set (`capacity_factor_min` empty in `config/experiments.yaml`) | none | none | none | OQ-008 (the YAML comment cites OQ-009) | n/a |
| `tau` (satisficing LCOE) | not set (`satisficing_lcoe_usd_per_mwh` empty) | none | none | none | OQ-008 | n/a |
| `q_ref` (regret quantile) | 0 (`regret_quantile: 0` in `config/experiments.yaml`; default of M-F7-02) | none; test {0, 0.01} planned | none | METHODOLOGY default, no source | OQ-020 | no, a method choice |
| `p_k` (top-k share) | null (`top_k_percent`); candidates 5, 10, 20 percent | none | none | none | OQ-021 (capacity variant: OQ-010) | n/a |

Land-availability parameters (F3) are the only ones with central values and ranges, and are not repeated here: see `config/experiments.yaml` `land_availability` and `docs/_audit/2026-10_f3_parameter_research.md`.

Summary: of the 10 parameters of U-03, 5 have a central value in `parameters.json` (CAPEX, O&M, discount rate, lifetime; variable O&M is null), none has a range, and 5 have no value (degradation, grid, substation, road, gamma/eta_loss). Of the other items, none has a value except `q_ref`. Values flagged as proxies: both wind O&M entries of BRA and IND, all CAPEX of PRT/BRA wind and IND, the O&M of every solar entry (global figure over a country CAPEX), the regional discount rates of PRT and BRA, and the global lifetime.

## 6. What this review did not do

- It did not run the test suite or any phase; statuses rest on reading the code and the recorded runs.
- It did not verify values against their cited sources; tiers and `verified` flags are quoted from `parameters.json`.
- It did not review `docs/CONVENTIONS.md` beyond a search for the removed names (none found), and it found no stale GPPD text in the maintained documents (the remaining mentions in `PROGRESS.json` and `LIMITATIONS.md` are historical and correct).

## Appendix A. Land sensitivity of the candidate set

### A.1 Run

- One run, one process: start (UTC) **2026-10-08T13:08:42+00:00**, commit **ac2ac42** (`ac2ac42ef166eb93638d2ebf465826fe0755109c`), tracked changes in `src/`, `config/`, `main.py`: **none**. Untracked at the time: `docs/PROJECT_SUMMARY.md` and this report.
- Script: `scratchpad/land_sweep.py` (outside the repository). Nothing was written under the repository or `GeoFREA_data`; the only output is a JSON file in the session scratchpad.
- How the override works. `build_eligibility` (`src/geofrea/land_eligibility/pipeline.py:289`) reads only `nominal_set` and writes the F3 outputs unconditionally (`:319`), so it cannot be used for a sweep without overwriting outputs. The pure engine `eligible_fraction(layers, ParameterSet)` (`src/geofrea/land_eligibility/eligibility.py`) accepts any `ParameterSet`, so the script builds the same `EligibilityLayers` as `build_eligibility` from the aligned rasters, the siting layers and the sub-pixel share caches in `interim/` (read only, without key validation) and evaluates `ParameterSet` objects built in memory. No code point blocks this, so the stop condition of the request did not apply.
- Gate before trusting the caches: for every country and technology the central set reproduces the stored `cells_<tech>.parquet` (same cell ids, maximum absolute difference below 0.001 km2) and the stored `candidates_<tech>.parquet` (same cell ids). The script asserts this and would have stopped otherwise.
- Candidate rule: `eligible_area_km2 >= 0.1 km2` per 0.05 degree cell (`min_eligible_area_km2` has no range, so it is 0.1 in every set).

### A.2 The three sets

Ranges used per set: only those with `status: sourced` in `config/experiments.yaml` vary; every other parameter, including the ones declared `range_set_by_douglas_unsourced` or `range_set_by_douglas_literature_lead`, stays at its central value (held, declared below). Direction of restriction: a higher slope maximum, a higher density maximum and a higher minimum river discharge are less restrictive; a larger riparian setback is more restrictive. Categorical parameters (excluded classes, IUCN set) stay central.

| Technology | Set | Slope max (deg) | Density max (persons/km2) | Riparian setback (km) | Min discharge (m3/s) | Held at central although a range exists |
|---|---|---|---|---|---|---|
| solar | central | 10 | 200 | 0.5 | 0 | none |
| solar | least restrictive, sourced ranges | 10 | 200 | 0.25 | 0 | slope_max_deg (range_set_by_douglas_literature_lead); pop_density_max_per_km2 (range_set_by_douglas_unsourced); riparian_min_discharge_m3s (range_set_by_douglas_unsourced) |
| solar | most restrictive, sourced ranges | 10 | 200 | 1 | 0 | slope_max_deg (range_set_by_douglas_literature_lead); pop_density_max_per_km2 (range_set_by_douglas_unsourced); riparian_min_discharge_m3s (range_set_by_douglas_unsourced) |
| wind | central | 16.7 | 200 | 0.5 | 0 | none |
| wind | least restrictive, sourced ranges | 30 | 200 | 0.25 | 0 | pop_density_max_per_km2 (range_set_by_douglas_unsourced); riparian_min_discharge_m3s (range_set_by_douglas_unsourced) |
| wind | most restrictive, sourced ranges | 10.2 | 200 | 1 | 0 | pop_density_max_per_km2 (range_set_by_douglas_unsourced); riparian_min_discharge_m3s (range_set_by_douglas_unsourced) |

The values are the same for the three countries. Note for solar: the central slope maximum (10 degrees) is already the lower end of its 10-15 range, so the most restrictive solar set has no slope room; and the solar slope range is not 'sourced' (its 15 degree end rests on a lead), so only the riparian setback varies for solar in the required table. For wind, slope (10.2-30) and setback (0.25-1.0) vary.

### A.3 Required table (sourced ranges only)

Columns: candidate cells; total eligible area (km2, sum over all cells); Jaccard of the candidate set against the central one; share of central candidates that leave the set; cells that enter the set; and, among central candidates that remain, p10 / p50 / p90 of the ratio (eligible area in the set) / (eligible area at central).

| Country | Technology | Set | Candidates | Eligible area (km2) | Jaccard | Left the set | Entered | Area ratio p10 / p50 / p90 |
|---|---|---|---|---|---|---|---|---|
| BRA | solar | central | 180,041 | 1,535,473 | 1.000 | 0.0% | 0 | 1.00 / 1.00 / 1.00 |
| BRA | solar | least restrictive | 181,897 | 1,767,638 | 0.990 | 0.0% | 1,856 | 1.04 / 1.17 / 1.40 |
| BRA | solar | most restrictive | 173,840 | 1,067,692 | 0.966 | 3.4% | 0 | 0.39 / 0.66 / 0.88 |
| BRA | wind | central | 181,277 | 2,196,099 | 1.000 | 0.0% | 0 | 1.00 / 1.00 / 1.00 |
| BRA | wind | least restrictive | 183,324 | 2,626,748 | 0.989 | 0.0% | 2,047 | 1.05 / 1.20 / 1.61 |
| BRA | wind | most restrictive | 175,154 | 1,437,182 | 0.966 | 3.4% | 0 | 0.32 / 0.60 / 0.84 |
| PRT | solar | central | 3,446 | 21,169 | 1.000 | 0.0% | 0 | 1.00 / 1.00 / 1.00 |
| PRT | solar | least restrictive | 3,486 | 24,052 | 0.989 | 0.0% | 40 | 1.00 / 1.13 / 1.40 |
| PRT | solar | most restrictive | 3,356 | 15,704 | 0.974 | 2.6% | 0 | 0.42 / 0.73 / 0.96 |
| PRT | wind | central | 3,496 | 28,136 | 1.000 | 0.0% | 0 | 1.00 / 1.00 / 1.00 |
| PRT | wind | least restrictive | 3,558 | 35,247 | 0.983 | 0.0% | 62 | 1.04 / 1.25 / 1.92 |
| PRT | wind | most restrictive | 3,369 | 17,562 | 0.964 | 3.6% | 0 | 0.26 / 0.56 / 0.86 |
| IND | solar | central | 54,071 | 146,152 | 1.000 | 0.0% | 0 | 1.00 / 1.00 / 1.00 |
| IND | solar | least restrictive | 56,000 | 166,135 | 0.966 | 0.0% | 1,929 | 1.00 / 1.13 / 1.45 |
| IND | solar | most restrictive | 48,416 | 105,156 | 0.895 | 10.5% | 0 | 0.40 / 0.73 / 0.98 |
| IND | wind | central | 62,696 | 509,298 | 1.000 | 0.0% | 0 | 1.00 / 1.00 / 1.00 |
| IND | wind | least restrictive | 65,436 | 598,112 | 0.958 | 0.0% | 2,740 | 1.02 / 1.18 / 1.95 |
| IND | wind | most restrictive | 56,183 | 354,700 | 0.896 | 10.4% | 0 | 0.31 / 0.66 / 0.93 |

The table has 3 countries x 2 technologies x 3 sets = 18 rows, all from the single run above.

### A.4 What the sourced ranges do

- BRA solar: eligible area -30% to +15% around the central value; candidate-set Jaccard at least 0.966.
- BRA wind: eligible area -35% to +20% around the central value; candidate-set Jaccard at least 0.966.
- PRT solar: eligible area -26% to +14% around the central value; candidate-set Jaccard at least 0.974.
- PRT wind: eligible area -38% to +25% around the central value; candidate-set Jaccard at least 0.964.
- IND solar: eligible area -28% to +14% around the central value; candidate-set Jaccard at least 0.895.
- IND wind: eligible area -30% to +17% around the central value; candidate-set Jaccard at least 0.896.

Reading, with the limits stated: (1) the eligible area moves by 26% to 38% downward and 14% to 25% upward across the sourced extremes, so a reported national range of area (and of capacity, which is area times factors) is wide compared with the climate and cost axes the thesis already treats; (2) the candidate set is far more stable than the area: at least 0.96 Jaccard everywhere except IND, where the most restrictive set drops 10.5% (solar) and 10.4% (wind) of the central candidates (Jaccard 0.895 and 0.896); (3) among the cells that stay candidates, the median area ratio is 0.56 to 0.73 in the most restrictive set and 1.13 to 1.25 in the least restrictive one, so the ranking inputs that use area (capacity) shift more than the membership.

### A.5 Supplement: all ranges, including the unsourced ones

Not part of the requested table. Same run, same rule, but every declared range varies, including density 150-300, discharge 0-10 and the solar slope 10-15 (declared `range_set_by_douglas_unsourced` or `..._literature_lead`). It shows what the unsourced ranges would add if the research confirmed them.

| Country | Technology | Set | Candidates | Eligible area (km2) | Jaccard | Left the set | Entered | Area ratio p10 / p50 / p90 |
|---|---|---|---|---|---|---|---|---|
| BRA | solar | least restrictive, all ranges | 183,782 | 2,207,609 | 0.980 | 0.0% | 3,741 | 1.13 / 1.49 / 2.37 |
| BRA | solar | most restrictive, all ranges | 173,755 | 1,064,969 | 0.965 | 3.5% | 0 | 0.39 / 0.66 / 0.88 |
| BRA | wind | least restrictive, all ranges | 184,462 | 3,016,969 | 0.983 | 0.0% | 3,185 | 1.10 / 1.39 / 2.13 |
| BRA | wind | most restrictive, all ranges | 175,077 | 1,433,780 | 0.966 | 3.4% | 0 | 0.31 / 0.60 / 0.84 |
| PRT | solar | least restrictive, all ranges | 3,536 | 32,637 | 0.975 | 0.0% | 90 | 1.13 / 1.68 / 3.10 |
| PRT | solar | most restrictive, all ranges | 3,314 | 15,339 | 0.962 | 3.8% | 0 | 0.39 / 0.70 / 0.95 |
| PRT | wind | least restrictive, all ranges | 3,574 | 40,841 | 0.978 | 0.0% | 78 | 1.07 / 1.49 / 2.76 |
| PRT | wind | most restrictive, all ranges | 3,333 | 17,150 | 0.953 | 4.7% | 0 | 0.24 / 0.53 / 0.85 |
| IND | solar | least restrictive, all ranges | 73,373 | 258,564 | 0.737 | 0.0% | 19,302 | 1.19 / 1.88 / 5.08 |
| IND | solar | most restrictive, all ranges | 35,949 | 81,681 | 0.665 | 33.5% | 0 | 0.21 / 0.53 / 0.85 |
| IND | wind | least restrictive, all ranges | 79,400 | 1,036,814 | 0.790 | 0.0% | 16,704 | 1.21 / 2.02 / 8.25 |
| IND | wind | most restrictive, all ranges | 42,101 | 226,255 | 0.672 | 32.8% | 0 | 0.12 / 0.42 / 0.77 |

What the supplement shows: in IND the unsourced density range (150-300 persons/km2) is the driver: with all ranges the candidate set falls to a Jaccard of 0.665 (solar) and 0.672 (wind) at the strict end, and 0.737 / 0.790 at the loose end, and the eligible area reaches 1.8 times (solar) and 2.0 times (wind) the central value. In BRA and PRT the supplement adds little on the strict side. So the stability of the F7 candidate set in IND depends on a range that has no source yet (OQ-047).

### A.6 Limits of this appendix

- Extremes of independent ranges are combined (all parameters at the same end at once); these are corner cases, not a sample, and the corners need not be plausible together.
- Only the candidate rule and eligible area were measured; capacity, capacity factor and LCOE do not exist yet (F5 to F6), so 'potential' here is eligible area.
- Resource and distance columns of the candidate table were not recomputed (they are weighted by the central eligible area, as in the design note); they do not enter the membership rule.
- The IND run used the land-cover tiles of about 100 m that the last F3 run used; the 10 m replacement was downloaded but not applied, so the IND numbers may change when it is.
- Caches were read without key validation; the central-set reproduction of the stored outputs is the check that they match the current inputs.
