# Audit of the generality of the code (COMMAND 125)

Written for: the author, to decide what has to change before a fourth country with other geography is added. Read-only: no code was changed and no phase was run. Everything below is from reading the code, the configuration and the manifests of the round 1d34ab23; where something was **not** verified by running it, it says so. State of the code: `main` at the merge of `ast-normalize` (commit `32c3106`).

## Summary

- **Country literals (step 1):** 263 occurrences of `BRA`, `PRT`, `IND` or `ZZZ` in `src`, `main.py` and `scripts`. **None is in executable code of `src` or `main.py`** (no quoted ISO code, no comparison on `iso`, no country-keyed table): 137 are comments, docstrings and usage text (class a). The other 126 are in `scripts`: 99 of class a, 4 of class b, 23 of class c (table below).
- **Region-dependent constants (step 2):** the grid, the pixel area (exact geodesic row by row) and the distances (exact geodesic) are global. The regional assumptions are: one UTM zone by the longitude of the centroid, a longitude that is continuous in -180..180, and a bounding box that does not cross the 0/360 seam. 5 items of class b, 4 of class c, 9 checked and global (table in section 2).
- **Per-country configuration (step 3):** 6 files hold per-country mappings. `parameters.json`, `experiments.yaml` (riparian, national targets) and `audit.yaml` are validated by Pydantic with `extra="forbid"`. **`countries.yaml` and `country_names.yaml` have no schema:** an unknown key is ignored without a message, and an absent key takes the default of the reader.
- **Optional national layer (step 4):** not accepted by configuration. A layer like REN needs code in the registry of F1, in F2a, in F3 (the six exclusions E1 to E6 are fixed) and in the figures.
- **Cache and fingerprint (step 5):** the layer keys of F2a hold the inputs by content and the configuration values they pass, the polygon of the country and the code; but **the configuration fingerprint of a phase does not cover everything the phase reads:** F2a does not name the substation voltage thresholds of `parameters.json`, F3 does not name the reference project, the power density and the PVCZ settings. A change of those values does not run the phase again.
- **Scale (step 6):** by arithmetic, upper bound, assuming what is above the process floor grows with the size of the country: of the 10 phases measured, 5 are already above the cap on BRA and 7 are above it or reach it at less than 3x; F3 reaches it at 1.4x because of whole-grid arrays.
- **Geometry (step 7):** no handling of the antimeridian, of countries with more than one UTM zone, nor of latitudes beyond 84 N and 80 S. Two places refuse with a named error (`acquisition_area.py`, `climate_forcing/forcing.py`).

### Defects of generality, from the most to the least serious

Ordered by the chance that a new country gets a wrong result without a message first, then by the chance that it stops with one, then by the cost of the fix. The ranking is a judgement, not a measurement.

