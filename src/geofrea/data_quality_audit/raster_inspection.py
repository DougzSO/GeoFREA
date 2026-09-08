"""Raster/vector/tabular inspection helpers for the data_quality_audit phase.

Ported near-verbatim from geoworld_framework's
src/processors/data_auditor.py (module-level functions, L79-837 — see
docs/architecture/data_quality_audit.md for the formulas and their exact
legacy line numbers). Each function still returns a plain dict, matching
the legacy signatures; audit.py is the boundary that validates the
assembled dict against this phase's Pydantic schemas (AuditResult and
friends) — see DECISIONS.md 2026-08-20 - orchestrator + data_quality_audit
phase for why the schema boundary is drawn there rather than in each
helper.

Not ported: legacy's `tqdm` progress bar is optional there and stays
optional here (falls back to a no-op iterator wrapper).
"""

from __future__ import annotations

import logging
import math
import warnings
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.errors import WindowError
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds as window_from_bounds
from shapely.geometry import box, mapping

from geofrea.core.constants import ESA_CLASS_NAMES, MASK_FILL

try:
    from tqdm import tqdm
except ImportError:

    def tqdm(iterable, **kwargs):  # type: ignore[misc]
        return iterable


logger = logging.getLogger("geofrea.data_quality_audit.raster_inspection")

_CHUNK_ROWS = 4_000

# Real incident, 2026-09-08 (see docs/DECISIONS.md same date, "wire das 5
# camadas restantes a partir do banco local, Fase 2 - roads", RAM finding):
# running the real end-to-end pipeline for BRA, _mask_raster_by_polygon()'s
# single float32 read of the country-bbox window for `population`
# (window (46813, 47036) px, WorldPop ~93m resolution over Brazil) drove
# free system RAM from a healthy baseline down to 0.14 GB of 15.84 GB —
# a near-OOM, not a crash, because numpy's allocation succeeded (the OS
# paged rather than raising) instead of tripping the existing
# `except MemoryError: pass` fallback to _stats_chunked() below.
# ~46,813 * 47,036 * 4 bytes (float32) ≈ 8.8 GB for that one array alone,
# before the boolean poly_mask and rasterio's own internal read buffer.
# This is a pre-existing risk in the windowed-read path, only exposed now
# that `population` got a real path for a country BRA's size for the
# first time (Fase 1, same DECISIONS.md date) — nothing about `roads`
# itself. Fixed here by ESTIMATING the allocation from the window's own
# pixel count before ever calling src.read(), and raising MemoryError
# proactively when it would exceed this budget — reusing inspect_raster()'s
# existing MemoryError -> _stats_chunked() fallback wiring rather than
# adding a second, parallel fallback path.
_WINDOWED_READ_MAX_BYTES = 1_500_000_000  # ~1.5 GB, conservative


@contextmanager
def timer(label: str, timings: dict[str, float]) -> Generator[None, None, None]:
    """Context manager that measures execution time and stores it in timings."""
    import time

    t0 = time.perf_counter()
    logger.info("  [%s] starting...", label)
    try:
        yield
    finally:
        elapsed = time.perf_counter() - t0
        timings[label] = round(elapsed, 2)
        logger.info("  [%s] completed in %.1fs", label, elapsed)


def _nodata_mask(data: np.ndarray, nodata) -> np.ndarray:
    """Return a boolean mask where True indicates a valid pixel.

    Safely handles nodata=None, nan, -9999, and float32 overflow.
    """
    finite = np.isfinite(data)
    if nodata is None:
        return finite

    try:
        nodata_as_float = float(nodata)
    except (TypeError, ValueError):
        return finite

    if not math.isfinite(nodata_as_float):
        return finite

    with np.errstate(over="ignore", invalid="ignore"):
        nodata_typed = data.dtype.type(nodata_as_float)

    if not np.isfinite(nodata_typed):
        return finite

    return finite & (data != nodata_typed)


