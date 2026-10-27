"""Global Wind Atlas fetcher.

Verified live 2026-08-24 (see docs/_archive/2026-09/DECISIONS.md same date): a plain
unauthenticated GET against a country-scoped API endpoint returns a
302 redirect to a CDN-hosted per-country GeoTIFF. Tested successfully
for both PRT and BRA — GeoFREA's two current countries — before this
module was written (not assumed).

Endpoint pattern discovered from a third-party R package's source
(optimal2050/globalwindatlas, gwa_get_wind_speed()), not guessed, then
independently confirmed with a live request. The wind-speed endpoint
is the one used here; `capacity-factor_IEC{1,2,3}` exists at the same
`/api/gis/country/{iso3}/...` root but is NOT fetched by this module —
explicitly out of scope for this stage (see module docstring on
single-path below).

Single-path, NOT multi-file — explicit instruction for this stage,
despite capacity-factor being available at the same URL pattern:
AuditInputs.wind_paths only ever inspects the first file
(data_quality_audit/schemas.py's own docstring), so adding a second
fetched file here would be dead weight until something downstream
actually reads more than one wind file — a future scope decision, not
this one. AcquiredLayer.paths therefore stays untouched; this fetcher
returns a single Path, same as MULTI_FILE_LAYER_NAMES already implies
("wind" is not in that set).

M-F1-03 (implemented 2026-09-23, task F1-2): fetch_gwa_product() below
generalizes the same verified endpoint pattern to the other three GWA
products (combined-Weibull-A, combined-Weibull-k, air-density) at all
three hub-relevant heights (100/150/200 m) — probed live against PRT
before implementing (all 12 product/height combinations return 200
with a real GeoTIFF; see docs/phases/F1_data_acquisition.md). Kept
deliberately separate from fetch_wind() above rather than rewriting it
in terms of the new function: fetch_wind() feeds the single "wind"
registry entry that grid_alignment/siting_layers already
consume as GeoFREA's actual wind resource layer, and its existing
soft-fail contract (returns None, never raises — see
tests/unit/test_fetchers_wind.py) is relied on by every other fetcher
in phase.py's _FETCHED_LAYER_HANDLERS. fetch_gwa_product() instead
raises on failure, per M-F1-03's explicit requirement that a missing
product fail loud (A-09) rather than be registered as silently absent
— phase.py's per-layer isolation already turns a raised exception into
that one layer's own resolution_status="failed" without aborting
others, so "raise" here is the correct contract, not an oversight.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import Window

from geofrea.core import paths
from geofrea.core.cache_code import cache_code
from geofrea.core.constants import WIND_HEIGHTS_M
from geofrea.core.http_retry import get_with_retry

logger = logging.getLogger("geofrea.data_acquisition.fetchers.wind")

_DEFAULT_HEIGHT_M = 100

# Internal layer-name key -> Global Wind Atlas URL slug. M-F1-03's four
# products. "wind_speed" here is the same product fetch_wind() above
# already fetches at 100 m (for the "wind" registry entry) — this dict
# lets fetch_gwa_product() also fetch it at 150/200 m under its own
# distinct registry entries (M-F1-03 requires all three heights for
# every product, not just wind-speed).
GWA_PRODUCTS: dict[str, str] = {
    "wind_speed": "wind-speed",
    "weibull_a": "combined-Weibull-A",
    "weibull_k": "combined-Weibull-k",
    "air_density": "air-density",
}

# M-F1-03's three hub-relevant heights.
GWA_HEIGHTS_M = WIND_HEIGHTS_M  # the heights of the products, one definition in core/constants.py


class GwaProductNotFoundError(RuntimeError):
    """A GWA product/height combination could not be fetched.

    Raised when the CDN response after the redirect is not a
    successful download — the real failure mode observed live: a
    missing product/height combination still 302-redirects to a CDN
    URL, but that URL then answers with an S3-style 403 "AccessDenied"
    XML body, not a 404 on the API itself. get_with_retry() ->
    request_with_retry() already calls resp.raise_for_status() against
    that FINAL response (core/http_retry.py) — this wraps the resulting
    requests.HTTPError (or any other request failure) so phase.py's
    per-layer failure record names the product and height directly,
    per M-F1-03's "existence confirmed on the CDN response after the
    redirect, never the redirect itself."
    """

    def __init__(self, country_code: str, product: str, height_m: int, cause: Exception) -> None:
        super().__init__(
            f"GWA product {product!r} at {height_m}m does not exist for "
            f"{country_code!r}, or the request failed after retries: {cause}"
        )
        self.country_code = country_code
        self.product = product
        self.height_m = height_m


def fetch_wind(
    outputs_dir: Path, country_code: str, height_m: int = _DEFAULT_HEIGHT_M
) -> Path | None:
    """Download the Global Wind Atlas wind-speed raster for one country.

    Args:
        outputs_dir: Root outputs directory (PhaseContext.outputs_dir).
        country_code: ISO-3166-alpha-3 code.
        height_m: Turbine hub height in meters (the API also supports
            10/50/150/200 — 100 matches this stage's verified example
            and is not otherwise parameterized elsewhere in GeoFREA
            today).

    Returns:
        Path to the saved GeoTIFF, or None if the fetch failed (logged,
        not raised).
    """
    dest_dir = paths.fetched_raw("gwa", country_code)
    dest_path = dest_dir / f"{country_code}_wind_speed_{height_m}m.tif"

    if dest_path.exists():
        return dest_path

    url = f"https://globalwindatlas.info/api/gis/country/{country_code}/wind-speed/{height_m}"

    try:
        resp = get_with_retry(url, timeout=60)
    except Exception as exc:  # noqa: BLE001 — one bad fetch must not abort acquisition
        logger.warning("Failed to fetch wind speed for %s: %s", country_code, exc)
        return None

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(resp.content)
    logger.info("Wind speed raster saved: %s", dest_path)
    return dest_path


def fetch_gwa_product(outputs_dir: Path, country_code: str, product: str, height_m: int) -> Path:
    """Download one Global Wind Atlas product at one hub height for one country.

    Implements: M-F1-03.

    Generalizes fetch_wind()'s verified endpoint pattern to all four GWA
    products (see GWA_PRODUCTS) at all three hub-relevant heights (see
    GWA_HEIGHTS_M) — probed live against PRT before this was wired into
    phase.py (all 12 combinations return 200 with a real GeoTIFF; see
    docs/phases/F1_data_acquisition.md). Unlike fetch_wind(), this
    raises rather than returning None on failure: M-F1-03 requires a
    missing product to fail loud (A-09), never be registered as an
    absent layer.

    Args:
        outputs_dir: Root outputs directory (PhaseContext.outputs_dir)
            — unused internally (destination resolves via
            paths.fetched_raw(), same as fetch_wind()); kept for
            call-site symmetry with phase.py's other fetch handlers.
        country_code: ISO-3166-alpha-3 code.
        product: One of GWA_PRODUCTS' keys.
        height_m: One of GWA_HEIGHTS_M.

    Returns:
        Path to the saved GeoTIFF.

    Raises:
        KeyError: If `product` is not one of GWA_PRODUCTS' keys.
        GwaProductNotFoundError: If the CDN response after the redirect
            is not a successful download (product/height does not
            exist in the catalogue, or the request failed after
            retries).
    """
    gwa_slug = GWA_PRODUCTS[product]
    dest_dir = paths.fetched_raw("gwa", country_code)
    dest_path = dest_dir / f"{country_code}_{product}_{height_m}m.tif"

    if dest_path.exists():
        return dest_path

    url = f"https://globalwindatlas.info/api/gis/country/{country_code}/{gwa_slug}/{height_m}"

    try:
        resp = get_with_retry(url, timeout=60)
    except Exception as exc:
        raise GwaProductNotFoundError(country_code, product, height_m, exc) from exc

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(resp.content)
    logger.info("GWA %s at %sm saved: %s", product, height_m, dest_path)
    return dest_path


# ----------------------------------------------------------------------------------- coverage of the country mask (COMMAND 58, OQ-062)

GWA_COVERAGE_MIN_PCT = 99.0  # a GWA file that holds a valid value in fewer than this share of the country mask is completed
GWA_MASK_RULE_VERSION = (
    "mosaic-1"  # bumped by hand when the mosaic changes its result; the derived file records it
)
_STRIP_ROWS = 1024
_ALIGN_TOLERANCE = 1e-6  # in pixels: two GWA files are on one lattice when their origins differ by a whole number of pixels within this


def _valid(block: np.ndarray, nodata: float | None) -> np.ndarray:
    ok = np.isfinite(block)
    if nodata is not None and np.isfinite(nodata):
        ok &= block != nodata
    return ok


def _lattice_offset(
    src: rasterio.DatasetReader, x0: float, y0: float, res: float
) -> tuple[int, int] | None:
    """(column, row) of the upper-left pixel of `src` on the lattice of origin (x0, y0) and pixel size `res`, or None if it is not on that lattice."""
    if abs(abs(src.transform.a) - res) > 1e-9 or abs(abs(src.transform.e) - res) > 1e-9:
        return None
    col = (src.transform.c - x0) / res
    row = (y0 - src.transform.f) / res
    if abs(col - round(col)) > _ALIGN_TOLERANCE or abs(row - round(row)) > _ALIGN_TOLERANCE:
        return None
    return round(col), round(row)


def mask_coverage_pct(path: Path, mask: gpd.GeoDataFrame) -> float:
    """Percentage of the pixels inside `mask` (pixel touched by the polygon) that hold a valid value in the raster at `path`.

    The mask is reprojected to the raster CRS (EPSG:4326 for a GWA file with no CRS). A part of the mask outside the raster counts as no data.
    """
    with rasterio.open(path) as src:
        projected = mask.to_crs(src.crs if src.crs is not None else "EPSG:4326")
        geoms = list(projected.geometry)
        minx, miny, maxx, maxy = projected.total_bounds
        res = abs(src.transform.a)
        c0 = int(np.floor((minx - src.transform.c) / res))
        c1 = int(np.ceil((maxx - src.transform.c) / res))
        r0 = int(np.floor((src.transform.f - maxy) / res))
        r1 = int(np.ceil((src.transform.f - miny) / res))
        inside_px = valid_px = 0
        for ra in range(r0, r1, _STRIP_ROWS):
            rb = min(ra + _STRIP_ROWS, r1)
            tf = rasterio.Affine(
                src.transform.a,
                0,
                src.transform.c + c0 * src.transform.a,
                0,
                src.transform.e,
                src.transform.f + ra * src.transform.e,
            )
            inside = geometry_mask(
                geoms, out_shape=(rb - ra, c1 - c0), transform=tf, invert=True, all_touched=True
            )
            data = np.full((rb - ra, c1 - c0), np.nan, dtype="float32")
            ra2, rb2, ca2, cb2 = max(ra, 0), min(rb, src.height), max(c0, 0), min(c1, src.width)
            if ra2 < rb2 and ca2 < cb2:
                data[ra2 - ra : rb2 - ra, ca2 - c0 : cb2 - c0] = src.read(
                    1, window=Window(ca2, ra2, cb2 - ca2, rb2 - ra2)
                ).astype("float32")
            inside_px += int(inside.sum())
            valid_px += int((_valid(data, src.nodata) & inside).sum())
    return 100.0 * valid_px / inside_px if inside_px else 0.0


def _stamp_path(derived: Path) -> Path:
    return derived.with_suffix(".rule.json")


def _source_identity(path: Path) -> list:
    stat = path.stat()
    return [path.name, stat.st_size, stat.st_mtime_ns]


def _mask_identity(mask: gpd.GeoDataFrame) -> str:
    return hashlib.sha256(b"".join(g.wkb for g in mask.geometry)).hexdigest()


def _stamp(sources: Sequence[Path], mask: gpd.GeoDataFrame) -> dict:
    """What the mosaic was made from: the rule, the code that makes it (COMMAND 61), the country mask it was cut to and the source files."""
    return {
        "rule": GWA_MASK_RULE_VERSION,
        "code": cache_code("gwa_mask_mosaic"),
        "mask": _mask_identity(mask),
        "sources": [_source_identity(p) for p in sources],
    }


def _derived_is_fresh(derived: Path, sources: Sequence[Path], mask: gpd.GeoDataFrame) -> bool:
    stamp = _stamp_path(derived)
    if not derived.is_file() or not stamp.is_file():
        return False
    try:
        return json.loads(stamp.read_text(encoding="utf-8")) == _stamp(sources, mask)
    except ValueError:
        return False


def mosaic_to_mask(sources: Sequence[Path], mask: gpd.GeoDataFrame, dest: Path) -> dict:
    """Write `dest`: the first source, with its holes filled from the next sources in order, cut to `mask`.

    The sources must lie on the lattice of the first one (same pixel size, origins a whole number of pixels apart); a source that does not is
    skipped and named in the result. The output covers the bounds of the mask on that lattice; a pixel is kept when the polygon touches it, and
    every other pixel is no data. Nothing is resampled.

    Returns:
        {"used": [names that filled at least one pixel], "skipped": {name: reason}, "shape": (rows, cols)}.
    """
    with rasterio.open(sources[0]) as own:
        crs, nodata, res = own.crs, own.nodata, abs(own.transform.a)
        x0, y0 = own.transform.c, own.transform.f
        out_dtype = own.dtypes[0]
    out_nodata = nodata if nodata is not None else -9999.0
    projected = mask.to_crs(crs if crs is not None else "EPSG:4326")
    geoms = list(projected.geometry)
    minx, miny, maxx, maxy = projected.total_bounds
    c0, c1 = int(np.floor((minx - x0) / res)), int(np.ceil((maxx - x0) / res))
    r0, r1 = int(np.floor((y0 - maxy) / res)), int(np.ceil((y0 - miny) / res))
    height, width = r1 - r0, c1 - c0
    transform = rasterio.Affine(res, 0, x0 + c0 * res, 0, -res, y0 - r0 * res)
    handles = [rasterio.open(p) for p in sources]
    skipped: dict[str, str] = {}
    offsets: list[tuple[int, int] | None] = []
    used: set[str] = set()
    tmp = dest.with_suffix(".tmp.tif")
    try:
        for i, handle in enumerate(handles):
            offset = _lattice_offset(handle, x0, y0, res)
            offsets.append(offset)
            if offset is None:
                skipped[sources[i].name] = (
                    "not on the lattice of the first file (pixel size or origin)"
                )
        dest.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(
            tmp, "w", driver="GTiff", height=height, width=width, count=1, dtype=out_dtype, crs=crs, transform=transform,
            nodata=out_nodata, tiled=True, blockxsize=256, blockysize=256, compress="deflate",
        ) as dst:  # fmt: skip
            for ra in range(0, height, _STRIP_ROWS):
                rb = min(ra + _STRIP_ROWS, height)
                strip = np.full((rb - ra, width), np.nan, dtype="float32")
                for i, handle in enumerate(handles):
                    if offsets[i] is None:
                        continue
                    sc, sr = offsets[i]
                    # strip pixel (r, c) is lattice pixel (r0 + r, c0 + c); the source holds lattice pixels [sr, sr + height) x [sc, sc + width)
                    lr0, lr1 = max(r0 + ra, sr), min(r0 + rb, sr + handle.height)
                    lc0, lc1 = max(c0, sc), min(c1, sc + handle.width)
                    if lr0 >= lr1 or lc0 >= lc1:
                        continue
                    block = handle.read(
                        1, window=Window(lc0 - sc, lr0 - sr, lc1 - lc0, lr1 - lr0)
                    ).astype("float32")
                    sel = strip[lr0 - (r0 + ra) : lr1 - (r0 + ra), lc0 - c0 : lc1 - c0]
                    fill = np.isnan(sel) & _valid(block, handle.nodata)
                    if fill.any():
                        sel[fill] = block[fill]
                        used.add(sources[i].name)
                tf = rasterio.Affine(res, 0, transform.c, 0, -res, transform.f - ra * res)
                inside = geometry_mask(
                    geoms, out_shape=strip.shape, transform=tf, invert=True, all_touched=True
                )
                strip[~inside | np.isnan(strip)] = out_nodata
                dst.write(strip.astype(out_dtype), 1, window=Window(0, ra, width, rb - ra))
    finally:
        for handle in handles:
            handle.close()
    tmp.replace(dest)
    return {"used": sorted(used), "skipped": skipped, "shape": (height, width)}


def neighbours_of(country_code: str) -> list[str]:
    """The countries whose GWA files complete this country's (`gwa_neighbours` in config/countries.yaml), none when it declares none."""
    from geofrea.data_acquisition.fetchers.gadm import _load_countries_config

    declared = _load_countries_config().get(country_code, {}).get("gwa_neighbours") or []
    return [str(c).upper() for c in declared]