1. **The configuration fingerprint omits values that F2a and F3 read** (class b, step 5). Silent: the phase is resumed with the old result. F2a reads `parameters.countries.<iso>.connection.poi_voltage_threshold_kv` and `poi_sensitivity_threshold_kv`; F3 reads `connection.reference_project_mw`, `technologies.*.power_density_mw_per_km2` (the project area of the restrictive scenario) and `settings.geospatial.pvcz_csv`, `pvcz_max_distance_km`. None is in `PHASE_CONFIG_SCOPE`; `tests/unit/test_config_fingerprint.py` checks that the named sections exist, not that the scope covers what the phase reads. It is general (every country), not specific to one.
2. **`countries.yaml` has no schema** (class c, step 3). Silent: `load_countries` returns the parsed YAML; `mainland_only` is read with `.get("mainland_only", False)`, so a misspelt key leaves the islands in the country; an unknown key is never reported. A new country is an entry of this file.
3. **`get_local_utm_crs` takes one zone from the longitude of the centroid** (class b, step 7), used for the contiguous-territory rule (1 km gap) and the vector statistics of F1b. Silent: a country that crosses the antimeridian (its polygons are cut at +-180) gets a zone near 0 degrees, and no zone exists beyond 84 N or 80 S. The exact distance layers do not use it.
4. **A bounding box that crosses the 0/360 seam stops F4** (class b, step 7): `climate_forcing/forcing.py::_to_file_lon` raises `MemberResolutionError`. It happens for a country that straddles Greenwich when the member files are in 0..360 (the code supports both conventions), and for one that crosses 180 in either. Loud, but it excludes every country on the prime meridian with such files (not verified which convention the member files of the three countries use).
5. **Memory: 7 of the 10 measured phases do not fit a country 3x the size of BRA** (class b, step 6). Loud (the guard waits, then the process dies), and `config/memory_budget.json` is calibrated on BRA as the largest country.
6. **The lattice and the grid assume a continuous longitude** (class b, step 7): `cell_id = row * 7200 + col`, `lattice_window` and `build_reference_grid` work on `total_bounds`; a country cut at +-180 would give a grid that spans the globe. Not run; from the code.
7. **The substations file of the country is optional without a message** (step 1, `main.py::_substation_source`): when `external/osm_substations/{iso}_substations_osm.geojson` is absent the raw grid extract, with points only, is used (OQ-067). By design and documented in the docstring; I did not find a flag for it in the code that was read (not run), so a new country can get another source quality without a message.
8. **Data per country written in scripts** (class c, 23 occurrences): `scripts/profiling/measure_layer_memory.py` repeats the POI thresholds of `parameters.json` (`{"BRA": 138.0, "PRT": 150.0, "IND": 220.0}`), `place_w5e5_tasmax.py` names the W5E5 files of the three countries, `report_poi_counts.py` and `audit_potential.py` hold per-country thresholds and texts.
9. **No extension point for a national layer** (step 4), a missing feature and not a defect of what exists.
10. **Documentation drift:** the docstrings of `data_acquisition/local_layers.py` and `fetchers/hydrosheds.py` still describe the tables `_ELEVATION_COUNTRY_DIRS`, `_LAND_COVER_COUNTRY_DIRS`, `_ROADS_COUNTRY_REGION_DIRS` and `_COUNTRY_TO_REGION`, which no longer exist (the data is in `config/countries.yaml`); `viz/examples.py` reads `tests/fixtures/archetypes` from `src`.

## 1. Country literals in the code

Search: `git grep -nw -E "BRA|PRT|IND|ZZZ"` over `src`, `scripts` and `main.py`, then by hand: quoted ISO codes (`"BRA"` and the like), comparisons and memberships on `iso`/`country_code`, country names, and tables keyed by country. Class a is a label, log, comment, docstring, usage text, a default of a command-line argument or the code of the fixture of the synthetic country; class b is country-specific logic in the code; class c is data that should be in the configuration.

| group | a | b | c | total |
|---|---:|---:|---:|---:|
| `src` and `main.py` | 137 | 0 | 0 | 137 |
| `scripts`, fixtures of the synthetic country (`generate_zzz_fixture`, `zzz_climate_fixture`, `generate_zzz2_fixture`, `zzz2_world`) | 39 | 0 | 0 | 39 |
| `scripts`, the others | 60 | 4 | 23 | 87 |
| **total** | **236** | **4** | **23** | **263** |

**`src` and `main.py`.** Every occurrence was read. The quoted-literal search finds three, all in docstrings (`reference_store.py:15`, `hydrosheds.py:109`, `local_layers.py:226`); the search for comparisons (`iso ==`, `country_code in`) finds none; the country names (Brazil, Portugal, India, Pamban, Madeira) are in comments and docstrings. The occurrences are of three kinds: usage text and help of `main.py`; the history that justifies a decision (`BRA: peak 2.9 GB`, `IND roads from the wrong GRIP4 region`); and the files that carry such history (`core/geo_utils.py`, `data_acquisition/fetchers/era5.py`, `local_layers.py`, `grid_alignment/raster_alignment.py`, `land_eligibility/fractions.py`). **No logic branches on the country.** The synthetic country is recognised by `synthetic_fixture_root` in `config/countries.yaml`, not by its code (`main.py:1639`, `local_layers.py:292`).