def row_area_km2(shape: tuple[int, int], transform: rasterio.Affine) -> np.ndarray:
    """Compute geodetic area per pixel row in km², corrected by latitude.

    Returns a 1D array (height,) rather than a full 2D grid to avoid
    memory issues with large tiles (see
    docs/architecture/data_quality_audit.md sec b, formula 1, for the
    exact WGS84 meridian/parallel-arc approximation used).
    """
    height, _ = shape
    res_x = abs(transform.a)
    res_y = abs(transform.e)

    rows = np.arange(height)
    y_top = transform.f + rows * transform.e
    y_bottom = transform.f + (rows + 1) * transform.e
    lat_mid = (y_top + y_bottom) / 2.0
    lat_rad = np.radians(lat_mid)

    lat_km = (
        111132.92
        - 559.82 * np.cos(2 * lat_rad)
        + 1.175 * np.cos(4 * lat_rad)
        - 0.0023 * np.cos(6 * lat_rad)
    ) / 1000.0
    lon_km = (
        111412.84 * np.cos(lat_rad)
        - 93.50 * np.cos(3 * lat_rad)
        + 0.118 * np.cos(5 * lat_rad)
    ) / 1000.0

    km_x = res_x * lon_km
    km_y = res_y * lat_km
    return (km_x * km_y).astype(np.float64)


def _country_window(
    bounds: tuple[float, float, float, float],
    transform: rasterio.Affine,
    width: int,
    height: int,
) -> rasterio.windows.Window:
    """Compute the raster window covering a country's bbox, clipped to the raster's own extent.

    Single source of truth for this computation, added 2026-09-08 (see
    docs/DECISIONS.md same date) after _mask_raster_by_polygon() and
    _stats_chunked() were found to have silently diverged: each
    computed this window independently (or, for _stats_chunked(),
    didn't compute it at all — it used to chunk over the FULL raster
    extent instead), which is exactly how their total_px denominators
    drifted apart undetected. Extracting the math here does NOT decide
    what "no overlap" means for a caller — see the "Raises" section and
    each caller's own docstring for why they deliberately differ on
    that.

    Args:
        bounds: Country geometry bounds (minx, miny, maxx, maxy),
            already reprojected into the raster's own CRS.
        transform: The raster's affine transform (src.transform).
        width: Raster width in pixels (src.width).
        height: Raster height in pixels (src.height).

    Returns:
        The bbox window, intersected with (0, 0, width, height).

    Raises:
        rasterio.errors.WindowError: If the country bbox does not
            overlap the raster's own extent at all. Deliberately NOT
            caught here — this function only computes the window, it
            does not decide whether a non-overlapping pairing is an
            error or a legitimate empty result. That policy differs by
            caller (see _mask_raster_by_polygon() and _stats_chunked()).
    """
    window = window_from_bounds(bounds[0], bounds[1], bounds[2], bounds[3], transform=transform)
    return window.intersection(rasterio.windows.Window(0, 0, width, height))


def _mask_raster_by_polygon(
    src: rasterio.DatasetReader,
    country_gdf: gpd.GeoDataFrame,
) -> tuple[np.ndarray | None, rasterio.Affine | None]:
    """Clip a raster to a country polygon using a windowed read strategy.

    Raises:
        rasterio.errors.WindowError: If the country bbox does not
            overlap the raster at all — propagated, not caught here.
            This is this function's PRE-EXISTING policy (unchanged by
            the 2026-09-08 _country_window() extraction, only made
            explicit by it): a country/raster pairing with zero overlap
            surfaces as inspect_raster()'s own result["error"] (via its
            broad except Exception), the same way a corrupt file would
            — treated as worth flagging, not silently swallowed.
            _stats_chunked() deliberately makes the OPPOSITE choice for
            the identical condition (see that function's docstring) —
            not an oversight that the two agree here, a considered
            per-caller policy documented explicitly this same session.
        MemoryError: If the window's pixel count alone would allocate
            more than _WINDOWED_READ_MAX_BYTES as float32 — estimated
            BEFORE reading, not caught after the fact (see that
            constant's docstring for the real incident this guards
            against: relying on numpy/rasterio's own allocation to
            raise MemoryError was not reliable enough on Windows, which
            can page instead of raising). Caller falls back to
            _stats_chunked().
    """
    geom_in_src_crs = country_gdf.to_crs(src.crs)
    bounds = geom_in_src_crs.total_bounds

    window = _country_window(bounds, src.transform, src.width, src.height)

    estimated_bytes = round(window.width) * round(window.height) * np.dtype(np.float32).itemsize
    if estimated_bytes > _WINDOWED_READ_MAX_BYTES:
        raise MemoryError(
            f"Windowed read would allocate ~{estimated_bytes / 1e9:.2f} GB "
            f"(window {round(window.height)}x{round(window.width)} px as float32), "
            f"over the {_WINDOWED_READ_MAX_BYTES / 1e9:.1f} GB budget — "
            "falling back to a chunked read instead."
        )

    win_transform = src.window_transform(window)
    data = src.read(1, window=window).astype(np.float32)

    shapes = [mapping(geom) for geom in geom_in_src_crs.geometry]
    poly_mask = geometry_mask(shapes, out_shape=data.shape, transform=win_transform, invert=True)
    data[~poly_mask] = MASK_FILL

    return data, win_transform


