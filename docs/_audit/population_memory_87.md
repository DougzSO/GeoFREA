# Memory of the population warp of BRA (COMMAND 87)

The cold F2a of BRA was stopped twice by the memory guard of `scripts/run_unattended.ps1` (available memory 378 MB and 87 MB, limit 400 MB) in the step `population`, on a 6 GB machine
with the editor and the assistant open. The step is `reproject_to_grid(..., Resampling.sum)` of `bra_pop_2020.tif` (46,814 x 54,172 float32, nodata -99999, one-row blocks)
in strips of at most 400 MB of source window.

## Measurements (read-only source, output in a scratch directory; peak RSS of the process)

| Case | Peak RSS |
|---|---|
| strip of a 362 to 373 MB window, code of 2026-11-02 | 2.0 to 3.3 GB (the guard stops the run) |
| strip of a 56 MB window | 0.4 GB (northern strips) to 2.7 GB (strips with data) |
| one strip of 49 MB, default warp memory | 1,746 MB |
| same strip, `warp_mem_limit=32 / 8 / 2` MB | 1,130 / 571 / 356 MB, output sha1 identical |
| strips of a 362 to 373 MB window, `warp_mem_limit=16` and the NaN cleaning in place | 1.38 to 1.71 GB |

The memory is GDAL's, not the window's: `Resampling.sum` is the general warp kernel and its chunk buffers grow with the data of the strip, not with the block size.
The step also made two more copies of a window that holds a literal NaN (`np.where(...).astype(...)`).

## Change (`src/geofrea/grid_alignment/raster_alignment.py`)

1. `reproject(..., warp_mem_limit=_WARP_MEM_LIMIT_MB)` with 16 MB.
2. The literal NaN of a window is replaced in place (`block[nan_mask] = src_nodata`).
3. The window stays at 400 MB. A 100 MB or 20 MB window gives the same raster with **one pixel in 588,750 differing by 3e-8**, which is not equal, so it was not adopted.

## Proof of equivalence (real band of the BRA population, 150 destination rows from row 2000, `Resampling.sum`)

Old code (`git show HEAD:`) against the new code with the 400 MB window: sha1 of the pixels equal, 0 pixels differ, sums equal (-2,681,155,584 with the nodata
excluded by value). Test: `tests/unit/test_grid_alignment_raster_alignment.py::test_the_warp_memory_limit_and_the_in_place_nan_cleaning_do_not_change_a_value`.

## Consequence

`cache_code("aligned_layers")` fingerprints the normalised source of `grid_alignment`, so every aligned layer made before this change is stale. Adoption
(`scripts/adopt_aligned_cache_keys.py`) is not usable: it needs every layer of the country current under one earlier revision, and roads, rivers, grid and poi of BRA were not yet made.
The BRA F2a restarts from the first layer.