**`scripts`, class c (23) and b (4).** The class is by the file; the default countries of a command line (`["PRT", "IND", "BRA"]` in `acquire_dem30.py`, `acquire_fabdem.py`, `check_manifests.py`, `verify_cache_integrity.py` and others) are counted as a, although they repeat the list of `parameters.json` and would have to be changed when a country is added.

| file | class | what it does |
|---|---|---|
| `place_w5e5_tasmax.py:27-29` | c | the name of the W5E5 file (a box of longitudes and latitudes) of each of the three countries |
| `profiling/measure_layer_memory.py:32` | c | `POI_THRESHOLD_KV = {BRA: 138, PRT: 150, IND: 220}`: the thresholds of `parameters.json` repeated |
| `report_poi_counts.py:23-24` | c | expected counts of substations by country |
| `audit_potential.py:38-48` | c | a text per country |
| `audit_slope_dem_test_100.py:54-60` | c | tile -> (country, description), 7 tiles |
| `make_archetype_fixtures.py:29-31`, `make_style_guide_examples.py:28-29` | c | the shape and the variable of the style-guide examples, per country |
| `proofs/check_polygon_derived_equivalence.py`, `check_population_strips.py`, `check_raster_step_equivalence.py` | c | `DEFAULT_WINDOWS`: the test window of each country |
| `derive_bra_bay_cost_bpr.py` | b | derives the bay cost of BRA from the ANEEL BPR: a script of a single country by construction |
| `acquire_worldcover10m.py:1,3,24` | b | downloads the 10 m tiles "for IND" with the tile names of the local set; the mechanism (`esa_worldcover.load_tiles`) is general, the script defaults to IND |

## 2. Constants that depend on the region

| item | where | verdict | class |
|---|---|---|---|
| Lattice 0.05 degree, 5 x 5 pixels, origin 90 N, 180 W | `core/constants.py` | global | checked, global |
| Area of a pixel by row, WGS84 geodesic (Bowring series) | `core/geodesy.py`, `land_eligibility/cells.py::pixel_row_area_km2` | valid at any latitude; its test at PRT and BRA latitudes only | checked, global |
| Distances to grid, roads, rivers, POI | `grid_alignment/vector_alignment.py` (COMMANDS 115 to 117) | exact geodesic, no projection | checked, global |
| Equal-area EPSG:6933 for areas of polygons | `core/geo_utils.py:322` | global | checked, global |
| Source names: ESA WorldCover tile names, GRIP4 `GP_RTP`, GEM `Country/area`, `gadm41_<ISO>_shp`, GWA, ERA5, GLO-30 | fetchers | global products | checked, global |
| Population file `population/<ISO>/<iso>_pop_2020.tif` | `local_layers.py::resolve_population_path` | a convention of the local database; a new country needs the file at that path, no code | checked, global |
| `WIND_HEIGHTS_M`, `REFERENCE_PERIOD`, ISA constants, `HOURS_PER_YEAR` | `core/constants.py` | global | checked, global |
| `MAINLAND_MAX_GAP_KM = 1.0`, `GWA_COVERAGE_MIN_PCT = 99`, `_MIN_OVERLAP_DEG2` | `geo_utils.py`, `wind.py`, `local_layers.py` | one value for every country, in code; `mainland_only` and `gwa_neighbours` are per country in the configuration | checked, global |
| `distance_cap_km`, `poi_line_tolerance_m`, `pvcz_max_distance_km`, `road_classes` | `settings.yaml` | in configuration | checked, global |
| One UTM zone by the longitude of the centroid (`(lon + 180) // 6 + 1`, 326/327 by sign of the latitude) | `core/geo_utils.py:251-288`, used at 306, 326, 440 and `vector_inspection.py:290` | no antimeridian, no polar zones, one zone for a country of several | **b** |
| A box with `west < east` is required | `data_acquisition/acquisition_area.py:31` | refuses a box that crosses 180 | **b** |
| `_to_file_lon` raises when the box crosses the 0/360 seam | `climate_forcing/forcing.py:95-100` | see defect 4 | **b** |
| `cell_id = row * n_cols + col`, `n_cols = 7200`; `lattice_window` | `land_eligibility/cells.py:63`, `core/scale.py` | a column beyond 7199 (a continuous longitude past 180) collides with the next row | **b** |
| Grid of F2a from `country_gdf.total_bounds` | `grid_alignment/raster_alignment.py:953,1130` | continuous longitude assumed | **b** |
| `COUNTRY_COLOURS` has 6 colours, cycled | `technical_potential/question_figures.py:66` | a seventh country repeats a colour | **c** |
| Names of the countries for the titles | `config/country_names.yaml` (3 countries) | absent: `ValueError` in `viz/mapstyle.py:1341` | **c** (in configuration, no schema) |
| The memory of every kind of layer, measured on BRA | `config/memory_budget.json` | the guard waits for the BRA figure; another country has another | **c** |
| `config/deferred_checks.yaml` (IND, BRA, PRT) | `core/deferred_check.py:416` | `.get(iso)`: a country without an entry is not checked | **c** |