def _stats_chunked(
    src: rasterio.DatasetReader,
    country_gdf: gpd.GeoDataFrame,
) -> tuple[dict[str, Any] | None, rasterio.Affine | None]:
    """Compute raster statistics by reading in chunks of _CHUNK_ROWS rows.

    Fallback for rasters too large to mask in one windowed read (e.g. a
    ~3.4 GB WorldPop 100m tile for Brazil).

    total_px scoping fixed 2026-09-08 (see docs/DECISIONS.md same date):
    this function used to chunk over the FULL raster extent
    (src.height/src.width) regardless of country_gdf, while
    _mask_raster_by_polygon() (the windowed-read strategy this falls
    back FROM) scopes to the country's own bbox window — live-verified
    to silently diverge (BRA population: 45.8% valid via the windowed
    path vs. 39.7% via this one, exactly explained by the ~15% larger
    full-raster pixel count used as this function's total_px
    denominator). min/max/mean/area_km2 were never affected — those
    come from valid_px directly, not total_px — only valid_pct
    (computed by the caller, inspect_raster(), as valid_px/total_px)
    was inconsistent depending on which strategy actually ran. Now
    chunks over the same country-bbox window _mask_raster_by_polygon()
    would have used (both now go through the shared _country_window()),
    so total_px means the same thing regardless of which strategy
    handled a given raster.

    WindowError policy DELIBERATELY differs from _mask_raster_by_polygon()
    for the identical "no overlap at all" condition — not an oversight,
    a considered choice made explicit 2026-09-08 when the two functions'
    window computation was unified into _country_window(): this
    function catches it and returns zero stats, because that has always
    been its own pre-existing contract (see
    test_stats_chunked_returns_zero_stats_when_polygon_does_not_overlap,
    which predates this session — before 2026-09-08 this function never
    computed a window at all, it just iterated real pixel data via
    geometry_mask(), which naturally produces zero valid pixels for a
    non-overlapping polygon without ever raising). Preserving that
    behavior through the shared helper, not changing it, is the point.
    """
    try:
        geom_in_src_crs = country_gdf.to_crs(src.crs)
        shapes = [mapping(geom) for geom in geom_in_src_crs.geometry]
        transform = src.transform
        nodata = src.nodata

        bounds = geom_in_src_crs.total_bounds
        try:
            country_window = _country_window(bounds, transform, src.width, src.height)
        except WindowError:
            return {
                "min": None,
                "max": None,
                "mean": None,
                "valid_px": 0,
                "total_px": 0,
                "area_km2": 0.0,
            }, transform

        row_off = round(country_window.row_off)
        col_off = round(country_window.col_off)
        win_height = round(country_window.height)
        win_width = round(country_window.width)

        g_min = np.inf
        g_max = -np.inf
        g_sum = 0.0
        g_valid_px = 0
        g_total_px = 0
        g_area_km2 = 0.0

        for chunk_start in range(0, win_height, _CHUNK_ROWS):
            chunk_end = min(chunk_start + _CHUNK_ROWS, win_height)
            chunk_h = chunk_end - chunk_start

            window = rasterio.windows.Window(col_off, row_off + chunk_start, win_width, chunk_h)
            win_tf = src.window_transform(window)
            block = src.read(1, window=window).astype(np.float32)

            poly_mask = geometry_mask(shapes, out_shape=block.shape, transform=win_tf, invert=True)

            valid_mask = poly_mask & np.isfinite(block)
            if nodata is not None:
                try:
                    nd = np.float32(nodata)
                    if np.isfinite(nd):
                        valid_mask &= block != nd
                except (TypeError, ValueError):
                    pass
            valid_mask &= block != np.float32(MASK_FILL)

            vals = block[valid_mask].astype(np.float64)
            n = vals.size

            if n > 0:
                g_min = min(g_min, float(vals.min()))
                g_max = max(g_max, float(vals.max()))
                g_sum += float(vals.sum())

            row_areas = row_area_km2((chunk_h, win_width), win_tf)
            valid_per_row = valid_mask.sum(axis=1)
            g_area_km2 += float((row_areas * valid_per_row).sum())

            g_valid_px += n
            g_total_px += block.size

        if g_valid_px == 0:
            return {
                "min": None,
                "max": None,
                "mean": None,
                "valid_px": 0,
                "total_px": g_total_px,
                "area_km2": 0.0,
            }, transform

        return {
            "min": round(g_min, 4),
            "max": round(g_max, 4),
            "mean": round(g_sum / g_valid_px, 4),
            "valid_px": g_valid_px,
            "total_px": g_total_px,
            "area_km2": round(g_area_km2, 1),
        }, transform

    except Exception as exc:  # noqa: BLE001 — fallback path itself must not crash the audit
        logger.debug("_stats_chunked failed: %s", exc)
        return None, None


