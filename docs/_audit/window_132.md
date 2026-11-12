# Window 132: what the branch `window-132` changes and what it moves (COMMAND 132)

Written for: the author, to decide whether to merge. **The branch is not merged.** Base: `main` at `2f8740f`. Fingerprints were computed with `closure_fingerprint` (19 phases), `cache_code` (9 caches), `function_fingerprint` (13) and `config_fingerprint` (every phase, PRT, IND, BRA) on the tree of `main` and on the branch.

## 1. What was changed

| item | change | files |
|---|---|---|
| 4a | one log line per layer of `data_acquisition`: resolve time, hash time, number of files. Not in the registry: a wall time there would change the content hash of `layer_registry` at every run | `data_acquisition/phase.py` |
| 4b | F4: `_subset` takes a circular longitude range (a box across the 0/360 seam of a 0..360 file): both sides are kept and the axis is made continuous in -180..180 and ascending; `_to_file_lon` no longer raises "crosses the 0/360 seam". A range with `lo <= hi` goes through the same code as before. F1: `crop_to_country_polygon` reorders the cropped axis to -180..180 only when the longitudes of the kept columns, wrapped, are not ascending in the order of the file (a country across Greenwich); every other country is cropped exactly as before | `climate_forcing/forcing.py`, `data_acquisition/fetchers/cmip6.py` |
| 4c | the DC note in the three `reference_project_mw` of `parameters.json` (OQ-079); OQ-073: `cf_table._grids` without `int(...)` and `cells.block_sum` with its names bound as default arguments, their `noqa` removed; OQ-078: `_SPAWN = mp.get_context("spawn")` for the `Value`, `Process` and `Queue` of `era5.py`, and the Linux skip of the test removed; dead code: `land_eligibility/pipeline.py::_pixel_raster` and the unused `indices_dir` of `group3_problems`; docstrings of `local_layers.py`, `hydrosheds.py` and `phase.py` no longer name tables that do not exist | `config/parameters.json`, `technical_potential/cf_table.py`, `land_eligibility/cells.py`, `land_eligibility/pipeline.py`, `lcoe_modeling/connection.py`, `data_acquisition/fetchers/era5.py`, docstrings |
| 4d | ZZZ3, ZZZ3b, ZZZ3c as ZZA, ZZB, ZZC (section 4) | `config/countries.yaml`, `config/country_names.yaml`, `scripts/zzz3_world.py`, `tests/unit/test_zzz3_miniatures.py`, `data_acquisition/local_layers.py` (fixture names by country code) |

**Not done, and why.** The `Self` return of `RasterStream.__enter__` (OQ-073, `core/raster_io.py`) was tried: it changes the function fingerprint of `aligned_layer.glo30` and `aligned_layer.fabdem_slope` (the layers that took 11,117 s and 4,177 s on BRA) and `aligned_layers`, and the closure of nine phases. It was reverted; one `noqa` stays. The dead-code candidates `draw_backdrop` and `draw_overlay` (`overview/style.py`) are imported by `results_synthesis/style.py`, and `_start_state`, `_posttask` and the `dsk`, `worker_id`, `exc_info` arguments are the signatures the dask callbacks and `__exit__` require: vulture reports them and they stay. No change touches `core/geo_utils`, `core/tables` or `core/paths`.

## 2. What moves

**Code fingerprints of the phases** (13 of 19 change):

| phase | ran on real data | moves because of |
|---|---|---|
| data_acquisition | yes | `phase.py` (log), `local_layers.py`, `era5.py` (spawn), `cmip6.py` (crop) |
| climate_forcing | yes | `forcing.py` (4b) |
| hazard_context | yes | `forcing.py` (through F4) |
| climate_maps | yes | `forcing.py` |
| land_eligibility | yes | `cells.py`, `pipeline.py` (`_pixel_raster`) |
| technical_potential | yes | `cf_table.py`, `forcing.py` |
| potential_maps | yes | `cf_table.py` |
| external_validation | no | `cells.py` |
| lcoe_modeling, lcoe_maps | no | `forcing.py`, `connection.py` |
| robustness_analysis, robustness_maps, sample_size_convergence | no | `forcing.py`, `cf_table.py` |