Total: 5 of class b, 4 of class c, 9 checked and global. Not audited: the thresholds inside `config/audit.yaml` (the expected pixel sizes of the products are those of global products).

## 3. Per-country configuration

`config/` has 10 files; 6 hold mappings keyed by country. A country is run when it is in `parameters.json` (or in `run.countries` of `settings.yaml`) **and** in `countries.yaml` (`main.py:1640-1650`: an unknown code returns 1).

| file | key by country | what it controls | required | schema | absent / unknown key |
|---|---|---|---|---|---|
| `countries.yaml` | `<ISO>` (entry) | the country exists for F1 | yes | **none** (`load_countries` returns the parsed YAML) | absent: `CountryMappingError` (`_require_country`, `local_layers.py:251`); unknown key: **ignored** |
| | `hydrosheds_region` | HydroRIVERS tile code | for rivers | none | null or absent: `CountryMappingError` |
| | `grip4_region_dir`, `grip4_region_file` | GRIP4 folder and file of the roads | for roads | none | null or absent: `CountryMappingError` |
| | `gadm_dir`, `gadm_level0_sha256` | the pre-placed GADM set and its checksum | optional | none | null or absent: falls through to the network; a different hash: `GadmChecksumMismatchError` |
| | `mainland_only` | only the contiguous territory | optional, default false | none | absent: false, **silently** |
| | `excluded_land_cover_tiles` | WorldCover tiles left out (BRA: 40 names) | optional | none | absent: empty |
| | `gwa_neighbours` | GWA files of the neighbours that complete the country file (IND: PAK, CHN) | optional | none | absent: the country file as it is |
| | `synthetic_fixture_root` | marks the synthetic country | optional | none | absent: a real country |
| | `gem_country_name` | the GEM spelling, read by `scripts/acquire_gem_trackers.py` only | for that script | none | `KeyError` in the script; no phase reads it |
| `parameters.json` | `countries.<ISO>.technologies.{solar,wind}.*` | capex, O&M, lifetime, discount rate, power density, with source and tier | yes for both technologies | **Pydantic, `extra="forbid"`** (`core/schemas.py`) | absent required: `ValidationError`; unknown key: `ValidationError` |
| | `countries.<ISO>.connection.*` | substation threshold, reference project, tortuosity, losses, line, bay and road costs | optional (`None`); F6 refuses a country without it | same | same |
| `experiments.yaml` | `land_availability.riparian.countries.<ISO>` | riparian buffer by scenario | yes for F3 | Pydantic (`CountryRiparian`, `extra="forbid"`) | absent: `LandEligibilityError` "has no entry for iso" (`scenarios.py:119`) |
| | `national_targets.<ISO>.<tech>` | national target of H5 | optional | Pydantic (`NationalTarget`) | absent: the decision records "national_targets has no value" |
| `audit.yaml` | `country_overrides.<ISO>.<layer>` | replaces the expected values of a layer | optional | Pydantic (`AuditConfig`) | absent: `{}`, the global values |
| `deferred_checks.yaml` | `countries.<ISO>` | baseline and phases of the deferred content check | optional | none | absent: not checked |
| `country_names.yaml` | `en.<ISO>`, `pt.<ISO>` | name in a figure title | for figures | none (`yaml.safe_load`) | absent: `ValueError` at the title |
| `settings.yaml` | `run.countries` | the countries of a run | optional | Pydantic (`RunConfig`) | absent: the countries of `parameters.json` that are not synthetic |

