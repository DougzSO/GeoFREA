"""The builder of each aligned layer of F2a, one function per layer (COMMAND 88, items 1 and 3).

Every builder takes a `LayerContext` (the inputs, the reference grid and the output directories, all picklable) and writes its raster(s). The
phase (`alignment.run_grid_alignment_phase`) runs each builder in a child process, one at a time, so a layer's memory returns to the system
before the next one starts; the builders hold no state between calls.

A builder is also the entry of the code fingerprint of its layer (`core.cache_code.CACHE_FUNCTION_ENTRIES`): only the functions a builder can
reach enter the key of its layer, so an edit of the population step does not invalidate the elevation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd
from rasterio.enums import Resampling

from geofrea.core.cache_key import FileHashMemo
from geofrea.core.clipped_cache import clipped_source
from geofrea.core.geo_utils import clip_cache_key as _clip_cache_key
from geofrea.core.geo_utils import (
    current_clip_cache,
    read_clipped_to_country,
    write_clip_cache_key,
)
from geofrea.core.raster_io import gdal_quiet
from geofrea.grid_alignment.poi import select_poi
from geofrea.grid_alignment.raster_alignment import (
    MissingSourceCrsError,
    glo30_aligned_outputs,
    land_cover_class_counts,
    mosaic_land_cover,
    reproject_to_grid,
    sum_to_grid,
)
from geofrea.grid_alignment.reference_grid import GridContext
from geofrea.grid_alignment.schemas import GridAlignmentInputs
from geofrea.grid_alignment.vector_alignment import (
    align_lakes,
    align_rivers,
    filter_road_classes,
    load_vector_bbox,
    rasterize_linear_distance,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LayerContext:
    """What a layer builder needs: the inputs of the phase, the reference grid, where the rasters go, and where the clip caches live."""

    inputs: GridAlignmentInputs
    grid: GridContext
    out_dir: Path
    interim_dir: Path
    country_code: str

    def path(self, suffix: str) -> Path:
        return self.out_dir / f"{self.country_code}_{suffix}_aligned.tif"


# The mosaic is categorical and must equal the layers made before exactly: with a 16 MB chunk 180 of 7.1 million pixels of BRA took another class
# (COMMAND 88, docs/_audit/memory_budget_88.md), so it keeps its own 1024 MB chunk and not `geospatial.warp_mem_limit_mb`.
_LAND_COVER_WARP_MEM_LIMIT_MB = 1024


def _exists(path: Path | None) -> bool:
    return bool(path and Path(path).exists())


def _read_clipped_with_cache(path: Path, country_gdf: gpd.GeoDataFrame, cache_path: Path) -> gpd.GeoDataFrame:
    """read_clipped_to_country(), backed by an on-disk cache keyed by cache_path.

    Duplicates vector_inspection.py's private helper of the same shape rather than importing it: the reuse between F1b and F2a is by the disk
    file convention (the same `cache_path`), not by code shared across the phase boundary.

    Returns:
        The clipped GeoDataFrame, from the cache if its key is current, else computed and cached for next time.
    """
    key = _clip_cache_key(path, country_gdf)
    current = current_clip_cache(cache_path, key)
    if current is not None:
        return gpd.read_file(str(current))
    # No key, or a key for a different source file or country polygon: the cached clip is stale (a cache clipped from another source,
    # e.g. IND roads from the wrong GRIP4 region, is rebuilt, never reused).
    clipped, repair_report = read_clipped_to_country(path, country_gdf)
    if repair_report.n_invalid:
        # INFO, not WARNING: the repair is documented behavior (D-F2a-020); the output schema has no slot for the report, so it is logged here.
        logger.info(
            "%s: %d/%d features were topologically invalid and repaired before clipping (expected, A-02; reasons: %s; decision D-F2a-020).",
            path,
            repair_report.n_invalid,
            repair_report.n_total,
            repair_report.invalid_reasons,
        )
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        clipped.to_file(cache_path, driver="GPKG")
        write_clip_cache_key(cache_path, key)
    except Exception as exc:  # noqa: BLE001 — caching is optional, must not fail alignment
        logger.warning("Failed to write clip cache %s: %s", cache_path, exc)
    return clipped


def _clipped_gdf(ctx: LayerContext, source_path: Path | None, layer_name: str) -> gpd.GeoDataFrame | None:
    if not _exists(source_path):
        return None
    return _read_clipped_with_cache(source_path, ctx.inputs.country_gdf, ctx.interim_dir / f"{layer_name}_clipped.gpkg")


def gwa_crs_for(key: str, path: Path, wind_layers: dict[str, Path]):
    """CRS for a GWA layer: its own, or, when the file declares none, the sibling wind-speed file's.

    The GWA API serves the Weibull A/k tiles without a CRS tag (observed 2026-10-06 for PRT, BRA and IND), but on the same grid as the wind-speed
    tile of the same height, which does declare EPSG:4326. The sibling's CRS is used only when its transform and shape are identical; otherwise
    this raises (A-09).

    Implements: M-F2a-04.
    """
    import rasterio

    with rasterio.open(path) as own:
        if own.crs is not None:
            return None
        height = key.rsplit("_", 1)[-1]
        sibling = wind_layers.get(f"wind_speed_{height}")
        if sibling is None:
            raise MissingSourceCrsError(f"{path}: no CRS and no wind-speed sibling at {height} to take it from")
        with rasterio.open(sibling) as sib:
            if sib.crs is None or sib.transform != own.transform or sib.shape != own.shape:
                raise MissingSourceCrsError(f"{path}: no CRS and the {height} wind-speed sibling is not on the same grid")
            return sib.crs


def _source(ctx: LayerContext, path: Path) -> Path:
    """The raster to warp for `path`: its pre-clip to the country's window in `cache/clipped`, or the source itself when a clip saves little."""
    return clipped_source(path, ctx.grid, memo=FileHashMemo(ctx.interim_dir / "input_sha256.json"))


