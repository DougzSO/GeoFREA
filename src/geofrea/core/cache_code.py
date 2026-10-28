"""The code behind each internal cache (COMMAND 61, A-02).

A cache outside the manifest (a clip, an aligned layer, the shares of F3, a checkpoint of the ERA5 reduction) holds a result that a piece of code
computed. A key made of the inputs and the configuration only reads the result of an earlier algorithm as current (COMMAND 58: the share caches of
F3 hid the E1 fix). Every cache key therefore holds the code fingerprint of the modules that compute what it stores: the normalised source of
`CACHE_CODE_ROOTS[name]` and of everything those modules import, transitively (`code_fingerprint.closure_fingerprint`). A calculation line changes
it, a comment, a docstring or a reformat does not.

`CACHE_CODE_ROOTS` is the inventory of the caches that hold a computed result; `docs/phases/core/resume_integrity_58.md` lists them with the other stores.
"""

from __future__ import annotations

from geofrea.core.code_fingerprint import cached_closure_fingerprint

# cache -> modules (or packages) whose code computes what it stores, as dotted names under `geofrea`
CACHE_CODE_ROOTS: dict[str, tuple[str, ...]] = {
    "clip": ("core.geo_utils",),
    "aligned_layers": ("grid_alignment",),
    "land_cover_tiles": ("data_quality_audit.land_cover_tiles",),
    "raster_audit": ("data_quality_audit.raster_inspection",),
    "subpixel_shares": ("land_eligibility.fractions",),
    "dem30_extremes": ("siting_layers.sanity",),
    "era5_reduction": ("data_acquisition.fetchers.era5",),
    "gwa_mask_mosaic": ("data_acquisition.fetchers.wind",),
    "gadm_mainland": ("data_acquisition.fetchers.gadm",),
    "cf_table": ("technical_potential.cf_table",),
}


def cache_code(name: str) -> str:
    """The code fingerprint of the cache `name`: part of its key.

    Raises:
        KeyError: `name` is not in `CACHE_CODE_ROOTS` (a cache must declare the code that computes it).
    """
    return cached_closure_fingerprint(CACHE_CODE_ROOTS[name])