Required for a new real country: an entry in `countries.yaml` (`hydrosheds_region`, `grip4_region_dir`, `grip4_region_file` for the layers that need them), `parameters.json` (both technologies), `experiments.yaml` riparian, `country_names.yaml` for the figures. Optional: `connection` (without it F6 refuses), `national_targets`, `audit.yaml` overrides, `gadm_*`, `mainland_only`, `gwa_neighbours`, `excluded_land_cover_tiles`.

**Technologies are not per-country configuration:** `TechnologyParams` declares `solar` and `wind` as fields, so a third technology is a change of the schema.

## 4. A layer or restriction that only one country has

**The code does not accept an optional layer declared in the configuration.** What exists:

- F1 resolves the layers of a fixed registry (`data_acquisition/phase.py::_LAYER_REGISTRY`), with a handler per layer name (`_LOCAL_PATH_HANDLERS`, fetchers).
- F2a builds a fixed set of aligned layers in `alignment.py`; one derived layer depends on the configuration, `poi_sensitivity`, and exists because `connection.poi_sensitivity_threshold_kv` is not null (IND, 132 kV): a threshold, not a new source. The manifest accepts it as optional (`main.py:489`: "layers a country has only when its parameters ask for them").
- F3 has **six fixed exclusions** (`land_eligibility/eligibility.py:31`, `EXCLUSION_NAMES = ("E1", ..., "E6")`), whose names enter the columns `excluded_area_km2_E*` of the cell tables, the figures (`figures.py`) and the schemas.
- The settings accept a path pattern per country for one input (`geospatial.poi_substations_geojson: external/osm_substations/{iso}_substations_osm.geojson`), which is a convention of file name, not a layer.

A national layer such as REN for PRT would need: a fetcher and a registry entry (F1); an aligned layer and its key (F2a); a seventh exclusion or a merge into E3 or E5, with the columns, the schema version and the figure labels (F3); the scenarios in `land_availability`; and the tests. **It cannot be added by configuration alone.**

## 5. Cache and fingerprint

Three keys decide whether something is recomputed.

**(i) Phase: the configuration fingerprint.** `core/config_fingerprint.py::config_fingerprint(phase, iso, source)` is the SHA-256 of the sections that `PHASE_CONFIG_SCOPE[phase]` names, taken from the validated files; `{iso}` in a selector (`countries.{iso}`, `parameters: countries.{iso}`) is replaced by the country. The orchestrator compares it with the recorded one (`core/orchestrator.py:1076-1097`: `config_changed = existing.config_fingerprint != spec.config_fingerprint`; a phase with another fingerprint is executed again). The code fingerprint is compared on the next lines (`code_changed`). **Yes, it includes the configuration of the country** for `data_acquisition` (`countries.<iso>`) and for the phases that read `parameters.countries.<iso>` (F5, F6, F7); `countries` and `published_potential` enter as parsed, without a schema.

**What the scope leaves out although the phase reads it** (the values can change without invalidating the phase; the files are read at `main.py`):

| phase | read at | not in its scope |
|---|---|---|
| `grid_alignment` (scope: `settings.geospatial`) | `main.py:414-430` | `parameters.countries.<iso>.connection.poi_voltage_threshold_kv` and `poi_sensitivity_threshold_kv` |
| `land_eligibility` (scope: `experiments.land_availability`) | `main.py:615-636`, `_zone_source` `main.py:369` | `parameters.countries.<iso>.connection.reference_project_mw`, `technologies.*.power_density_mw_per_km2`, `settings.geospatial.pvcz_csv`, `pvcz_max_distance_km` |
| any phase | | `country_names.yaml`, `memory_budget.json`, `deferred_checks.yaml` are not in `CONFIG_FILES` (labels, scheduling and a check: not a result) |

The tests of the scope (`test_config_fingerprint.py`) check that every phase has a scope and that every section it names exists; they do not compare the scope with what the phase reads.

