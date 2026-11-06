"""F3 land_eligibility end to end for one country: eligibility, 0.05 degree cells, candidate tables, maps (M-F3-01 to M-F3-06).

Reads the aligned F2a rasters, the F2b physical layers and the vector sources (protected areas, lakes, rivers); writes under
`outputs/<ISO3>/land_eligibility/artifacts/`, per technology:

  - `cells_<tech>.parquet`: every 0.05 degree cell with at least one in-country pixel (areas, excluded area per constraint,
    dominant exclusion, resource and distance means weighted by eligible area, `candidate` flag);
  - `candidates_<tech>.parquet`: the cells with any eligible area, an elevation and, for wind, not above the altitude limit (M-F3-04/05);
  - `cells_0p1deg_<tech>.parquet` (default scale only): the same cells grouped 2 x 2, the area check of a 0.1 degree run (V-07);
  - `admin1_units.parquet`: the GADM level-1 units that hold cells, with their cell counts (each cell table carries `admin1_id`, D-F3-012);
  - `eligible_fraction_<tech>.tif` (pixels), `eligible_area_km2_<tech>.tif` and `dominant_exclusion_<tech>.tif` (cells).

The parameter sets are the three scenarios of `land_availability` in `config/experiments.yaml` (the central one feeds F4-F7); the engine itself is a
function of one `ParameterSet`. The minimum-area rules (pixel floor, cluster floor) need the eligible fraction of the whole grid, so a scenario that has
them is computed in two passes (`min_area.py`).
"""

from __future__ import annotations

import dataclasses
import logging
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pydantic import BaseModel, ConfigDict
from rasterio.windows import Window

from geofrea.config_models.land_availability import (
    ELEVATION_COLUMN,
    LandAvailability,
    ParameterSet,
    elevation_sensitivity_m,
    load_land_availability,
)
from geofrea.core import paths as core_paths
from geofrea.core.atomic_io import replace_durable, write_text_atomic
from geofrea.core.cache_code import cache_code
from geofrea.core.cache_key import cache_key
from geofrea.core.checkpoint import CheckpointStore, clear_checkpoint, make_key
from geofrea.core.constants import (
    CELL_ORIGIN_LAT,
    CELL_ORIGIN_LON,
    NODATA_FLOAT,
    WIND_HEIGHTS_M,
)
from geofrea.core.geo_utils import (
    clip_cache_key,
    current_clip_cache,
    read_clipped_to_country,
    write_clip_cache_key,
)
from geofrea.core.pv_zones import ZoneSource, zones_for_cells
from geofrea.core.raster_io import open_raster_stream, safe_raster_open, safe_raster_write
from geofrea.core.scale import active_scale
from geofrea.core.tables import write_table
from geofrea.grid_alignment.schemas import GridAlignmentResult
from geofrea.land_eligibility.admin1 import assign_admin1, read_units
from geofrea.land_eligibility.cells import (
    aggregate_to_cells,
    coarse_cell_id,
    eligible_fraction_file,
    pixel_row_area_km2,
)
from geofrea.land_eligibility.eligibility import (
    EXCLUSION_NAMES,
    EligibilityLayers,
    corridor_key,
    slope_steep_shares,
)
from geofrea.land_eligibility.errors import LandEligibilityError, MissingRequiredLayerError
from geofrea.land_eligibility.fractions import (
    DEFAULT_FACTOR,
    DEFAULT_STRIP_ROWS,
    corridor_half_widths_m,
    mask_setback_fractions,
    polygon_coverage_fraction,
    river_corridor_fraction,
)
from geofrea.land_eligibility.min_area import write_minimum_area
from geofrea.land_eligibility.scenarios import (
    REASON_ELEVATION_MAX,
    REASON_MISSING_ELEVATION,
    candidate_exclusion_reasons,
    candidate_stability,
    check_scenario_order,
    scenario_composition,
    scenario_sets,
)
from geofrea.land_eligibility.table_schemas import (
    LAND_ELIGIBILITY_TABLE_SCHEMA_VERSION,
    Admin1UnitRow,
    CandidateStabilityRow,
    CellRow,
    CoarseCellRow,
)
from geofrea.land_eligibility.windows import (
    ClassCountRows,
    FlagRows,
    NpyRows,
    NpyWriter,
    RasterRows,
    ScenarioStripes,
    StripeInputs,
    prepare_slope_shares,
    resolve_stripe_pixels,
)
from geofrea.siting_layers.physical_layers import SitingLayersResult

logger = logging.getLogger("geofrea.land_eligibility.pipeline")

DOMINANT_CODES = {
    name: i + 1 for i, name in enumerate(EXCLUSION_NAMES)
}  # 0 = nothing excluded in the cell
ANY_CATEGORY = "*"  # a protected-area level that excludes every polygon, whatever its IUCN category (incl. Not Reported)


class ScenarioSummary(BaseModel):
    """One named land-availability scenario of one technology (U-06): its parameter set and its two tables."""

    model_config = ConfigDict(extra="forbid")

    scenario: str
    parameter_set: dict
    varied: dict[str, dict[str, float | None]]
    held_central: dict[str, str]
    min_area: dict | None = None  # what the minimum-area rules removed (`min_area.MinAreaStats`); None when the scenario has none
    n_candidates: int
    eligible_area_km2: float
    cells: Path
    candidates: Path


class TechSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    technology: str
    parameter_set: dict
    scenarios: dict[str, ScenarioSummary]
    stability: Path
    n_cells: int
    n_candidates: int
    cell_area_km2: float
    eligible_area_km2: float
    eligible_share: float
    excluded_share_by_constraint: dict[str, float]
    invalid_pixel_share: float
    candidates: Path
    cells: Path
    cells_0p1deg: (
        Path | None
    )  # only at the default scale: the exact 2 x 2 sum of the 0.05 degree cells
    rasters: dict[str, Path]
    admin1_units: Path
    # OQ-058: candidates of the central scenario above the sensitivity altitude (None: the technology has none), and V-B3: candidates whose
    # Weibull shape is below 1 at each data height (an empty mapping for a technology without Weibull layers); counted, never excluded
    elevation_sensitivity_m: float | None = None
    n_candidates_above_elevation_sensitivity: int | None = None
    # OQ-058, COMMAND 46: the altitude limit in force (cells above it are not candidates in any scenario) and the cells of the central
    # scenario it removed, that is, the ones that would have been candidates by area (None: the technology has no limit)
    elevation_max_m: float | None = None
    n_cells_excluded_by_elevation: int | None = None
    # OQ-060, COMMAND 51: cells of the central scenario with enough eligible area that are not candidates, by reason (`missing_elevation`
    # for every technology, `elevation_max` for a technology with a limit); a cell below the minimum area is in neither
    candidate_exclusions: dict[str, int] = {}
    n_candidates_weibull_k_below_1: dict[str, int] = {}


class EligibilitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: str
    technologies: dict[str, TechSummary]


def artifacts_dir(iso: str) -> Path:
    path = core_paths.phase_dir(iso, "land_eligibility", "artifacts")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read(path: Path | None, name: str, dtype: str = "float64") -> np.ndarray:
    """Band 1 as `dtype` (float64; float32 for the resource layers, whose rasters are float32: the values are the same, half the memory) with nodata and
    non-finite values -> NaN; a missing file is an error, never 'free'."""
    if path is None or not Path(path).exists():
        raise LandEligibilityError(f"required layer {name!r} is missing ({path})")
    with safe_raster_open(path) as src:
        arr = src.read(1).astype(dtype, copy=False)
        nodata = src.nodata
    if nodata is not None and np.isfinite(nodata):
        arr[arr == nodata] = np.nan
    arr[~np.isfinite(arr)] = np.nan
    return arr


def _read_class_counts(path: Path | None) -> tuple[np.ndarray, tuple[int, ...], np.ndarray, int]:
    """(counts per class, class codes, valid mask, samples per pixel) from the aligned class-count raster; fails loudly if absent."""
    if path is None or not Path(path).exists():
        raise LandEligibilityError(
            "the aligned land-cover class counts (F2a `land_cover_counts`) are missing; rerun grid_alignment"
        )
    with safe_raster_open(path) as src:
        counts = src.read()
        tags = src.tags()
        nodata = src.nodata
    classes = tuple(int(c) for c in tags["worldcover_classes"].split(","))
    if 0 in classes or int(tags["samples_per_pixel"]) <= 0:
        raise LandEligibilityError(
            "the aligned land-cover class counts come from the retired centre-count mode (a band for no class, or no samples per "
            "pixel); delete the file and rerun grid_alignment (M-F2a-06, V19)"
        )
    outside = (counts == nodata).all(axis=0)
    counts[:, outside] = 0
    return (
        counts,
        classes,
        ~outside & (counts.sum(axis=0, dtype=np.uint32) > 0),
        int(tags["samples_per_pixel"]),
    )


def _read_slope_counts(path: Path | None) -> tuple[np.ndarray, np.ndarray]:
    """(30 m sample counts per 1 degree slope bin, valid mask) from the aligned slope-bin raster; fails loudly if absent."""
    if path is None or not Path(path).exists():
        raise LandEligibilityError(
            "the aligned slope bins (F2a `slope_counts`) are missing: run `python scripts/acquire_dem30.py`, then rerun grid_alignment"
        )
    with safe_raster_open(path) as src:
        counts = src.read()
        nodata = src.nodata
    outside = (counts == nodata).all(axis=0)
    counts[:, outside] = 0
    return counts, ~outside & (counts.sum(axis=0, dtype=np.uint32) > 0)


def _clipped(
    path: Path | None, name: str, country_gdf: gpd.GeoDataFrame, interim: Path
) -> gpd.GeoDataFrame:
    """The vector clipped to the country, through a cache keyed by the source identity and the polygon.

    Implements: M-F2b-05.

    Raises:
        MissingRequiredLayerError: `path` is None or the file does not exist.
    """
    if path is None or not Path(path).exists():
        raise MissingRequiredLayerError(
            f"required layer {name!r} is absent ({path}); F3 never assumes a zero share for a missing "
            f"protected-area, lake or river layer"
        )
    cache = interim / f"{name}_clipped.gpkg"
    key = clip_cache_key(path, country_gdf)
    current = current_clip_cache(cache, key)
    if current is not None:
        return gpd.read_file(str(current))
    gdf, _ = read_clipped_to_country(path, country_gdf)
    if len(gdf):
        interim.mkdir(parents=True, exist_ok=True)
        gdf.to_file(str(cache), driver="GPKG")
        write_clip_cache_key(cache, key)
    return gdf


def _iucn_subset(
    protected: gpd.GeoDataFrame | None, categories: tuple[str, ...]
) -> gpd.GeoDataFrame | None:
    if protected is None or len(protected) == 0:
        return protected
    if ANY_CATEGORY in categories:
        return protected
    cat = protected["IUCN_CAT"].astype(str).str.strip().str.lower()
    return protected[cat.isin(categories)]


def _fraction_dir(path: Path) -> Path:
    """The directory of the `.npy` files of a share cache: `path` without its suffix."""
    return path.with_suffix("")


def _save_share(path: Path, array: np.ndarray) -> None:
    """One share as an `.npy` file that is whole or absent: written beside, flushed, moved into place (COMMAND 98)."""
    temporary = path.with_name(path.name + ".tmp")
    with open(temporary, "wb") as handle:
        np.save(handle, array, allow_pickle=False)
    replace_durable(temporary, path)


def _fraction_files(path: Path, key: str, build, checkpointed: bool = False) -> dict[str, Path]:
    """The sub-pixel shares of a cache as `.npy` files (name -> file), valid only for the same key (inputs, thresholds, grid, code).

    `build()` returns a dict of arrays or yields `(name, array)` pairs. With `checkpointed`, `build(store)` is called with a `CheckpointStore`
    (`<share>_ckpt`, under the key of the share) from which a builder takes the finished strips of an interrupted build (COMMAND 98); the store is
    cleared when the key is written.

    One file a share, written one at a time, so that a share can be read by rows through a memory map (`windows.NpyRows`). The key is written last:
    a directory without it, or with another, is rebuilt. A cache made by an earlier version as one `.npz` with the same key is converted, not
    rebuilt (COMMAND 91).
    """
    folder = _fraction_dir(path)
    key_file = folder / "_key.txt"
    checkpoint_dir = folder.with_name(folder.name + "_ckpt")

    def listed() -> dict[str, Path]:
        return {p.name[: -len(".npy")]: p for p in sorted(folder.glob("*.npy"))}

    if key_file.exists() and key_file.read_text(encoding="utf-8") == key:
        clear_checkpoint(checkpoint_dir)  # a stop between the key and the cleanup leaves the strips of a build that is finished
        return listed()
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".npz" and path.exists():
        with np.load(path, allow_pickle=False) as data:
            if str(data["_key"]) == key:
                for name in (k for k in data.files if k != "_key"):
                    _save_share(folder / f"{name}.npy", data[name])
                write_text_atomic(key_file, key)
                return listed()
    store = None
    if checkpointed:
        store = CheckpointStore(
            checkpoint_dir,
            make_key(share=key, factor=DEFAULT_FACTOR, strip_rows=DEFAULT_STRIP_ROWS),
            label=f"share {folder.name}",
        )
    arrays = build(store) if checkpointed else build()
    if isinstance(arrays, dict):
        for name in list(arrays):
            _save_share(folder / f"{name}.npy", arrays.pop(name))
    else:  # a builder that yields (name, array) saves each share before it makes the next (the riparian grid is 12 arrays of 61 MB for BRA)
        for name, array in arrays:
            _save_share(folder / f"{name}.npy", array)
            del array
    write_text_atomic(key_file, key)
    if store is not None:
        store.clear()
    return listed()


