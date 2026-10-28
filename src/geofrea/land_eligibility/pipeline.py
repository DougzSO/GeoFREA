"""F3 land_eligibility end to end for one country: eligibility, 0.05 degree cells, candidate tables, maps (M-F3-01 to M-F3-06).

Reads the aligned F2a rasters, the F2b physical layers and the vector sources (protected areas, lakes, rivers); writes under
`outputs/<ISO3>/land_eligibility/artifacts/`, per technology:

  - `cells_<tech>.parquet`: every 0.05 degree cell with at least one in-country pixel (areas, excluded area per constraint,
    dominant exclusion, resource and distance means weighted by eligible area, `candidate` flag);
  - `candidates_<tech>.parquet`: the cells with `eligible_area_km2 >= min_eligible_area_km2` (M-F3-04/05);
  - `cells_0p1deg_<tech>.parquet` (default scale only): the same cells grouped 2 x 2, the area check of a 0.1 degree run (V-07);
  - `admin1_units.parquet`: the GADM level-1 units that hold cells, with their cell counts (each cell table carries `admin1_id`, D-F3-012);
  - `eligible_fraction_<tech>.tif` (pixels), `eligible_area_km2_<tech>.tif` and `dominant_exclusion_<tech>.tif` (cells).

The parameter set is the nominal one of `land_availability` in `config/experiments.yaml` (it feeds F4-F7); the engine itself is a
function of one `ParameterSet`, so ranges can be sampled later without changing it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pydantic import BaseModel, ConfigDict

from geofrea.config_models.land_availability import (
    ELEVATION_COLUMN,
    LandAvailability,
    ParameterSet,
    elevation_sensitivity_m,
    load_land_availability,
    nominal_set,
    riparian_discharges_m3s,
    riparian_thresholds_km,
)
from geofrea.core import paths as core_paths
from geofrea.core.cache_code import cache_code
from geofrea.core.cache_key import cache_key
from geofrea.core.constants import (
    CELL_ORIGIN_LAT,
    CELL_ORIGIN_LON,
    NODATA_FLOAT,
    WIND_HEIGHTS_M,
)
from geofrea.core.geo_utils import (
    clip_cache_is_current,
    clip_cache_key,
    read_clipped_to_country,
    write_clip_cache_key,
)
from geofrea.core.raster_io import safe_raster_open, safe_raster_write
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
    eligible_fraction,
    slope_steep_shares,
    valid_pixels,
)
from geofrea.land_eligibility.fractions import polygon_coverage_fraction, river_fractions
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
from geofrea.siting_layers.physical_layers import SitingLayersResult

logger = logging.getLogger("geofrea.land_eligibility.pipeline")

DOMINANT_CODES = {
    name: i + 1 for i, name in enumerate(EXCLUSION_NAMES)
}  # 0 = nothing excluded in the cell
ANY_CATEGORY = "*"  # a protected-area level that excludes every polygon, whatever its IUCN category (incl. Not Reported)


class LandEligibilityError(RuntimeError):
    """An input of F3 is missing or an invariant of the result fails (A-09, V-03)."""


class MissingRequiredLayerError(LandEligibilityError):
    """A protected-area, lake or river layer of a configured country is absent; a zero share is never assumed (M-F2b-05)."""


class ScenarioSummary(BaseModel):
    """One named land-availability scenario of one technology (U-06): its parameter set and its two tables."""

    model_config = ConfigDict(extra="forbid")

    scenario: str
    parameter_set: dict
    varied: dict[str, dict[str, float]]
    held_central: dict[str, str]
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
    if clip_cache_is_current(cache, key):
        return gpd.read_file(str(cache))
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


def _fraction_cache(path: Path, key: str, build) -> dict[str, np.ndarray]:
    """npz cache of sub-pixel shares, valid only for the same key (inputs, thresholds, grid)."""
    if path.exists():
        with np.load(path, allow_pickle=False) as data:
            if str(data["_key"]) == key:
                return {k: data[k] for k in data.files if k != "_key"}
    arrays = build()
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, _key=np.array(key), **arrays)
    return arrays


SHARE_ALGORITHM_VERSION = 1


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
    names = ["dist_grid_km", "dist_road_km"]
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
    riparian_fraction: dict[tuple[float, float], np.ndarray]
    flags: dict[str, np.ndarray]


def prepare_shared_layers(
    la: LandAvailability,
    techs: list[str],
    grid_result: GridAlignmentResult,
    country_gdf: gpd.GeoDataFrame,
    protected_path: Path | None,
    lakes_path: Path | None,
    rivers_path: Path | None,
    interim: Path,
) -> SharedLayers:
    """Read the aligned layers and build (or load from the cache) the sub-pixel shares for the levels and setbacks of `techs`.

    Used by F3 and, to evaluate the same engine at the pixels of existing plants, by F7b (M-F3-05, M-F7b-01).

    Raises:
        LandEligibilityError: an aligned layer is missing.
        MissingRequiredLayerError: a protected-area, lake or river layer is absent.
    """
    slope_counts, slope_valid = _read_slope_counts(grid_result.slope_counts)
    slope_maxima = {
        p.slope_max_deg
        for t in techs
        for p in (*scenario_sets(la.technologies[t]).values(), nominal_set(la.technologies[t]))
    }
    slope_steep = slope_steep_shares(slope_counts, slope_maxima)
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

    # shared sub-pixel shares: lakes, protected areas for every IUCN level used, riparian for every setback used
    lakes_gdf = _clipped(lakes_path, "lakes", country_gdf, interim)
    protected_gdf = _clipped(protected_path, "protected", country_gdf, interim)
    rivers_gdf = _clipped(rivers_path, "rivers", country_gdf, interim)
    lakes_fraction = _fraction_cache(
        interim / "lakes_fraction.npz",
        _share_key("lakes", lakes_path, country_gdf, transform, shape),
        lambda: {"a": polygon_coverage_fraction(lakes_gdf, transform, shape)},
    )["a"]

    level_sets: dict[tuple[str, ...], None] = {}
    thresholds: set[float] = set()
    for t in techs:
        p = nominal_set(la.technologies[t])
        level_sets[tuple(sorted(p.iucn_categories))] = None
        thresholds.update(riparian_thresholds_km(la.technologies[t]))
    protected_fraction: dict[tuple[str, ...], np.ndarray] = {}
    for cats in level_sets:
        arrays = _fraction_cache(
            interim / f"protected_fraction_{'_'.join(cats).replace('*', 'any')}.npz",
            _share_key(
                "protected", protected_path, country_gdf, transform, shape, categories=list(cats)
            ),
            lambda cats=cats: {
                "a": polygon_coverage_fraction(_iucn_subset(protected_gdf, cats), transform, shape)
            },
        )
        protected_fraction[cats] = arrays["a"]
    thr = sorted(thresholds)
    discharges = riparian_discharges_m3s(la)
    rip = _fraction_cache(
        interim / "riparian_fraction.npz",
        _share_key(
            "rivers",
            rivers_path,
            country_gdf,
            transform,
            shape,
            thresholds=thr,
            discharges=[float(q) for q in discharges],
        ),
        lambda: {
            f"q{q}_t{t}": a
            for (q, t), a in river_fractions(rivers_gdf, transform, shape, thr, discharges).items()
        },
    )
    riparian_fraction = {(q, t): rip[f"q{q}_t{t}"] for q in discharges for t in thr}

    flags = {
        "dist_grid_capped_share": _read(grid_result.grid_distance_capped, "grid_distance_capped")
        == 1,
        "dist_road_capped_share": _read(grid_result.roads_distance_capped, "roads_distance_capped")
        == 1,
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
        riparian_fraction=riparian_fraction,
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
        riparian_fraction=shared.riparian_fraction,
        required_valid={name: np.isfinite(a) for name, a in resources.items()},
    )
    return layers, resources


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
) -> EligibilitySummary:
    """Eligibility, cells and candidate tables for every configured technology (nominal parameter set)."""
    la: LandAvailability = load_land_availability(experiments_yaml)
    techs = technologies or sorted(la.technologies)
    out = artifacts_dir(iso)
    interim = core_paths.interim(iso, "land_eligibility")
    interim.mkdir(parents=True, exist_ok=True)
    if admin1_path is None or not Path(admin1_path).exists():
        raise MissingRequiredLayerError(
            f"required layer 'admin1' is absent ({admin1_path}); every cell takes its admin1 unit from it (M-F3-03)"
        )
    units = read_units(gpd.read_file(str(admin1_path)))
    admin1_by_cell: dict[int, str] = {}
    units_path = Path(str(out / "admin1_units") + ".parquet")

    shared = prepare_shared_layers(
        la, techs, grid_result, country_gdf, protected_path, lakes_path, rivers_path, interim
    )
    transform, grid_ref = shared.transform, Path(grid_result.grid)
    country_mask, pixel_area, flags = shared.country_mask, shared.pixel_area, shared.flags
    elevation = _read(
        grid_result.elevation, "elevation", "float32"
    )  # the aligned DEM: the altitude of a cell is its eligible-area-weighted mean (OQ-058)

    summaries: dict[str, TechSummary] = {}
    for tech in techs:
        sets = scenario_sets(la.technologies[tech])
        composition = scenario_composition(la.technologies[tech])
        params: ParameterSet = sets["central"]
        layers, resources = technology_layers(shared, tech, siting_result)
        cell_resources = {
            **resources,
            ELEVATION_COLUMN: elevation,
        }  # elevation is a column of the cells, not a validity requirement
        cells_by_scenario: dict[str, pd.DataFrame] = {}
        scenario_summaries: dict[str, ScenarioSummary] = {}
        central: dict = {}
        for scenario, sparams in sets.items():
            eligible, excl = eligible_fraction(layers, sparams)
            cells = aggregate_to_cells(
                transform, country_mask, eligible, excl, resources=cell_resources, flags=flags
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
            cells["admin1_id"] = cells["cell_id"].map(admin1_by_cell)
            if cells["admin1_id"].isna().any():
                raise LandEligibilityError(
                    f"{tech}/{scenario}: cells that the first table did not have (the cells of one country do not depend on the scenario)"
                )
            _check_invariants(f"{tech}/{scenario}", cells, eligible, pixel_area, country_mask)
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
            if scenario != "central":  # the central one is written with the other rasters below
                _pixel_raster(out / eligible_fraction_file(tech, scenario), eligible, grid_ref)
            cells_by_scenario[scenario] = cells
            scenario_summaries[scenario] = ScenarioSummary(
                scenario=scenario,
                parameter_set={
                    k: (list(v) if isinstance(v, tuple) else v) for k, v in sparams.__dict__.items()
                },
                varied=composition.varied,
                held_central=composition.held,
                n_candidates=len(candidates),
                eligible_area_km2=float(cells["eligible_area_km2"].sum()),
                cells=cells_path,
                candidates=cand_path,
            )
            if scenario == "central":
                central = {
                    "eligible": eligible,
                    "excl": excl,
                    "cells": cells,
                    "candidates": candidates,
                }
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
            candidate_stability(
                cells_by_scenario, params.min_eligible_area_km2, params.elevation_max_m
            ),
            stability_path,
            schema_version=LAND_ELIGIBILITY_TABLE_SCHEMA_VERSION,
            row_model=CandidateStabilityRow,
        )

        eligible, excl, cells, candidates = (
            central["eligible"],
            central["excl"],
            central["cells"],
            central["candidates"],
        )
        coarse_path: Path | None = None
        if active_scale().is_default:
            coarse_path = Path(str(out / f"cells_0p1deg_{tech}") + ".parquet")
            write_table(
                _coarse(cells),
                coarse_path,
                schema_version=LAND_ELIGIBILITY_TABLE_SCHEMA_VERSION,
                row_model=CoarseCellRow,
            )
        rasters = _write_rasters(out, tech, eligible, cells, transform, grid_ref)

        valid = valid_pixels(layers)
        total_area = float(cells["cell_area_km2"].sum())
        sensitivity_m = elevation_sensitivity_m(la, tech)
        limit_m = params.elevation_max_m
        n_excluded_by_elevation = (
            None
            if limit_m is None
            else int(
                (
                    (central["cells"]["eligible_area_km2"] >= params.min_eligible_area_km2)
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
                1.0 - np.count_nonzero(valid) / max(1, np.count_nonzero(country_mask))
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
    return EligibilitySummary(country_code=iso, technologies=summaries)


def _exclusion_reasons(cells: pd.DataFrame, params: ParameterSet) -> pd.Series:
    return candidate_exclusion_reasons(
        cells["eligible_area_km2"],
        cells[ELEVATION_COLUMN],
        params.min_eligible_area_km2,
        params.elevation_max_m,
    )


def _is_candidate(cells: pd.DataFrame, params: ParameterSet) -> pd.Series:
    """M-F3-04: eligible area at least the minimum, an elevation (OQ-060) and, when the technology has an altitude limit, not above it (OQ-058)."""
    return (cells["eligible_area_km2"] >= params.min_eligible_area_km2) & _exclusion_reasons(
        cells, params
    ).isna()


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


def _check_invariants(
    tech: str, cells: pd.DataFrame, eligible: np.ndarray, pixel_area: np.ndarray, mask: np.ndarray
) -> None:
    """V-03: eligible area never above cell area; the cell total equals the pixel total."""
    if (cells["eligible_area_km2"] > cells["cell_area_km2"] * (1 + 1e-6)).any():
        raise LandEligibilityError(f"{tech}: a cell has more eligible area than cell area (V-03)")
    pixel_total = float((eligible * pixel_area * mask).sum())
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


def _write_rasters(
    out: Path, tech: str, eligible: np.ndarray, cells: pd.DataFrame, transform, grid_ref: Path
) -> dict[str, Path]:
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
        "eligible_fraction": _pixel_raster(
            out / f"eligible_fraction_{tech}.tif", eligible, grid_ref
        ),
        "eligible_area_km2": _cell_raster(
            out / f"eligible_area_km2_{tech}.tif", area, row0, col0, "float32", NODATA_FLOAT
        ),
        "dominant_exclusion": _cell_raster(
            out / f"dominant_exclusion_{tech}.tif", dominant, row0, col0, "uint8", 255
        ),
    }