**(ii) Internal caches: `core/cache_key.py::cache_key(algorithm_version, input_files, config, memo, code=...)`.** The SHA-256 of the algorithm version, the hash of every input file, the values the caller passes as `config` and the code fingerprint of the cache (`cache_code`, `core/cache_code.py`). It does **not** include the configuration fingerprint of the phase: it holds only what each caller passes. The aligned layers of F2a pass (`grid_alignment/alignment.py:346-352`) the resolution, the nesting, the SHA-256 of the country polygon and, by layer, `distance_cap_km`, the POI threshold and tolerance, the road classes (the key of the POI layer does hold `poi_voltage_threshold_kv`: a forced rerun of the phase would compute it again). The clip caches (`core/geo_utils.py::clip_cache_key`) hold the source file, the polygon and the code; `mainland_only` enters through the polygon.

**(iii) Cache of the phase outputs and references:** the manifest records `config_fingerprint` and `code_fingerprint` per phase entry (schema 2.5 and 2.6); an entry without them is resumed and adopts the current ones (`orchestrator.py:1103-1109`).

So: the configuration that can change without invalidating the cache is (a) what the two rows above name, (b) in a cache key, anything the builder reads and the caller does not pass in `config` (not found in F2a, not audited in the other caches), (c) the three files outside `CONFIG_FILES`.

## 6. Scale

**Model.** For a phase that does not work by stripes, memory above the floor of the process grows with the size of the country: pixels (BRA 15.3 M), candidate cells (BRA 286 k), forcing rows (BRA 10.58 M, 37 members). The arithmetic is `peak(k) = 247 + k x (P_BRA - 247)` MB, with `P_BRA` the measured peak (manifest, round 1d34ab23, or the measurement of `f5_peak_measured.md`) and `247` MB the resident set of the process at the start of a phase (measured: `f5_peak_measured.md`). It is an **upper bound**: it assumes the whole variable part grows linearly with the area (members, 37 or 31, do not grow). The cap is 1536 MB (`config/memory_budget.json`). **No measurement was made for this section.**

| phase | memory grows with | by stripes or windows | BRA peak (MB) | at 3x BRA (MB) | at 10x BRA (MB) | reaches 1,536 MB at |
|---|---|---|---:|---:|---:|---|
| data_acquisition (F1) | area of the boxes (ERA5, GWA, CMIP6 crops), tiles | partly: ERA5 in batches, downloads streamed | 782 (round 1d34ab23) | 1,852 | 5,597 | 2.4x BRA |
| data_quality_audit (F1b) | pixels (windowed statistics) and vector features (clips whole) | rasters yes, vectors no | 1,152 (round 1d34ab23) | 2,962 | 9,297 | 1.4x BRA |
| external_inputs | files checked, nothing else | n/a | 303 (round 1d34ab23) | 415 | 807 | 23.0x BRA |
| climate_forcing (F4) | cells x members (forcing rows) | no | 565 (round 1d34ab23) | 1,201 | 3,427 | 4.1x BRA |
| climate_maps (F4) | pixels and members (one figure per member) | no | 2,333 (round 1d34ab23) | 6,505 | 21,107 | already above the cap at 1x |
| hazard_context (F4) | pixels (bands of latitude rows, a fifth of the grid at a time) and members | partly, by bands of rows | 2,728 (round 1d34ab23) | 7,690 | 25,057 | already above the cap at 1x |
| overview | tables by member, pixels (maps of the layers) | no | 2,041 (round 1d34ab23 (entry stale_upstream, run of 2026-11-07)) | 5,629 | 18,187 | already above the cap at 1x |
| siting_layers (F2b) | pixels, one layer at a time | layer by layer | 272 (round 1d34ab23) | 322 | 497 | 51.6x BRA |
| technical_potential (F5) | candidate cells x members (forcing, pieces, table), pixels of the candidate cells (wind) | no | 2,307 (F5 alone in a new process, `f5_peak_measured.md`; 3,410 in the round) | 6,427 | 20,847 | already above the cap at 1x |
| potential_maps | rows of the potential tables, figures | no | 2,548 (round 1d34ab23) | 7,150 | 23,257 | already above the cap at 1x |