def _fraction_cache(path: Path, key: str, build) -> dict[str, np.ndarray]:
    """The sub-pixel shares of a cache, read whole (what F7b and the tests use); see `_fraction_files`."""
    return {name: np.load(p, allow_pickle=False) for name, p in _fraction_files(path, key, build).items()}


SHARE_ALGORITHM_VERSION = 2  # 2: river corridors and settlement setbacks (Group 6, COMMAND 97)


def _share_key(kind: str, source: Path | None, country_gdf, transform, shape, **config) -> str:
    """Key of a share cache: the clip of the source (its content, the country polygon and the clip code), the grid, the thresholds and the code
    of the shares (`fractions.py` and what it imports).

    COMMAND 58 found a key made of the file name, its mtime and the grid: the shares of an earlier algorithm were read as current. COMMAND 61: the
    key holds the content of the input through the clip key and the code through `cache_code`, as every other internal cache.
    """
    return cache_key(
        SHARE_ALGORITHM_VERSION,
        [],
        {
            "kind": kind,
            "clip": clip_cache_key(source, country_gdf),
            "transform": [float(v) for v in tuple(transform)[:6]],
            "shape": [int(v) for v in shape],
            **config,
        },
        code=cache_code("subpixel_shares"),
    )


def _required_resources(tech: str, siting: dict[str, Path]) -> dict[str, Path]:
    names = ["dist_grid_km", "dist_sub_km", "dist_road_km"]
    if tech == "solar":
        names.append("pvout_kwh_kwp_day")
    elif tech == "wind":
        for h in WIND_HEIGHTS_M:
            names += [f"weibull_a_{h}m", f"weibull_k_{h}m", f"air_density_{h}m"]
    else:
        raise LandEligibilityError(f"no resource layer list for technology {tech!r}")
    missing = [n for n in names if n not in siting]
    if missing:
        raise LandEligibilityError(f"{tech}: siting layers missing from F2b: {missing}")
    return {n: siting[n] for n in names}