Unchanged: `data_quality_audit`, `external_inputs`, `grid_alignment`, `siting_layers`, `overview`, `results_synthesis`.

**Caches:** `cf_table` (cheap) and `era5_reduction` (spawn change in `era5.py`: the ERA5 reduction is rebuilt) change. Unchanged: `clip`, `dem30_extremes`, `gadm_mainland`, `gwa_mask_mosaic`, `land_cover_tiles`, `raster_audit`, `subpixel_shares`, **and the 13 function fingerprints, so no aligned layer is rebuilt** (`aligned_layer.glo30` and `fabdem_slope` included).

**Configuration fingerprints** (the DC note in `parameters.json`; the whole country block of the parameters is read by these phases), in PRT, IND and BRA: `land_eligibility`, `technical_potential`, `lcoe_modeling`, `robustness_analysis`, `sample_size_convergence`, `results_synthesis`. The window list of COMMAND 131 said "land_eligibility and F6"; the measurement says six phases. Of them `land_eligibility` and `technical_potential` have run on real data; the other four (`lcoe_modeling`, `robustness_analysis`, `sample_size_convergence`, `results_synthesis`) have not.

**Cost of one round on the branch** (seconds of the cold executions of the manifests): data_acquisition 713, climate_forcing 338, hazard_context 321, climate_maps 169, land_eligibility 821, technical_potential 301, potential_maps 86 = **2,749 s, about 46 minutes for the three countries** (PRT 217 s, IND 1,035 s, BRA 1,497 s), plus the ERA5 reduction. `grid_alignment` and `siting_layers` do not run again. `overview` has no fingerprint change of its own; it reruns only if the content hash of an artifact it requires changes. F6 to F8 have never run on real data, so their share is not counted.

## 3. Profile of `data_acquisition` (IND, `cProfile`, no code changed)

Run in a scratch data directory whose `raw` and `external` are junctions to the real ones, with no hash memo (a cold hash of every source file); the phase function was called directly. **785 s of wall time under the profiler**, against 411 to 422 s in the manifests: the profile ran while `verify_cache_integrity` was reading the same disk and `cProfile` adds its own cost, so the shares are reliable and the seconds are not.

| # | parcel | cumulative | share | where |
|---|---|---:|---:|---|
| 1 | coverage of the GWA files against the country mask (`mask_coverage_pct`, 24 calls of `complete_gwa_to_mask`, 12 layers) | 635 s | 81 % | `fetchers/wind.py:233`; inside it `rasterio.features.geometry_mask` and `rasterize`, 264 calls, 494 s (the country polygon is rasterized again for every file and call); of that, 173 s is `shapely` turning the MultiPolygon into `__geo_interface__` (110 million coordinates iterated) |
| 2 | SHA-256 of the source files (`_hash_layer_files`, 74 files) | 94 s | 12 % | `core/cache_key.py:file_sha256`: 83 s reading the bytes, 6 s in `hashlib.update` |
| 3 | tiles of land cover over the polygon (`resolve_land_cover_tiles`) | 37 s | 4.7 % | 30 s in `shapely.union_all` |
| 4 | the cached protected-areas collection check | 8.7 s | 1.1 % | `protected_planet.py:75`: 7 s decoding JSON |
| 5 | everything else (borders, admin1, registry validation) | about 10 s | 1.3 % | |

Reading, writing and clipping (in the sense of the cache `clip`) are not in the list: the phase writes almost nothing (the GWA completions are cached, `gwa_mask_mosaic`) and no clip runs for IND. **The finding is that hashing, the suspect of COMMAND 131, is 12 %; the cost is the mask coverage, 81 %**: it rasterizes the same polygon 264 times. Rasterizing it once per grid (the 12 GWA files of IND share one grid) and reusing the mask would remove most of it; that is a change in `fetchers/wind.py`, inside the closure of `data_acquisition`, and it was not made here (not requested). The log lines of item 4a will show the same by layer in the next round.

