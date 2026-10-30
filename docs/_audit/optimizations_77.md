# Optimizations 77: item by item, with the proof and the gain

COMMAND 77 (branch `perf/77`, from the ranked list E of `docs/_audit/profile_76.md`), corrected by COMMAND 79, merged with COMMAND 80. The whole-country
times of IND and BRA are in `docs/_audit/performance_75.md`; this file has the isolated gain and the proof of each item.

Rule: one change per commit; the proof is the canonical content hash of what the changed code writes, against the code before the change, on the same input
(the clips by `equals_exact` at tolerance 0, the figures by pixels); an item whose proof fails is not applied and its evidence stays in `docs/_audit`.
Items 11 (block sum of the population) and 12 (cKDTree for the distances) of the list were forbidden by the command and were not touched.

## Applied

| Item | Change | Proof | Isolated gain |
|---|---|---|---|
| **a** (1a) | In the clip, a **simple LineString** that the country polygon wholly covers is kept as it is instead of intersected (`core/geo_utils._not_covered_lines`). Restricted by COMMAND 79 (see below). | PRT, hash of the clip: `clip_equivalence_1a_PRT.json` (roads 178,986 features, rivers, lakes equal). IND whole layers, `equals_exact` tolerance 0, against the clips made before COMMAND 77: `protected`, `roads`, `rivers`, `lakes` equal (`clip_layers_equivalence_IND.json`). | PRT roads 117.4 s to 9.0 s wall (109.5 s to 8.8 s CPU); rivers 5.3 s to 2.4 s; lakes unchanged |
| **b** (2) | The audit, F2a and F3 read one clip: `current_clip_cache` returns the phase's own cache, else the audit's copy when its key is current | `shared_clip_equivalence_item2_PRT.json`: every aligned artifact equal | the clip is made once per country and layer; not timed apart (it is part of the cold audit, F2a and F3 of the round) |
| **c** (4) | The contiguous territory of a country (`get_contiguous_mainland_gdf`) is cached in `interim/_mainland_cache/<key>.wkb`; the union of the country geometry is computed once per process (`core/geometry_memo.country_union`) | `mainland_equivalence_item4.json`: WKB hash of the territory and of the union equal in PRT, IND and BRA, cold and warm | warm read: PRT 9.2 s to 0.26 s, IND 55.0 s to 0.35 s, BRA 24.6 s to 0.32 s; the cold computation costs the same |
| **d** (7) | The digest of each source file of the code fingerprint is kept between processes in `interim/_code_digest_cache.json` (key: size, mtime, Python version and the bytes of the module) | `tests/unit/test_code_fingerprint.py`: same fingerprints with and without the store; a changed file is read again | not timed apart |
| **e** (8) | The GLO-30 tiles of the strip pass are kept open (`raster_alignment._TileHandles`, LRU of 12) | `glo30_equivalence_item8.json`: elevation, slope and slope bins equal (content hash) in PRT, IND and BRA windows | opens 162 to 15 and CPU 22.3 s to 10.7 s (PRT, 2 x 2 degrees); 7.27 s to 2.88 s (IND, 1 degree); 6.52 s to 2.81 s (BRA, 1 degree) |
| **h** | `viz.mapstyle.quiet_figure`: `canvas.draw_idle` is replaced by a no-op on the figures of `mapstyle`, `panels` and `charts` (geopandas `plot()` ends with a full draw on Agg after every layer) | `figures_pixel_equivalence_itemh_PRT.json` (`scripts/proofs/compare_png_dirs.py`): 95 of 95 PNG equal by pixels | PRT `climate_maps` 83.6 s to 31.8 s CPU; BRA 169 s to 78 s and IND 248 s to 114 s in the round |
| **j** | `core/memory_guard.py`: a cold audit or F2a does not start with less than 2 GB available (exit code 75, before any phase of any country) | `tests/unit/test_core_memory_guard.py` | addresses the two silent kills of the cold IND round of COMMAND 75 (`profile_76.md` D) |
| **k** | `keep_awake` is an option of `settings.yaml` (schema default false, the shipped file sets true: the behaviour of the pipeline does not change) | `tests/unit/test_core_power.py` | |

### Correction of COMMAND 79 to item a

The unattended round of 2026-10-29 compared every artifact of IND and BRA with the manifest saved before it. IND `land_eligibility` and what follows differed, from `protected`. Diagnosis
(`scripts/proofs/diagnose_clip_shortcut.py`, `clip_shortcut_diagnosis_IND.json`): of the 8,747 line features of the IND protected areas, 8,705 are **closed, non-simple** `LineString`s (the boundary
rings of protected areas). The exact intersection rewrites them: GEOS nodes the ring (1,614 become `MultiLineString`) and drops vertices (20,836 coordinates against 28,713 kept), with
Hausdorff distance 0 and yet other pixels burned by `rasterize`: 148 of 2.25 million pixels differed by up to 0.02 in the coverage that F3 reads. No simple LineString differed
(150,000 river lines and 150,000 road lines sampled, and the 38 `MultiLineString`s of `protected`, all equal). The rule is now: **only a simple LineString wholly covered skips the
intersection; `MultiLineString`, a line that touches itself, a ring and every polygon are always intersected exactly**, with no layer name in the code. The cumulative proof was made again on PRT (94 of 94,
`cumulative_equivalence_77_PRT.json`) and the whole IND layers were compared as above. BRA `audit_report` also differed in that round (probably the same cause: its `geometry_types` count); the
reference copy of the file was not kept and the deferred check of D-core-050 flags it for review.

## Not applied

| Item | Idea | Why not | Evidence |
|---|---|---|---|
| **f** | rasterize without `mapping(g)` | no gain: rasterio calls `__geo_interface__` itself | measured, no file kept (a one-line benchmark) |
| **g** (3) | keep a covered polygon as it is (a polygon fast path of the clip) | the hash of a derived raster changes in IND: `protected_fraction_all` differs (PRT and BRA equal), because the intersection rewrites the rings | `polygon_derived_equivalence_item3.json`, `polygon_fastpath_equivalence_item3_PRT.json` |
| **i** | smaller strips in the population warp | the summed population changes with the strip size in IND (400 MB and 200 MB strips give different hashes; PRT does not) | `population_strips_itemi.json` |

## Open

* BRA `land_eligibility` peaks at 3,397 MB in the cold round (target under 3 GB not met); the size of the pixel arrays of the largest grid is the cause, not one of these items.
* `reproject_to_grid` with `Resampling.sum` peaks near 2 GB even on a small window (GDAL warp buffers); not changed.
* The round that measured the times above ran before the restriction of item a. The restricted rule sends 8,707 closed lines of IND `protected` (and any multipart line) to the exact
  intersection: seconds, and `roads` and `rivers` are unchanged because their sampled lines are simple.