def _cell_raster(path: Path, values: np.ndarray, row0: int, col0: int, dtype: str, nodata) -> Path:
    n_r, n_c = values.shape
    cell_deg = active_scale().cell_deg
    transform = rasterio.Affine(
        cell_deg,
        0,
        CELL_ORIGIN_LON + col0 * cell_deg,
        0,
        -cell_deg,
        CELL_ORIGIN_LAT - row0 * cell_deg,
    )
    with safe_raster_write(
        path,
        driver="GTiff",
        dtype=dtype,
        width=n_c,
        height=n_r,
        count=1,
        crs="EPSG:4326",
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(values.astype(dtype), 1)
    return path


def _pixel_raster(path: Path, values: np.ndarray, like: Path) -> Path:
    with safe_raster_open(like) as ref:
        profile = {"crs": ref.crs, "transform": ref.transform}
    with safe_raster_write(
        path,
        driver="GTiff",
        dtype="float32",
        width=values.shape[1],
        height=values.shape[0],
        count=1,
        nodata=NODATA_FLOAT,
        **profile,
    ) as dst:
        dst.write(np.where(np.isfinite(values), values, NODATA_FLOAT).astype("float32"), 1)
    return path


@dataclass
class SharedLayers:
    """The aligned layers and sub-pixel shares that every technology of a country reads (M-F3-01)."""

    transform: rasterio.Affine
    shape: tuple[int, int]
    country_mask: np.ndarray
    pixel_area: np.ndarray
    slope_counts: np.ndarray | None
    slope_steep: dict[float, np.ndarray]  # E4 share per slope maximum of the scenarios (the bins are dropped after it)
    slope_valid: np.ndarray
    population: np.ndarray
    land_cover_counts: np.ndarray
    land_cover_classes: tuple[int, ...]
    land_cover_valid: np.ndarray
    samples_per_pixel: int
    lakes_fraction: np.ndarray
    protected_fraction: dict[tuple[str, ...], np.ndarray]
    river_corridor: dict[tuple, np.ndarray]  # the corridor share of each (width exponent, buffer steps) of the scenarios
    settlement_share: dict[float, np.ndarray]  # the share within each settlement setback (m) of the scenarios
    settlement_valid: np.ndarray
    flags: dict[str, np.ndarray]


@dataclass
class _ShareNeeds:
    """The distinct slope maxima, IUCN levels, river corridors and settlement setbacks the parameter sets of a country need."""

    slope_maxima: set[float]
    levels: list[tuple[str, ...]]
    corridors: list[tuple]
    setbacks_m: list[float]


def _share_needs(parameter_sets) -> _ShareNeeds:
    sets = list(parameter_sets)
    levels: dict[tuple[str, ...], None] = {}
    for p in sets:
        levels[tuple(sorted(p.iucn_categories))] = None
    return _ShareNeeds(
        slope_maxima={float(p.slope_max_deg) for p in sets},
        levels=list(levels),
        corridors=sorted({corridor_key(p) for p in sets}, key=repr),
        setbacks_m=sorted({float(p.settlement_setback_m) for p in sets if p.pop_density_max_per_km2 is None}),
    )


def _corridor_half_widths(rivers_gdf: gpd.GeoDataFrame, la: LandAvailability, key: tuple) -> np.ndarray:
    """Half-width (m) of the corridor of every reach for a (width exponent, buffer steps) key: `W/2 + B_c(W)`, `W = a Q^b`."""
    column = la.riparian.discharge_column
    if column not in rivers_gdf.columns:
        raise LandEligibilityError(
            f"rivers have no {column} column, so the channel width cannot be estimated (Group 6, eq:g6_width)"
        )
    exponent, exponent_range, steps = key
    return corridor_half_widths_m(
        rivers_gdf[column].to_numpy(), la.riparian.width_coefficient, exponent, steps, exponent_range
    )


def _corridor_shares(rivers_gdf, la: LandAvailability, corridors: list[tuple], transform, shape, store=None):
    """`(name, share)` of each corridor key (`c0`, `c1`, ... in the order of `corridors`), one at a time."""
    for i, key in enumerate(corridors):
        group = None if store is None else store.group(f"c{i}")
        yield (
            f"c{i}",
            river_corridor_fraction(rivers_gdf, _corridor_half_widths(rivers_gdf, la, key), transform, shape, checkpoint=group),
        )


def _settlement_mask(classes: np.ndarray, min_class: int) -> np.ndarray:
    """True where the GHS-SMOD class is a settlement (`min_class` = rural cluster and denser); a pixel with no class is not a settlement here and not valid."""
    with np.errstate(invalid="ignore"):
        return np.nan_to_num(classes, nan=-1.0) >= min_class


def _settlement_key(settlements: Path, transform, shape, la: LandAvailability, setbacks_m: list[float]) -> str:
    return cache_key(
        SHARE_ALGORITHM_VERSION,
        [settlements],
        {
            "kind": "settlements",
            "transform": [float(v) for v in tuple(transform)[:6]],
            "shape": [int(v) for v in shape],
            "min_class": int(la.settlements.min_class),
            "setbacks_m": [float(t) for t in setbacks_m],
        },
        code=cache_code("subpixel_shares"),
    )


def _settlement_shares(mask: np.ndarray, setbacks_m: list[float], transform, shape, store=None):
    group = None if store is None else store.group("s")
    for t, share in mask_setback_fractions(mask, transform, shape, setbacks_m, checkpoint=group).items():
        yield f"s{t}", share


def prepare_shared_layers(
    la: LandAvailability,
    parameter_sets,
    grid_result: GridAlignmentResult,
    country_gdf: gpd.GeoDataFrame,
    protected_path: Path | None,
    lakes_path: Path | None,
    rivers_path: Path | None,
    interim: Path,
) -> SharedLayers:
    """Read the aligned layers and build (or load from the cache) the sub-pixel shares for the parameter sets given.

    Used by F7b, to evaluate the same engine at the pixels of existing plants, and by the tests as the oracle of the stripe engine (M-F3-05, M-F7b-01).

    Args:
        parameter_sets: Every `ParameterSet` the shares must cover (the scenarios of the technologies, or the central ones).

    Raises:
        LandEligibilityError: an aligned layer is missing.
        MissingRequiredLayerError: a protected-area, lake or river layer is absent.
    """
    needs = _share_needs(parameter_sets)
    slope_counts, slope_valid = _read_slope_counts(grid_result.slope_counts)
    slope_steep = slope_steep_shares(slope_counts, needs.slope_maxima)
    del slope_counts  # 41 bins of uint16 a pixel (BRA: 1.2 GB) are not needed again
    population = _read(grid_result.population, "population")
    land_cover_counts, land_cover_classes, land_cover_valid, samples_per_pixel = _read_class_counts(
        grid_result.land_cover_counts
    )
    # the distance-to-grid raster is valid on exactly the in-country pixels of the F2a grid (as in F4, `aligned_mask_path`)
    grid_ref = Path(grid_result.grid)
    country_mask = np.isfinite(_read(grid_ref, "grid"))
    with safe_raster_open(grid_ref) as src:
        transform, shape = src.transform, (src.height, src.width)
    pixel_area = np.repeat(pixel_row_area_km2(transform, shape[0])[:, None], shape[1], axis=1)

    # shared sub-pixel shares: lakes, protected areas for every IUCN level used, river corridors, settlement setbacks
    lakes_gdf = _clipped(lakes_path, "lakes", country_gdf, interim)
    protected_gdf = _clipped(protected_path, "protected", country_gdf, interim)
    rivers_gdf = _clipped(rivers_path, "rivers", country_gdf, interim)
    lakes_fraction = _fraction_cache(
        interim / "lakes_fraction.npz",
        _share_key("lakes", lakes_path, country_gdf, transform, shape),
        lambda: {"a": polygon_coverage_fraction(lakes_gdf, transform, shape)},
    )["a"]
    protected_fraction: dict[tuple[str, ...], np.ndarray] = {}
    for cats in needs.levels:
        arrays = _fraction_cache(
            interim / f"protected_fraction_{'_'.join(cats).replace('*', 'any')}.npz",
            _share_key("protected", protected_path, country_gdf, transform, shape, categories=list(cats)),
            lambda cats=cats: {"a": polygon_coverage_fraction(_iucn_subset(protected_gdf, cats), transform, shape)},
        )
        protected_fraction[cats] = arrays["a"]
    corridor_arrays = _fraction_cache(
        interim / "river_corridor.npz",
        _share_key(
            "river_corridor",
            rivers_path,
            country_gdf,
            transform,
            shape,
            corridors=[repr(k) for k in needs.corridors],
            width_coefficient=float(la.riparian.width_coefficient),
        ),
        lambda: dict(_corridor_shares(rivers_gdf, la, needs.corridors, transform, shape)),
    )
    river_corridor = {key: corridor_arrays[f"c{i}"] for i, key in enumerate(needs.corridors)}

    settlement_class = _read(grid_result.settlements, "settlements", "float32")
    settlement_valid = np.isfinite(settlement_class)
    settlement_share: dict[float, np.ndarray] = {}
    if needs.setbacks_m:
        settlement_mask = _settlement_mask(settlement_class, la.settlements.min_class)
        shares = _fraction_cache(
            interim / "settlement_fraction.npz",
            _settlement_key(Path(grid_result.settlements), transform, shape, la, needs.setbacks_m),
            lambda: dict(_settlement_shares(settlement_mask, needs.setbacks_m, transform, shape)),
        )
        settlement_share = {t: shares[f"s{t}"] for t in needs.setbacks_m}
        del settlement_mask
    del settlement_class

    flags = {
        "dist_grid_capped_share": _read(grid_result.grid_distance_capped, "grid_distance_capped") == 1,
        "dist_road_capped_share": _read(grid_result.roads_distance_capped, "roads_distance_capped") == 1,
        "dist_sub_capped_share": _read(grid_result.poi_distance_capped, "poi_distance_capped") == 1,
    }

    return SharedLayers(
        transform=transform,
        shape=shape,
        country_mask=country_mask,
        pixel_area=pixel_area,
        slope_counts=None,
        slope_steep=slope_steep,
        slope_valid=slope_valid,
        population=population,
        land_cover_counts=land_cover_counts,
        land_cover_classes=land_cover_classes,
        land_cover_valid=land_cover_valid,
        samples_per_pixel=samples_per_pixel,
        lakes_fraction=lakes_fraction,
        protected_fraction=protected_fraction,
        river_corridor=river_corridor,
        settlement_share=settlement_share,
        settlement_valid=settlement_valid,
        flags=flags,
    )


def technology_layers(
    shared: SharedLayers, tech: str, siting_result: SitingLayersResult
) -> tuple[EligibilityLayers, dict[str, np.ndarray]]:
    """The eligibility layers of one technology (its resource layers must be valid) and the resource arrays."""
    resource_paths = _required_resources(tech, siting_result.layers)
    resources = {name: _read(path, name, "float32") for name, path in resource_paths.items()}
    layers = EligibilityLayers(
        country_mask=shared.country_mask,
        pixel_area_km2=shared.pixel_area,
        slope_counts=shared.slope_counts,
        slope_steep_share=shared.slope_steep,
        slope_valid=shared.slope_valid,
        population_count=shared.population,
        land_cover_counts=shared.land_cover_counts,
        land_cover_classes=shared.land_cover_classes,
        land_cover_valid=shared.land_cover_valid,
        samples_per_pixel=shared.samples_per_pixel,
        lakes_fraction=shared.lakes_fraction,
        protected_fraction=shared.protected_fraction,
        river_corridor=shared.river_corridor,
        settlement_share=shared.settlement_share,
        settlement_valid=shared.settlement_valid,
        required_valid={name: np.isfinite(a) for name, a in resources.items()},
    )
    return layers, resources


def _require_vector(path: Path | None, name: str) -> None:
    if path is None or not Path(path).exists():
        raise MissingRequiredLayerError(
            f"required layer {name!r} is absent ({path}); F3 never assumes a zero share for a missing "
            f"protected-area, lake or river layer"
        )


def _prepare_window_rows(width: int) -> int:
    return max(1, 500_000 // max(1, width))


def prepare_stripe_inputs(
    la: LandAvailability,
    parameter_sets,
    grid_result: GridAlignmentResult,
    country_gdf: gpd.GeoDataFrame,
    protected_path: Path | None,
    lakes_path: Path | None,
    rivers_path: Path | None,
    interim: Path,
    scratch: Path,
) -> StripeInputs:
    """The inputs of F3 as row sources (COMMAND 91): the same layers and shares as `prepare_shared_layers`, none of them read whole.

    The sub-pixel shares come from the `.npy` caches of `interim` (built here, before any raster is opened, when the key is not current). The slope
    bins are reduced to the E4 share of each slope maximum and to their validity by one pass over windows, written under `scratch`.

    Raises:
        LandEligibilityError: an aligned layer is missing.
        MissingRequiredLayerError: a protected-area, lake or river layer is absent.
    """
    needs = _share_needs(parameter_sets)
    slope = prepare_slope_shares(grid_result.slope_counts, needs.slope_maxima, scratch)

    grid_rows = RasterRows(grid_result.grid, "grid")
    height, width = grid_rows.shape
    with safe_raster_open(Path(grid_result.grid)) as src:
        transform = src.transform
    # the distance-to-grid raster is valid on exactly the in-country pixels of the F2a grid (as in F4, `aligned_mask_path`)
    country_mask = np.empty((height, width), dtype=bool)
    step = _prepare_window_rows(width)
    for r0 in range(0, height, step):
        country_mask[r0 : r0 + step] = np.isfinite(grid_rows[r0 : r0 + step])

    shape = (height, width)
    # a missing vector layer is an error whether or not its shares are cached; the clipped vector is read only when its shares have to be built, and
    # is released before the next one (COMMAND 91: the three at once, with the riparian work on top, took 1.8 GB on a cold BRA)
    for path_, name_ in ((lakes_path, "lakes"), (protected_path, "protected"), (rivers_path, "rivers")):
        _require_vector(path_, name_)

    def clipped_when_built(path_, name_):
        return _clipped(path_, name_, country_gdf, interim)

    def build_lakes(store=None):
        group = None if store is None else store.group("a")
        return {"a": polygon_coverage_fraction(clipped_when_built(lakes_path, "lakes"), transform, shape, checkpoint=group)}

    lakes_files = _fraction_files(
        interim / "lakes_fraction.npz",
        _share_key("lakes", lakes_path, country_gdf, transform, shape),
        build_lakes,
        checkpointed=True,
    )
    protected: dict[tuple[str, ...], NpyRows] = {}
    for cats in needs.levels:

        def build_protected(store=None, cats=cats):
            subset = _iucn_subset(clipped_when_built(protected_path, "protected"), cats)
            group = None if store is None else store.group("a")
            return {"a": polygon_coverage_fraction(subset, transform, shape, checkpoint=group)}

        files = _fraction_files(
            interim / f"protected_fraction_{'_'.join(cats).replace('*', 'any')}.npz",
            _share_key("protected", protected_path, country_gdf, transform, shape, categories=list(cats)),
            build_protected,
            checkpointed=True,
        )
        protected[cats] = NpyRows(files["a"])
    corridor_files = _fraction_files(
        interim / "river_corridor.npz",
        _share_key(
            "river_corridor",
            rivers_path,
            country_gdf,
            transform,
            shape,
            corridors=[repr(k) for k in needs.corridors],
            width_coefficient=float(la.riparian.width_coefficient),
        ),
        lambda store: _corridor_shares(clipped_when_built(rivers_path, "rivers"), la, needs.corridors, transform, shape, store),
        checkpointed=True,
    )
    settlement_class = RasterRows(grid_result.settlements, "settlements", "float32")
    settlement_files: dict[str, Path] = {}
    if needs.setbacks_m:

        def build_settlements(store=None):
            mask = np.zeros(shape, dtype=bool)
            for r0 in range(0, height, step):
                mask[r0 : r0 + step] = _settlement_mask(settlement_class[r0 : r0 + step], la.settlements.min_class)
            return _settlement_shares(mask, needs.setbacks_m, transform, shape, store)

        settlement_files = _fraction_files(
            interim / "settlement_fraction.npz",
            _settlement_key(Path(grid_result.settlements), transform, shape, la, needs.setbacks_m),
            build_settlements,
            checkpointed=True,
        )
    return StripeInputs(
        transform=transform,
        shape=shape,
        country_mask=country_mask,
        area_row=pixel_row_area_km2(transform, height),
        population=RasterRows(grid_result.population, "population"),
        land_cover=ClassCountRows(grid_result.land_cover_counts),
        slope=slope,
        lakes=NpyRows(lakes_files["a"]),
        protected=protected,
        corridor={key: NpyRows(corridor_files[f"c{i}"]) for i, key in enumerate(needs.corridors)},
        settlement={t: NpyRows(settlement_files[f"s{t}"]) for t in needs.setbacks_m},
        settlement_class=settlement_class,
        flags={
            "dist_grid_capped_share": FlagRows(grid_result.grid_distance_capped, "grid_distance_capped"),
            "dist_road_capped_share": FlagRows(grid_result.roads_distance_capped, "roads_distance_capped"),
            "dist_sub_capped_share": FlagRows(grid_result.poi_distance_capped, "poi_distance_capped"),
        },
    )


class _EligibleRaster:
    """The pixel eligible fraction of a scenario, written window by window (what `_pixel_raster` wrote from the whole array)."""

    def __init__(self, path: Path, like: Path) -> None:
        with safe_raster_open(like) as ref:
            profile = {"crs": ref.crs, "transform": ref.transform, "width": ref.width, "height": ref.height}
        self.path, self.width = path, profile["width"]
        self._stream = open_raster_stream(
            path, driver="GTiff", dtype="float32", count=1, nodata=NODATA_FLOAT, **profile
        )

    def write(self, first_row: int, values: np.ndarray) -> None:
        out = np.where(np.isfinite(values), values, NODATA_FLOAT).astype("float32")
        self._stream.dataset.write(out, 1, window=Window(0, first_row, self.width, out.shape[0]))

    def commit(self) -> Path:
        return self._stream.commit()

    def discard(self) -> None:
        self._stream.discard()


def build_eligibility(
    iso: str,
    experiments_yaml: Path,
    grid_result: GridAlignmentResult,
    siting_result: SitingLayersResult,
    country_gdf: gpd.GeoDataFrame,
    protected_path: Path | None,
    lakes_path: Path | None,
    rivers_path: Path | None,
    admin1_path: Path | None,
    technologies: list[str] | None = None,
    zone_source: ZoneSource | None = None,
    stripe_pixels: int | None = None,
    project_area_km2: Mapping[str, Mapping[str, float]] | None = None,
) -> EligibilitySummary:
    """Eligibility, cells and candidate tables for every configured technology, under the three land scenarios.

    `project_area_km2` maps technology -> scenario -> the area of the reference project `P_ref / PD` (km2), from `parameters.json` (Group 3 and
    Group 1): the minimum cluster of the scenario that takes the project area (`land_availability`) needs it.

    The pixel engine works by stripes of whole cell rows (COMMAND 91, `windows.py`): every input is read by a window, the exclusions and the
    cell sums of a window are computed, and the eligible fraction is written as it goes. `stripe_pixels` (else `GEOFREA_F3_STRIPE_PIXELS`, else
    1,000,000) sets the height of a stripe, that is the memory, and changes no result.
    """
    la: LandAvailability = load_land_availability(experiments_yaml)
    techs = technologies or sorted(la.technologies)
    sets_by_tech = {
        tech: scenario_sets(la, tech, iso, (project_area_km2 or {}).get(tech)) for tech in techs
    }
    out = artifacts_dir(iso)
    interim = core_paths.interim(iso, "land_eligibility")
    interim.mkdir(parents=True, exist_ok=True)
    if admin1_path is None or not Path(admin1_path).exists():
        raise MissingRequiredLayerError(
            f"required layer 'admin1' is absent ({admin1_path}); every cell takes its admin1 unit from it (M-F3-03)"
        )
    units = read_units(gpd.read_file(str(admin1_path)))
    stripe_px = resolve_stripe_pixels(stripe_pixels)
    scratch = interim / "stripes_tmp"
    shutil.rmtree(scratch, ignore_errors=True)
    try:
        inputs = prepare_stripe_inputs(
            la,
            [p for sets in sets_by_tech.values() for p in sets.values()],
            grid_result,
            country_gdf,
            protected_path,
            lakes_path,
            rivers_path,
            interim,
            scratch,
        )
        elevation = RasterRows(
            grid_result.elevation, "elevation", "float32"
        )  # the aligned DEM: the altitude of a cell is its eligible-area-weighted mean (OQ-058)
        return _build_tables(
            iso,
            la,
            techs,
            sets_by_tech,
            project_area_km2,
            out,
            units,
            inputs,
            elevation,
            siting_result,
            Path(grid_result.grid),
            zone_source,
            stripe_px,
            scratch,
        )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _build_tables(
    iso: str,
    la: LandAvailability,
    techs: list[str],
    sets_by_tech: dict[str, dict[str, ParameterSet]],
    project_area_km2: Mapping[str, Mapping[str, float]] | None,
    out: Path,
    units,
    inputs: StripeInputs,
    elevation: RasterRows,
    siting_result: SitingLayersResult,
    grid_ref: Path,
    zone_source: ZoneSource | None,
    stripe_px: int,
    scratch: Path,
) -> EligibilitySummary:
    transform, country_mask = inputs.transform, inputs.country_mask
    admin1_by_cell: dict[int, str] = {}
    units_path = Path(str(out / "admin1_units") + ".parquet")

    summaries: dict[str, TechSummary] = {}
    for tech in techs:
        sets = sets_by_tech[tech]
        composition = scenario_composition(la, tech, iso, (project_area_km2 or {}).get(tech))
        params: ParameterSet = sets["central"]
        resources = {
            name: RasterRows(path, name, "float32")
            for name, path in _required_resources(tech, siting_result.layers).items()
        }
        cells_by_scenario: dict[str, pd.DataFrame] = {}
        scenario_summaries: dict[str, ScenarioSummary] = {}
        central: dict = {}
        n_valid = 0
        for scenario, sparams in sets.items():
            eligible_path = out / eligible_fraction_file(tech, scenario)
            override, min_area_stats = _eligible_after_minimum_area(
                inputs, resources, sparams, scratch, f"{tech}_{scenario}", stripe_px
            )
            raster = _EligibleRaster(eligible_path, grid_ref)
            try:
                stripes = ScenarioStripes(
                    inputs, resources, elevation, sparams, on_eligible=raster.write, eligible_override=override
                )
                cells = aggregate_to_cells(
                    transform,
                    country_mask,
                    stripes.eligible,
                    stripes.exclusions,
                    resources={**stripes.cell_resources, ELEVATION_COLUMN: stripes.elevation_view()},
                    flags=inputs.flags,
                    stripe_pixels=stripe_px,
                )
                if stripes.rows_done != inputs.shape[0]:
                    raise LandEligibilityError(
                        f"{tech}/{scenario}: {stripes.rows_done} of {inputs.shape[0]} pixel rows were computed (the stripes do not cover the grid)"
                    )
                if not admin1_by_cell:
                    ids = assign_admin1(cells["row"].to_numpy(), cells["col"].to_numpy(), units)
                    admin1_by_cell = dict(zip(cells["cell_id"].tolist(), ids.tolist(), strict=True))
                    write_table(
                        _admin1_units(cells.assign(admin1_id=ids), units),
                        units_path,
                        schema_version=LAND_ELIGIBILITY_TABLE_SCHEMA_VERSION,
                        row_model=Admin1UnitRow,
                    )
                if zone_source is not None:
                    cells["pvcz_zone"] = zones_for_cells(
                        cells["lat_c"].to_numpy(), cells["lon_c"].to_numpy(), zone_source
                    ).astype("int8")
                cells["admin1_id"] = cells["cell_id"].map(admin1_by_cell)
                if cells["admin1_id"].isna().any():
                    raise LandEligibilityError(
                        f"{tech}/{scenario}: cells that the first table did not have (the cells of one country do not depend on the scenario)"
                    )
                _check_invariants(f"{tech}/{scenario}", cells, stripes.pixel_total)
                raster.commit()
            finally:
                raster.discard()
            if scenario == "central":
                n_valid = stripes.n_valid
            del stripes
            cells["candidate"] = _is_candidate(cells, sparams)
            candidates = cells[cells["candidate"]].reset_index(drop=True).drop(columns="candidate")
            cells_path = _table_path(out, "cells", tech, scenario)
            cand_path = _table_path(out, "candidates", tech, scenario)
            write_table(
                cells,
                cells_path,
                schema_version=LAND_ELIGIBILITY_TABLE_SCHEMA_VERSION,
                row_model=CellRow,
            )
            write_table(
                candidates,
                cand_path,
                schema_version=LAND_ELIGIBILITY_TABLE_SCHEMA_VERSION,
                row_model=CellRow,
            )
            cells_by_scenario[scenario] = cells
            scenario_summaries[scenario] = ScenarioSummary(
                scenario=scenario,
                parameter_set={
                    k: (list(v) if isinstance(v, tuple) else v) for k, v in sparams.__dict__.items()
                },
                varied=composition.varied,
                held_central=composition.held,
                min_area=None if min_area_stats is None else dataclasses.asdict(min_area_stats),
                n_candidates=len(candidates),
                eligible_area_km2=float(cells["eligible_area_km2"].sum()),
                cells=cells_path,
                candidates=cand_path,
            )
            if scenario == "central":
                central = {"cells": cells, "candidates": candidates}
            logger.info(
                "%s %s [%s]: %d cells, %d candidates, %.1f%% of the land eligible",
                iso,
                tech,
                scenario,
                len(cells),
                len(candidates),
                100 * float(cells["eligible_area_km2"].sum() / cells["cell_area_km2"].sum()),
            )
        check_scenario_order(tech, cells_by_scenario)
        stability_path = Path(str(out / f"candidate_stability_{tech}") + ".parquet")
        write_table(
            candidate_stability(cells_by_scenario, {s: p.elevation_max_m for s, p in sets.items()}),
            stability_path,
            schema_version=LAND_ELIGIBILITY_TABLE_SCHEMA_VERSION,
            row_model=CandidateStabilityRow,
        )

        cells, candidates = central["cells"], central["candidates"]
        coarse_path: Path | None = None
        if active_scale().is_default:
            coarse_path = Path(str(out / f"cells_0p1deg_{tech}") + ".parquet")
            write_table(
                _coarse(cells),
                coarse_path,
                schema_version=LAND_ELIGIBILITY_TABLE_SCHEMA_VERSION,
                row_model=CoarseCellRow,
            )
        rasters = _write_rasters(out, tech, out / eligible_fraction_file(tech, "central"), cells)

        total_area = float(cells["cell_area_km2"].sum())
        sensitivity_m = elevation_sensitivity_m(la, tech)
        limit_m = params.elevation_max_m
        n_excluded_by_elevation = (
            None
            if limit_m is None
            else int(
                (
                    (central["cells"]["eligible_area_km2"] > 0)
                    & (central["cells"][ELEVATION_COLUMN] > limit_m)
                ).sum()
            )
        )
        if limit_m is not None:
            logger.info(
                "%s %s: %d central cells with enough eligible area lie above %.0f m and are not candidates (OQ-058)",
                iso,
                tech,
                n_excluded_by_elevation,
                limit_m,
            )
        reasons = _exclusion_reasons(central["cells"], params)
        exclusions = {
            reason: int((reasons == reason).sum())
            for reason in (
                (REASON_MISSING_ELEVATION, REASON_ELEVATION_MAX)
                if limit_m is not None
                else (REASON_MISSING_ELEVATION,)
            )
        }
        logger.info(
            "%s %s: central cells with enough eligible area that are not candidates, by reason: %s (OQ-060)",
            iso,
            tech,
            exclusions,
        )
        k_below_1 = {
            col: int((candidates[col] < 1.0).sum())
            for col in sorted(candidates.columns)
            if col.startswith("weibull_k_")
        }
        if k_below_1:
            logger.info(
                "%s %s: candidates with Weibull k below 1 (counted, not excluded): %s",
                iso,
                tech,
                k_below_1,
            )
        if sensitivity_m is not None:
            logger.info(
                "%s %s: %d of %d candidates lie above %.0f m (reported as a sensitivity, not excluded; OQ-058)",
                iso,
                tech,
                int((candidates[ELEVATION_COLUMN] > sensitivity_m).sum()),
                len(candidates),
                sensitivity_m,
            )
        summaries[tech] = TechSummary(
            technology=tech,
            parameter_set={
                k: (list(v) if isinstance(v, tuple) else v) for k, v in params.__dict__.items()
            },
            scenarios=scenario_summaries,
            stability=stability_path,
            n_cells=len(cells),
            n_candidates=len(candidates),
            cell_area_km2=total_area,
            eligible_area_km2=float(cells["eligible_area_km2"].sum()),
            eligible_share=float(cells["eligible_area_km2"].sum() / total_area),
            excluded_share_by_constraint={
                name: float(cells[f"excluded_area_km2_{name}"].sum() / total_area)
                for name in EXCLUSION_NAMES
            },
            invalid_pixel_share=float(
                1.0 - n_valid / max(1, np.count_nonzero(country_mask))
            ),
            candidates=scenario_summaries["central"].candidates,
            cells=scenario_summaries["central"].cells,
            cells_0p1deg=coarse_path,
            rasters=rasters,
            admin1_units=units_path,
            elevation_sensitivity_m=sensitivity_m,
            n_candidates_above_elevation_sensitivity=None
            if sensitivity_m is None
            else int((candidates[ELEVATION_COLUMN] > sensitivity_m).sum()),
            n_candidates_weibull_k_below_1=k_below_1,
            elevation_max_m=limit_m,
            n_cells_excluded_by_elevation=n_excluded_by_elevation,
            candidate_exclusions=exclusions,
        )
        del central, cells_by_scenario
    return EligibilitySummary(country_code=iso, technologies=summaries)


def _exclusion_reasons(cells: pd.DataFrame, params: ParameterSet) -> pd.Series:
    return candidate_exclusion_reasons(
        cells["eligible_area_km2"], cells[ELEVATION_COLUMN], params.elevation_max_m
    )


def _is_candidate(cells: pd.DataFrame, params: ParameterSet) -> pd.Series:
    """M-F3-04: any eligible area, an elevation (OQ-060) and, when the technology has an altitude limit in the scenario, not above it (OQ-058)."""
    return (cells["eligible_area_km2"] > 0) & _exclusion_reasons(cells, params).isna()


def _eligible_after_minimum_area(
    inputs: StripeInputs,
    resources,
    params: ParameterSet,
    scratch: Path,
    name: str,
    stripe_px: int,
):
    """The eligible fraction of the whole grid after the minimum-area rules of `params` (Group 6), as a row source, with what the rules removed.

    A scenario with no rule needs no first pass (None, None): the stripes of the cell sums compute its eligible fraction themselves. With a rule, the
    first pass writes the fraction by windows to a file, the clusters are labelled on the whole grid (`min_area.py`) and the stripes of the cell sums read
    the result. Only one scenario's files exist at a time.
    """
    if params.min_pixel_fraction is None and params.min_cluster_km2 is None:
        return None, None
    width = inputs.shape[1]
    scratch.mkdir(parents=True, exist_ok=True)
    raw_path = scratch / f"eligible_raw_{name}.npy"
    first_pass = ScenarioStripes(inputs, resources, None, params)
    writer = NpyWriter(raw_path, inputs.shape, np.float32)
    first_pass.pass_eligible(writer.write, max(1, stripe_px // max(1, width)))
    writer.close()
    del first_pass
    final, stats = write_minimum_area(NpyRows(raw_path), inputs.area_row, params, scratch / f"eligible_final_{name}.npy")
    if final.path != raw_path:
        raw_path.unlink(missing_ok=True)
    return final, stats


def _admin1_units(cells: pd.DataFrame, units: pd.DataFrame) -> pd.DataFrame:
    """The units that hold at least one cell, with the number of cells and their land area (D-F3-012)."""
    grouped = cells.groupby("admin1_id", as_index=False).agg(
        n_cells=("cell_id", "size"), cell_area_km2=("cell_area_km2", "sum")
    )
    return grouped.merge(units[["admin1_id", "admin1_name"]], on="admin1_id", how="left")[
        ["admin1_id", "admin1_name", "n_cells", "cell_area_km2"]
    ]


def _table_path(out: Path, kind: str, tech: str, scenario: str) -> Path:
    """`<kind>_<tech>__<scenario>.parquet` under the F3 artifacts directory (the scenario is part of the file name, V2)."""
    return out / f"{kind}_{tech}__{scenario}.parquet"


def _check_invariants(tech: str, cells: pd.DataFrame, pixel_total: float) -> None:
    """V-03: eligible area never above cell area; the cell total equals the pixel total (summed by stripes of rows)."""
    if (cells["eligible_area_km2"] > cells["cell_area_km2"] * (1 + 1e-6)).any():
        raise LandEligibilityError(f"{tech}: a cell has more eligible area than cell area (V-03)")
    cell_total = float(cells["eligible_area_km2"].sum())
    if abs(pixel_total - cell_total) > 1e-6 * max(1.0, pixel_total):
        raise LandEligibilityError(
            f"{tech}: cell eligible area {cell_total} differs from the pixel total {pixel_total} (V-03)"
        )


def _coarse(cells: pd.DataFrame) -> pd.DataFrame:
    """V-07: the 0.05 degree cells grouped into 0.1 degree cells (areas add up exactly)."""
    df = cells.assign(cell_0p1deg_id=coarse_cell_id(cells["cell_id"].to_numpy()))
    cols = ["cell_area_km2", "eligible_area_km2"] + [
        c for c in cells.columns if c.startswith("excluded_area_km2_")
    ]
    g = df.groupby("cell_0p1deg_id", as_index=False)[cols].sum()
    g["n_cells_0p05deg"] = df.groupby("cell_0p1deg_id").size().to_numpy()
    return g


def _write_rasters(out: Path, tech: str, eligible_path: Path, cells: pd.DataFrame) -> dict[str, Path]:
    row0, col0 = int(cells["row"].min()), int(cells["col"].min())
    n_r, n_c = int(cells["row"].max()) - row0 + 1, int(cells["col"].max()) - col0 + 1
    area = np.full((n_r, n_c), NODATA_FLOAT, dtype="float32")
    dominant = np.zeros((n_r, n_c), dtype="uint8")
    r, c = cells["row"].to_numpy() - row0, cells["col"].to_numpy() - col0
    area[r, c] = cells["eligible_area_km2"].to_numpy()
    dominant[r, c] = (
        cells["dominant_exclusion"].map(DOMINANT_CODES).fillna(0).astype("uint8").to_numpy()
    )
    return {
        "eligible_fraction": eligible_path,  # written by stripes while the cells were summed
        "eligible_area_km2": _cell_raster(
            out / f"eligible_area_km2_{tech}.tif", area, row0, col0, "float32", NODATA_FLOAT
        ),
        "dominant_exclusion": _cell_raster(
            out / f"dominant_exclusion_{tech}.tif", dominant, row0, col0, "uint8", 255
        ),
    }