def build_glo30(
    ctx: LayerContext, checkpoint_dir: Path | None = None, checkpoint_key: str | None = None
) -> dict[str, Path | None]:
    """One pass over the GLO-30 tiles writes the elevation, the slope and the slope bins (COMMAND 75).

    With a checkpoint directory and the key of the layer, the groups of rows already done by an interrupted run are taken from it (COMMAND 98).
    """
    with gdal_quiet():
        return glo30_aligned_outputs(
            list(ctx.inputs.slope_dem_tiles),
            ctx.grid,
            elevation_out=ctx.path("elevation"),
            slope_out=ctx.path("slope"),
            counts_out=ctx.path("slope_counts"),
            checkpoint_dir=checkpoint_dir,
            checkpoint_key=checkpoint_key,
        )


def build_solar(ctx: LayerContext) -> Path:
    with gdal_quiet():
        return reproject_to_grid(
            _source(ctx, ctx.inputs.solar_path), ctx.path("solar"), ctx.grid, warp_mem_limit_mb=ctx.inputs.warp_mem_limit_mb
        )


def build_wind(ctx: LayerContext, key: str) -> Path:
    """One GWA product at one height ("<product>_<height>m"), on its own (M-F2a-04, G-2); nothing is combined across heights."""
    source = ctx.inputs.wind_layers[key]
    with gdal_quiet():
        return reproject_to_grid(
            _source(ctx, source),
            ctx.path(f"wind_{key}"),
            ctx.grid,
            src_crs=gwa_crs_for(key, source, ctx.inputs.wind_layers),
            warp_mem_limit_mb=ctx.inputs.warp_mem_limit_mb,
        )


def build_land_cover(
    ctx: LayerContext, checkpoint_dir: Path | None = None, checkpoint_key: str | None = None
) -> Path | None:
    return mosaic_land_cover(
        ctx.inputs.land_cover_tiles,
        ctx.path("land_cover"),
        ctx.grid,
        ctx.inputs.country_gdf,
        warp_mem_limit_mb=_LAND_COVER_WARP_MEM_LIMIT_MB,
        checkpoint_dir=checkpoint_dir,
        checkpoint_key=checkpoint_key,
    )


def build_land_cover_counts(
    ctx: LayerContext, checkpoint_dir: Path | None = None, checkpoint_key: str | None = None
) -> Path | None:
    return land_cover_class_counts(
        ctx.inputs.land_cover_count_tiles or ctx.inputs.land_cover_tiles,
        ctx.path("land_cover_counts"),
        ctx.grid,
        ctx.inputs.country_gdf,
        checkpoint_dir=checkpoint_dir,
        checkpoint_key=checkpoint_key,
    )