def inspect_raster(path: Path, country_gdf: gpd.GeoDataFrame | None = None) -> dict[str, Any]:
    """Read metadata and statistics from a single raster file.

    Adaptive memory strategy: try a windowed polygon-masked read first;
    on MemoryError, fall back to a chunked read. Since 2026-09-08 (see
    _WINDOWED_READ_MAX_BYTES's docstring — a real near-OOM incident),
    that MemoryError can come from _mask_raster_by_polygon() estimating
    the window's allocation size upfront and refusing it proactively,
    not only from an actual failed allocation.

    Args:
        path: Path to the raster file.
        country_gdf: Country polygon for masking (uses the full file if None).

    Returns:
        Dict matching geofrea.data_quality_audit.schemas.RasterInspection's fields.
    """
    result: dict[str, Any] = {
        "name": path.name,
        "size_mb": round(path.stat().st_size / (1024**2), 2),
        "crs": None,
        "resolution": None,
        "global_shape": None,
        "analysis_shape": None,
        "masked_by": "full file",
        "nodata": None,
        "min": None,
        "max": None,
        "mean": None,
        "valid_pct": None,
        "area_km2": None,
        "error": None,
    }

    try:
        with rasterio.open(str(path)) as src:
            result["crs"] = str(src.crs)
            result["resolution"] = round(abs(src.res[0]), 8)
            result["global_shape"] = (src.height, src.width)
            result["nodata"] = src.nodata

            if country_gdf is not None:
                data, transform = None, None
                try:
                    data, transform = _mask_raster_by_polygon(src, country_gdf)
                except MemoryError:
                    pass

                if data is None:
                    logger.info(
                        "  [%s] large file — using chunked read (%d rows/chunk)",
                        path.stem,
                        _CHUNK_ROWS,
                    )
                    stats, transform = _stats_chunked(src, country_gdf)
                    if stats is None:
                        result["error"] = (
                            "Failed to process raster "
                            "(both windowed and chunked strategies failed)"
                        )
                        return result

                    result["masked_by"] = "country polygon (chunked)"
                    result["analysis_shape"] = (src.height, src.width)
                    result["min"] = stats["min"]
                    result["max"] = stats["max"]
                    result["mean"] = stats["mean"]
                    result["valid_pct"] = (
                        round(100.0 * stats["valid_px"] / stats["total_px"], 1)
                        if stats["total_px"] > 0
                        else 0.0
                    )
                    result["area_km2"] = stats["area_km2"]
                    return result

                result["masked_by"] = "country polygon (windowed)"

            else:
                data = src.read(1).astype(np.float32)
                transform = src.transform

            result["analysis_shape"] = data.shape

            valid_mask = _nodata_mask(data, MASK_FILL)
            if src.nodata is not None and src.nodata != MASK_FILL:
                valid_mask &= _nodata_mask(data, src.nodata)

            valid_data = data[valid_mask]
            total_px = data.size
            valid_px = valid_data.size

            if valid_px > 0:
                result["min"] = round(float(valid_data.min()), 4)
                result["max"] = round(float(valid_data.max()), 4)
                result["mean"] = round(float(valid_data.mean()), 4)
                result["valid_pct"] = round(100.0 * valid_px / total_px, 1)

                row_areas = row_area_km2(data.shape, transform)
                valid_per_row = valid_mask.sum(axis=1)
                result["area_km2"] = round(float((row_areas * valid_per_row).sum()), 1)
            else:
                result["valid_pct"] = 0.0
                result["area_km2"] = 0.0

    except Exception as exc:  # noqa: BLE001 — one bad raster must not abort the whole audit
        result["error"] = str(exc)
        logger.warning("Error inspecting %s: %s", path.name, exc)

    return result