**F3 (`land_eligibility`), by stripes of rows** (`land_eligibility/windows.py`): the reading of the rasters, the exclusions and the cell sums are bounded by the stripe (`GEOFREA_F3_STRIPE_PIXELS`, 4 M pixels). What is not: the clusters of the minimum area are labelled on the whole grid (`min_area.py`: "the eligible fraction of the whole grid is held as one float32 array and the labels as one int32 array (BRA: about 70 MB each)"). With only those two arrays growing, the BRA peak of 1,481 MB becomes 1,761 MB at 3x and 2,741 MB at 10x, and reaches the cap at 1.39x BRA (a lower bound: the other whole-grid and per-cell arrays are not decomposed in any document).

**F2a, layers in child processes** (cap 1,536 MB each, `config/memory_budget.json`): the raster layers (`glo30` 984, `fabdem_slope` 942, `land_cover` 1,473, `land_cover_counts` 1,207, `population` 742, `solar` 409, `wind` 610, `settlements` 315) work by strips and warp chunks (`warp_mem_limit_mb`), so they do not depend on the size of the country in the first order; the strip is a whole row, so what grows with the width (the root of the area) was not decomposed. The vector layers hold the vector: for `rivers` (1,221 MB; the vector is about 400 MB on BRA, `vector_alignment.py:530`) the arithmetic is 821 + k x 400 = 2,021 MB at 3x and 4,821 MB at 10x, reaching the cap at 1.8x. `grid` (744), `poi` (449), `roads` (848) and `lakes` (376) are not decomposed in any document: no arithmetic is possible.

**F6, F7, F8 (`lcoe_modeling`, `sample_size_convergence`, `robustness_analysis`, `external_validation`, `lcoe_maps`, `robustness_maps`, `results_synthesis`)** never ran on real data of BRA or IND; their peaks are not measured. By design the cell-by-sample arrays of F6 and F7 are cut in blocks that fit `memory.max_batch_gb` (1 GB, `settings.yaml`), so they do not grow with the country in the first order; the tables of candidate cells that they hold whole grow with the cells. F7b (`external_validation`) calls `prepare_shared_layers`, which holds the shared layers of F3 whole: about 1.5 GB for BRA before any plant (OQ-068), that is, by arithmetic about 4.5 GB at 3x and 15 GB at 10x for that part alone.

Phases that do not work by stripes: F1b (vectors), F4 (`climate_forcing`, `climate_maps`, partly `hazard_context`), F5, `potential_maps`, `overview`, F7b, and the vector layers of F2a.

## 7. Geometry

| case | handling in the code | evidence | what happens |
|---|---|---|---|
| **Antimeridian** | none | `acquisition_area.py:31` requires `west < east`; `climate_forcing/forcing.py:95-100` raises for a box that crosses the seam; `get_local_utm_crs` takes the centroid of coordinates in -180..180; `cell_id` and `lattice_window` assume columns 0 to 7199; the grid of F2a comes from `total_bounds` | F1 and F4 stop with a message; F1b and the territory rule would take a wrong UTM zone with no message; a grid from `total_bounds` of a polygon cut at +-180 would span the globe (not run) |
| **Greenwich** (a country that crosses 0 degrees) | partial | `_to_file_lon` converts a negative longitude to 0..360 when the file is in that convention; then `lo > hi` raises. `bilinear_to_points` and `_with_periodic_longitude` do handle the seam in the interpolation | F4 stops with `MemberResolutionError` if the member files are in 0..360; with -180..180 files it works (not verified which convention the files of the three countries have) |
| **More than one UTM zone** | one zone from the centroid | `get_local_utm_crs` | distortion at the edges of a wide country (BRA spans about 8 zones); it is used for a 1 km threshold of the territory rule and for the vector statistics of F1b; areas and distances elsewhere are geodesic, not projected |
| **Latitudes above 60 degrees** | the area by pixel row is geodesic (`pixel_row_area_km2`), the distances are exact geodesic, the pixel is 0.01 degree | `core/geodesy.py`, `land_eligibility/cells.py:88` | the pixel narrows with the cosine of the latitude and the area follows; correct by construction; not run. The Bowring coefficients were checked at 39 N and between 10 S and 30 S only |
| **Latitudes beyond 84 N or 80 S** | none | `get_local_utm_crs` builds `EPSG:326xx` or `327xx` | no UTM zone exists there (UPS); only the territory rule and the F1b statistics are affected |
| **Southern hemisphere** | yes | `hemisphere = 326 if lat >= 0 else 327`; BRA and the ZZZ fixture (lat -5) run | works |
| **Coverage of the global products by latitude** (WorldCover, PVOUT, GWA, GHSL) | not encoded | the code does not state the latitude range of any product; F1b audits the share of the country mask covered (99 %, `_COVERAGE_REQUIRED_LAYERS`) | a country beyond the extent of a product is caught by the audit, not by a check on the latitude (the extents were not verified here) |