def build_population(ctx: LayerContext) -> Path:
    """Counts per pixel are SUMMED onto the coarser grid: bilinear took about one 100 m sample per 1.1 km pixel and left 1/144 of the population (D-F2a-014).

    The sum is the exact area-weighted one (`sum_to_grid`, D-F2a-026): GDAL's `Resampling.sum` gave another value, by up to 4 people in a pixel, for a pixel
    whose source edge fell near the middle of a source pixel, according to its window.
    """
    with gdal_quiet():
        return sum_to_grid(_source(ctx, ctx.inputs.population_path), ctx.path("population"), ctx.grid)


def build_settlements(ctx: LayerContext) -> Path:
    """The GHS-SMOD class of each pixel by nearest neighbour (Group 6, COMMAND 97): the 1 km Mollweide cell that contains the centre of the pixel.

    The classes are categorical (10 to 30), so no value is mixed; a pixel whose source cell has no value is 255 (the layer then makes it invalid in F3, never free).
    The warp runs in the child process of the layer with `warp_mem_limit` of the settings, as the other warped layers.
    """
    with gdal_quiet():
        return reproject_to_grid(
            _source(ctx, ctx.inputs.settlements_path),
            ctx.path("settlements"),
            ctx.grid,
            resampling=Resampling.nearest,
            nodata_out=255,
            dtype_out="uint8",
            warp_mem_limit_mb=ctx.inputs.warp_mem_limit_mb,
        )


def build_grid_distance(ctx: LayerContext) -> Path | None:
    return rasterize_linear_distance(
        load_vector_bbox(ctx.inputs.grid_source, ctx.inputs.country_gdf, "grid"),
        ctx.path("grid"),
        ctx.inputs.country_gdf,
        ctx.grid,
        "grid",
        ctx.inputs.distance_cap_km,
    )


def _poi_points(ctx: LayerContext, threshold_kv: float, counts_path: Path) -> object | None:
    """The eligible substations at `threshold_kv` of the country (see `select_poi`); writes the counts beside the raster."""
    inputs = ctx.inputs
    grid_gdf = load_vector_bbox(inputs.grid_source, inputs.country_gdf, "grid")
    if grid_gdf is None:
        return None
    if inputs.poi_substation_source is not None:
        # substations as nodes, ways and relations (OQ-067): they replace the points of the raw grid extract, the lines stay
        substations = load_vector_bbox(inputs.poi_substation_source, inputs.country_gdf, "substations")
        lines = grid_gdf[grid_gdf["power"] != "substation"]
        grid_gdf = (
            lines
            if substations is None
            else gpd.GeoDataFrame(pd.concat([lines, substations], ignore_index=True), geometry="geometry", crs=lines.crs)
        )
    points, counts = select_poi(grid_gdf, threshold_kv, inputs.poi_line_tolerance_m)
    counts_path.write_text(json.dumps(counts.as_dict(), indent=2), encoding="utf-8")
    logger.info("    [%s] substations at %s kV: %s", counts_path.stem, threshold_kv, counts.as_dict())
    return points


def build_poi(ctx: LayerContext, name: str, threshold_kv: float, counts_path: Path) -> Path | None:
    """The distance to the nearest eligible substation (`name` is "poi" or "poi_sensitivity", the latter at another voltage threshold)."""
    points = _poi_points(ctx, threshold_kv, counts_path)
    if points is None:
        return None
    return rasterize_linear_distance(
        points if len(points) else None,
        ctx.path(name),
        ctx.inputs.country_gdf,
        ctx.grid,
        name,
        ctx.inputs.distance_cap_km,
    )


def build_roads(ctx: LayerContext) -> Path | None:
    inputs = ctx.inputs
    return rasterize_linear_distance(
        filter_road_classes(_clipped_gdf(ctx, inputs.roads_source, "roads"), inputs.road_classes),
        ctx.path("roads"),
        inputs.country_gdf,
        ctx.grid,
        "roads",
        inputs.distance_cap_km,
    )


def build_lakes(ctx: LayerContext) -> Path | None:
    return align_lakes(_clipped_gdf(ctx, ctx.inputs.lakes_path, "lakes"), ctx.path("lakes"), ctx.grid)


def build_rivers(ctx: LayerContext) -> Path | None:
    return align_rivers(
        _clipped_gdf(ctx, ctx.inputs.rivers_path, "rivers"), ctx.path("rivers"), ctx.grid, ctx.inputs.distance_cap_km
    )