def inspect_land_cover_tiles(
    tile_paths: list[Path], country_gdf: gpd.GeoDataFrame | None = None
) -> dict[str, Any]:
    """Aggregate ESA WorldCover statistics across multiple tiles.

    Each tile is masked by the real country polygon; tiles with no
    overlap are skipped automatically.

    Args:
        tile_paths: ESA WorldCover tile paths.
        country_gdf: Country polygon for masking (required for accuracy).

    Returns:
        Dict matching geofrea.data_quality_audit.schemas.LandCoverInspection's fields.
    """
    if country_gdf is None:
        logger.warning("[land_cover] country_gdf not provided — cannot mask tiles.")
        return {"error": "country_gdf required for tile analysis"}

    class_areas: dict[int, float] = {}
    total_area = 0.0
    tiles_used = 0
    tiles_skip = 0
    crs_set: set[str] = set()
    res_set: set[float] = set()
    errors: list[str] = []

    country_geom = country_gdf.geometry.union_all()
    country_bounds = country_gdf.total_bounds

    pbar = tqdm(tile_paths, desc="   [land_cover] Analyzing", unit="tile", leave=False)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)

        for tile in pbar:
            if hasattr(pbar, "set_postfix"):
                pbar.set_postfix({"status": tile.name[-20:]})
            try:
                with rasterio.open(str(tile)) as src:
                    t_bounds = src.bounds

                    if (
                        t_bounds[2] < country_bounds[0]
                        or t_bounds[0] > country_bounds[2]
                        or t_bounds[3] < country_bounds[1]
                        or t_bounds[1] > country_bounds[3]
                    ):
                        tiles_skip += 1
                        continue

                    tile_box_geom = box(*t_bounds)
                    intersected_geom = country_geom.intersection(tile_box_geom)

                    if intersected_geom.is_empty:
                        tiles_skip += 1
                        continue

                    crs_set.add(str(src.crs))
                    res_set.add(round(abs(src.res[0]), 8))
                    tiles_used += 1

                    row_areas_global = row_area_km2((src.height, src.width), src.transform)

                    step = 8192
                    for r in range(0, src.height, step):
                        for c in range(0, src.width, step):
                            window = rasterio.windows.Window(
                                c, r, min(step, src.width - c), min(step, src.height - r)
                            )

                            w_bounds = src.window_bounds(window)
                            if not box(*w_bounds).intersects(intersected_geom):
                                continue

                            data_block = src.read(1, window=window)
                            if not np.any(data_block > 0):
                                continue

                            win_transform = src.window_transform(window)
                            block_mask = geometry_mask(
                                [intersected_geom],
                                out_shape=data_block.shape,
                                transform=win_transform,
                                invert=True,
                            )

                            valid_mask = (data_block > 0) & block_mask
                            if not np.any(valid_mask):
                                continue

                            row_areas_win = row_areas_global[
                                window.row_off : window.row_off + window.height
                            ]
                            unique_classes = np.unique(data_block[valid_mask])

                            for cls in unique_classes:
                                cls_mask = (data_block == cls) & block_mask
                                cls_per_row = cls_mask.sum(axis=1)
                                area = float((row_areas_win * cls_per_row).sum())
                                cls_int = int(cls)
                                class_areas[cls_int] = class_areas.get(cls_int, 0.0) + area
                                total_area += area

                    del row_areas_global

            except Exception as exc:  # noqa: BLE001 — one bad tile must not abort the whole scan
                errors.append(f"{tile.name}: {exc}")

    if tiles_used == 0:
        logger.warning("[land_cover] No tile overlapped with the country polygon.")

    class_stats: dict[int, dict] = {}
    for cls, area in sorted(class_areas.items()):
        pct = round(100.0 * area / total_area, 2) if total_area > 0 else 0.0
        class_stats[cls] = {
            "name": ESA_CLASS_NAMES.get(cls, f"Class {cls}"),
            "area_km2": round(area, 1),
            "pct": pct,
        }

    return {
        "n_tiles": len(tile_paths),
        "tiles_used": tiles_used,
        "tiles_skipped": tiles_skip,
        "crs_set": list(crs_set),
        "res_set": list(res_set),
        "class_stats": class_stats,
        "total_area_km2": round(total_area, 1),
        "errors": errors,
    }


