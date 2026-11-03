"""The code behind each internal cache (COMMAND 61, A-02).

A cache outside the manifest (a clip, an aligned layer, the shares of F3, a checkpoint of the ERA5 reduction) holds a result that a piece of code
computed. A key made of the inputs and the configuration only reads the result of an earlier algorithm as current (COMMAND 58: the share caches of
F3 hid the E1 fix). Every cache key therefore holds the code fingerprint of the modules that compute what it stores: the normalised source of
`CACHE_CODE_ROOTS[name]` and of everything those modules import, transitively (`code_fingerprint.closure_fingerprint`). A calculation line changes
it, a comment, a docstring or a reformat does not.

`CACHE_CODE_ROOTS` is the inventory of the caches that hold a computed result; `docs/phases/core/resume_integrity_58.md` lists them with the other stores.
"""

from __future__ import annotations

import hashlib
from functools import cache
from pathlib import Path

from geofrea.core.code_fingerprint import SRC_ROOT, cached_closure_fingerprint, closure_fingerprint
from geofrea.core.function_fingerprint import function_fingerprint

# cache -> modules (or packages) whose code computes what it stores, as dotted names under `geofrea`
CACHE_CODE_ROOTS: dict[str, tuple[str, ...]] = {
    "clip": ("core.geo_utils",),
    "land_cover_tiles": ("data_quality_audit.land_cover_tiles",),
    "raster_audit": ("data_quality_audit.raster_inspection",),
    "subpixel_shares": ("land_eligibility.fractions",),
    "dem30_extremes": ("siting_layers.sanity",),
    "era5_reduction": ("data_acquisition.fetchers.era5",),
    "gwa_mask_mosaic": ("data_acquisition.fetchers.wind",),
    "gadm_mainland": ("data_acquisition.fetchers.gadm",),
    "cf_table": ("technical_potential.cf_table",),
}


# The grid every aligned layer is built on enters the fingerprint of each of them
_ALIGNED_GRID_ENTRY = "grid_alignment.reference_grid:build_reference_grid"

# cache -> the entry functions whose reachable code computes what it stores (COMMAND 88, item 3): the key of a layer holds the code of ITS builder
# and of what that builder calls, not of the whole package, so an edit of the population step leaves the elevation current
CACHE_FUNCTION_ENTRIES: dict[str, tuple[str, ...]] = {
    "aligned_layer.glo30": ("grid_alignment.layers:build_glo30", _ALIGNED_GRID_ENTRY),
    "aligned_layer.solar": ("grid_alignment.layers:build_solar", _ALIGNED_GRID_ENTRY),
    "aligned_layer.wind": ("grid_alignment.layers:build_wind", _ALIGNED_GRID_ENTRY),
    "aligned_layer.land_cover": ("grid_alignment.layers:build_land_cover", _ALIGNED_GRID_ENTRY),
    "aligned_layer.land_cover_counts": ("grid_alignment.layers:build_land_cover_counts", _ALIGNED_GRID_ENTRY),
    "aligned_layer.population": ("grid_alignment.layers:build_population", _ALIGNED_GRID_ENTRY),
    "aligned_layer.grid": ("grid_alignment.layers:build_grid_distance", _ALIGNED_GRID_ENTRY),
    "aligned_layer.poi": ("grid_alignment.layers:build_poi", _ALIGNED_GRID_ENTRY),
    "aligned_layer.roads": ("grid_alignment.layers:build_roads", _ALIGNED_GRID_ENTRY),
    "aligned_layer.lakes": ("grid_alignment.layers:build_lakes", _ALIGNED_GRID_ENTRY),
    "aligned_layer.rivers": ("grid_alignment.layers:build_rivers", _ALIGNED_GRID_ENTRY),
}


@cache
def _function_code(name: str) -> str:
    return function_fingerprint(CACHE_FUNCTION_ENTRIES[name])


def cache_code(name: str) -> str:
    """The code fingerprint of the cache `name`: part of its key.

    Raises:
        KeyError: `name` is in neither `CACHE_CODE_ROOTS` nor `CACHE_FUNCTION_ENTRIES` (a cache must declare the code that computes it).
    """
    if name in CACHE_FUNCTION_ENTRIES:
        return _function_code(name)
    return cached_closure_fingerprint(CACHE_CODE_ROOTS[name])


def aligned_layers_code(src_root: Path | None = None) -> str:
    """One fingerprint for all the aligned layers of F2a, for the equivalence proof and the adoption of earlier layers (`scripts/adopt_aligned_cache_keys.py`).

    On a tree that has the per-layer builders (`grid_alignment/layers.py`) it is the digest of the fingerprints of every `aligned_layer.*` cache; on
    an earlier tree, where the key of every layer held the code of the whole `grid_alignment` package, it is that package fingerprint.
    """
    root = Path(src_root) if src_root is not None else SRC_ROOT
    if not (root / "grid_alignment" / "layers.py").is_file():
        return closure_fingerprint(("grid_alignment",), root)
    digest = hashlib.sha256()
    for name in sorted(CACHE_FUNCTION_ENTRIES):
        digest.update(f"{name}:{function_fingerprint(CACHE_FUNCTION_ENTRIES[name], root)}\n".encode())
    return digest.hexdigest()