## 4. The miniatures (`tests/unit/test_zzz3_miniatures.py`, 18 tests, all pass)

The three codes are ZZA (ZZZ3), ZZB (ZZZ3b) and ZZC (ZZZ3c): `core/country_guard.py` requires three capital letters for a country code, so `ZZZ3` cannot be a key. Each has its own entry in `config/countries.yaml` with `synthetic_fixture_root` and **only the keys the schema requires** (a test compares the keys with the required fields of `CountryEntry`), and a name in both languages. The fixture file names of `local_layers.resolve_synthetic_fetched_layer` now take the country code (`{iso}`), so ZZA resolves `gadm41_ZZA_0.shp`; ZZZ resolves what it always did.

| case | what is checked | result |
|---|---|---|
| ZZA, 45 W | forcing at lon -45.125 .. -44.875 from a 0..360 file with `dT = 0.5 lon + 0.2 lat`: the interpolated value equals the formula | exact to 1e-9; `delta_rsds` 1.1 and `delta_wind` 1.05 exact to 1e-12 |
| ZZA | grid with no `voltage` attribute: `select_poi` gives 1 substation, 0 with a tag, 1 excluded for no voltage, 0 eligible, and the `poi` layer is not written (`rasterize_linear_distance` returns None) | as stated |
| ZZB, Greenwich | change factors (`dT`, `delta_rsds`, `delta_wind`) from the 0..360 file and from the same field written in -180..180: values and longitude axes equal with `np.array_equal`, and after interpolation to 35 points across the seam too | **bit for bit** |
| ZZB | the same forcing across the seam is the closed form (1e-9), finite everywhere, axis from negative to positive | pass |
| ZZB | F1 crop of a polygon across Greenwich in a 0..360 file: axis `-1, 0, 1`, no NaN, values equal the formula | pass |
| ZZA/F1 | F1 crop of a polygon that does not cross the seam: axis `315, 316`, still 0..360 | pass (unchanged behaviour) |
| ZZA/F4 | a box that does not cross the seam is subset with the file's own values, ascending, no shift | pass |
| ZZC, 65 N | pixel area at 65.195 N: hand value 0.522148688 km2 (1.1125 km by 0.4693 km); the Bowring series of the code is within 1e-6 of the exact ellipsoid (0.5221482 against 0.5221487); row 19 at 65.005: 0.5258744 | pass at 5e-6 |
| ZZC | the cell (5 x 5 pixels): 13.0635 km2 and the exact authalic band area 13.0635 km2 within 1e-6 | pass |
| antimeridian | a polygon drawn past 180, one cut at the seam and one drawn the long way round are refused by `refuse_antimeridian_countries` with the country named; the three miniatures are not | pass |

The code of the pixel area has a relative error of about 9e-7 against the exact ellipsoid (the truncated series of `wgs84_km_per_degree`); the tests pin it at 5e-6. That is a finding of the miniature, not a change.

## 5. The suite and the CI

Ruff 0.17.4: `ruff check src tests scripts main.py` clean. Whole suite once with `-n 2` on the branch: **2,559 passed, 1 skipped, 31 min 51 s**, summed RSS 2,639 MB, lowest free memory 41 MB. A first complete run (2,556 passed, 3 failed) found three consequences of the change, all fixed before the run reported here: the per-layer log called `time.perf_counter`, which a test of the hash replaces by a finite clock (the log now uses `time.monotonic`); the literal `ZZZ` that I put in `local_layers.py` (the fixture names now use `{iso}`); and the word `gem_country_name` in a comment of `countries.yaml`, which the V-06 test reads as a plant-derived value.

CI by `workflow_dispatch` on `window-132` (commit before this note): `Unit tests and lint` passed on Python 3.11 and 3.12 on Linux (2,423 passed, 3 skipped each, ruff clean; **`test_write_annual_maxima_from_hourly_persists_a_readable_netcdf` now runs on Linux and passes**, which was the question of OQ-078), `Synthetic fixture (ZZZ)` and `Regression` passed.