## 8. Acceptance test proposed: the synthetic country ZZZ3 (not implemented)

The existing synthetic countries ZZZ and ZZZ2 have the same extent: longitude 20.0 to 20.3, latitude -5.0 to -4.8, 30 x 20 pixels, in one UTM zone, on the equator side of the southern hemisphere, with the voltage attribute and the layers of a normal country. ZZZ3 is meant to break what sections 1 to 7 found fragile, on a miniature that runs in minutes.

| fragility | what ZZZ3 does | what it must show |
|---|---|---|
| southern hemisphere at a latitude where the pixel area differs | latitudes -45.0 to -44.8 | area by row, distances and UTM sign; the sum of the areas equals the geodesic area of the polygon |
| crosses the antimeridian | longitudes 179.85 to 180.15, the polygon cut in two at 180 (as in GADM) | what stops (the boxes of F1, the forcing of F4) and what goes on with a wrong value (the UTM zone, the grid): the test fixes the expected behaviour first, even if it is an error with a message |
| crosses the prime meridian in a second variant ZZZ3b | longitudes -0.15 to 0.15, climate files written in 0..360 | `_to_file_lon` |
| more than one UTM zone | a polygon of 8 degrees of longitude at a mid latitude (in a miniature at coarse pixel, only to test the zone) | the zone rule and the 1 km territory test at the edge of the zone |
| latitude above 60 | a variant ZZZ3c at 65 N, and one beyond 84 N | the pixel area, the cell area at 0.05 degree, the UTM or the refusal |
| no voltage attribute in the grid | the grid layer without `voltage` and without a substations file | the substations are taken from the lines (`poi_line_tolerance_m`), the fallback is flagged in the manifest and does not pass without a message |
| no national layer | `countries.yaml` without `gadm_dir`, `mainland_only`, `gwa_neighbours`; `connection` absent; no `national_targets`; no `audit` override | each absent key takes its documented behaviour; F6 refuses a country without `connection`; the optional keys do not change a result |
| a key that is not in the schema | a misspelt `mainland_onlly` | today ignored; the test records the current behaviour and fails when `countries.yaml` has a schema |
| the configuration changes | change `poi_voltage_threshold_kv`, `reference_project_mw` and `pvcz_max_distance_km` of ZZZ3 between two rounds | the phases that read them run again; today F2a and F3 do not (defect 1) |
| a country larger than BRA by arithmetic | not by size: a variant with a grid of 3 x the pixels of the ZZZ grid, to test that the stripes give the same value as the whole grid | equivalence at tolerance 0 of the F3 stripes and of the windows proposed for F5 |

Expected data: every value computable by hand, as in ZZZ (`generate_zzz_fixture.py`), with a separate expected-values file; a new `countries.yaml` entry with `synthetic_fixture_root`, so it never enters the default country list.

## What was not verified

- Nothing was run: the behaviour at the antimeridian, at Greenwich, beyond 84 N and with a larger country is from the code.
- The convention of longitude (0..360 or -180..180) of the member files of the three countries.
- The latitude extents of the global products.
- The 99 occurrences of class a in `scripts` were classified by file; the 27 of class b and c were read line by line.
- The scale arithmetic is an upper bound with a single floor; F6 to F8 have no measure.