def inspect_power_plants(plants_df: pd.DataFrame | None) -> dict[str, Any]:
    """Aggregate statistics from existing power-generation plants.

    Args:
        plants_df: DataFrame with power plant records.

    Returns:
        Dict matching geofrea.data_quality_audit.schemas.PowerPlantsInspection's fields.
    """
    if plants_df is None or plants_df.empty:
        return {"error": "Data not available", "total_plants": 0}

    result: dict[str, Any] = {
        "total_plants": len(plants_df),
        "total_capacity_mw": 0.0,
        "by_fuel": {},
        "error": None,
    }
    try:
        df = plants_df.copy()
        df.columns = [c.strip().lower() for c in df.columns]

        cap_col = next((c for c in ["capacity_mw", "capacity_in_mw"] if c in df.columns), None)
        if cap_col:
            result["total_capacity_mw"] = round(
                float(pd.to_numeric(df[cap_col], errors="coerce").sum()), 1
            )

        fuel_col = next(
            (c for c in ["primary_fuel", "fuel1", "fuel"] if c in df.columns), None
        )
        if fuel_col and cap_col:
            by_fuel = (
                df.groupby(fuel_col)[cap_col]
                .apply(lambda x: pd.to_numeric(x, errors="coerce").sum())
                .sort_values(ascending=False)
            )
            result["by_fuel"] = {
                str(f): round(float(c), 1) for f, c in by_fuel.items() if float(c or 0) > 0
            }
    except Exception as exc:  # noqa: BLE001 — malformed plant records must not abort the audit
        result["error"] = str(exc)

    return result


def diagnose_consistency(
    raster_meta: dict[str, dict], expected_resolutions: dict[str, float], res_tolerance: float
) -> list[str]:
    """Check for divergent CRS and unexpected resolutions across layers.

    Args:
        raster_meta: Layer name -> inspect_raster() result.
        expected_resolutions: Expected resolution in degrees per layer.
        res_tolerance: Fractional tolerance for resolution comparison.

    Returns:
        Alert strings describing consistency issues found.
    """
    alerts = []

    crs_set = {
        m["crs"] for m in raster_meta.values() if m.get("crs") and not m.get("error")
    }
    if len(crs_set) > 1:
        alerts.append("DIVERGENT CRS across layers — pipeline will reproject to EPSG:4326.")

    for layer, meta in raster_meta.items():
        if meta.get("error") or not meta.get("resolution"):
            continue
        expected = expected_resolutions.get(layer)
        if not expected:
            continue
        ratio = meta["resolution"] / expected
        if ratio < (1 - res_tolerance) or ratio > (1 + res_tolerance):
            alerts.append(
                f"UNEXPECTED RESOLUTION [{layer}]: {meta['resolution']:.6f}° "
                f"(expected ~{expected:.6f}°, ratio={ratio:.1f}x)"
            )

    return alerts