def complete_gwa_to_mask(
    outputs_dir: Path,
    country_code: str,
    product: str,
    height_m: int,
    own: Path | None,
    *,
    min_pct: float = GWA_COVERAGE_MIN_PCT,
) -> Path | None:
    """The GWA file of the country, completed from the files of the declared neighbours where it does not cover the country mask.

    Implements: OQ-062 (COMMAND 58). The same product at the same height of the same Global Wind Atlas (version 3, one grid) is used, so a
    mosaic has one source and one definition. The country file is kept as fetched; the completed file is derived, named
    `<ISO>_<product>_<height>m_mask.tif` beside it, and returned only when the country file holds a valid value in fewer than `min_pct` of
    the mask pixels. Without a neighbour that fills something, the country file is returned and the gap is logged.

    Args:
        own: the country file as fetched (None: nothing to complete, None is returned).
    """
    if own is None:
        return None
    from geofrea.data_acquisition.fetchers.gadm import fetch_borders

    borders = fetch_borders(outputs_dir, country_code)
    if borders is None:
        logger.warning(
            "GWA %s %sm for %s: no country mask, coverage not checked",
            product,
            height_m,
            country_code,
        )
        return own
    mask = gpd.read_file(borders)
    before = mask_coverage_pct(own, mask)
    if before >= min_pct:
        return own
    neighbours = neighbours_of(country_code)
    if not neighbours:
        logger.warning(
            "GWA %s %sm for %s covers %.1f%% of the country mask (below %.0f%%) and the country declares no `gwa_neighbours`",
            product, height_m, country_code, before, min_pct,
        )  # fmt: skip
        return own
    files = [own]
    for iso in neighbours:
        known = paths.fetched_raw("gwa", iso) / f"{iso}_{product}_{height_m}m.tif"
        try:
            files.append(
                known if known.exists() else fetch_gwa_product(outputs_dir, iso, product, height_m)
            )
        except GwaProductNotFoundError as exc:
            logger.warning(
                "GWA %s %sm of the neighbour %s not available: %s", product, height_m, iso, exc
            )
    derived = (
        paths.fetched_raw("gwa", country_code) / f"{country_code}_{product}_{height_m}m_mask.tif"
    )
    if not _derived_is_fresh(derived, files, mask):
        info = mosaic_to_mask(files, mask, derived)
        _stamp_path(derived).write_text(json.dumps(_stamp(files, mask)), encoding="utf-8")
        logger.info(
            "GWA %s %sm for %s completed from %s (skipped %s)",
            product,
            height_m,
            country_code,
            info["used"],
            info["skipped"],
        )
    after = mask_coverage_pct(derived, mask)
    logger.info(
        "GWA %s %sm for %s: mask coverage %.1f%% -> %.1f%%",
        product,
        height_m,
        country_code,
        before,
        after,
    )
    if after < min_pct:
        logger.warning(
            "GWA %s %sm for %s still covers %.1f%% of the country mask (below %.0f%%)",
            product,
            height_m,
            country_code,
            after,
            min_pct,
        )
    return derived if after > before else own
