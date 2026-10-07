"""F3 land_eligibility end to end for one country: eligibility, 0.05 degree cells, candidate tables, maps (M-F3-01 to M-F3-06).

Reads the aligned F2a rasters, the F2b physical layers and the vector sources (protected areas, lakes, rivers); writes under
`outputs/<ISO3>/land_eligibility/artifacts/`, per technology:

  - `cells_<tech>.parquet`: every 0.05 degree cell with at least one in-country pixel (areas, excluded area per constraint,
    dominant exclusion, resource and distance means weighted by eligible area, `candidate` flag);
  - `candidates_<tech>.parquet`: the cells with `eligible_area_km2 >= min_eligible_area_km2` (M-F3-04/05);
  - `cells_0p1deg_<tech>.parquet`: the same cells grouped 2 x 2 for the scale check (V-07);
  - `eligible_fraction_<tech>.tif` (pixels), `eligible_area_km2_<tech>.tif` and `dominant_exclusion_<tech>.tif` (cells).

The parameter set is the nominal one of `land_availability` in `config/experiments.yaml` (it feeds F4-F7); the engine itself is a
function of one `ParameterSet`, so ranges can be sampled later without changing it.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pydantic import BaseModel, ConfigDict

from geofrea.core import paths as core_paths
from geofrea.core.constants import CELL_DEG, CELL_ORIGIN_LAT, CELL_ORIGIN_LON, NODATA_FLOAT
from geofrea.core.geo_utils import (
    clip_cache_is_current,
    clip_cache_key,
    read_clipped_to_country,
    write_clip_cache_key,
)
from geofrea.core.raster_io import safe_raster_open, safe_raster_write
from geofrea.grid_alignment.schemas import GridAlignmentResult
from geofrea.land_eligibility.cells import (
    aggregate_to_cells,
    candidate_cells,
    coarse_cell_id,
    pixel_row_area_km2,
)
from geofrea.land_eligibility.eligibility import (
    EXCLUSION_NAMES,
    EligibilityLayers,
    eligible_fraction,
    valid_pixels,
)
from geofrea.land_eligibility.fractions import polygon_coverage_fraction, river_fractions
from geofrea.land_eligibility.parameters import (
    LandAvailability,
    ParameterSet,
    load_land_availability,
    nominal_set,
    riparian_discharges_m3s,
    riparian_thresholds_km,
)
from geofrea.suitability_criteria.physical_layers import SitingLayersResult

logger = logging.getLogger("geofrea.land_eligibility.pipeline")

WIND_HEIGHTS_M = (100, 150, 200)
DOMINANT_CODES = {name: i + 1 for i, name in enumerate(EXCLUSION_NAMES)}  # 0 = nothing excluded in the cell
ANY_CATEGORY = "*"  # a protected-area level that excludes every polygon, whatever its IUCN category (incl. Not Reported)


class LandEligibilityError(RuntimeError):
    """An input of F3 is missing or an invariant of the result fails (A-09, V-03)."""


class TechSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    technology: str
    parameter_set: dict
    n_cells: int
    n_candidates: int
    cell_area_km2: float
    eligible_area_km2: float
    eligible_share: float
    excluded_share_by_constraint: dict[str, float]
    invalid_pixel_share: float
    candidates: Path
    cells: Path
    cells_0p1deg: Path
    rasters: dict[str, Path]


class EligibilitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: str
    technologies: dict[str, TechSummary]


def artifacts_dir(iso: str) -> Path:
    path = core_paths.phase_dir(iso, "land_eligibility", "artifacts")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read(path: Path | None, name: str) -> np.ndarray:
    """Band 1 as float64 with nodata and non-finite values -> NaN; a missing file is an error, never 'free'."""
    if path is None or not Path(path).exists():
        raise LandEligibilityError(f"required layer {name!r} is missing ({path})")
    with safe_raster_open(path) as src:
        arr = src.read(1).astype("float64")
        nodata = src.nodata
    if nodata is not None and np.isfinite(nodata):
        arr[arr == nodata] = np.nan
    arr[~np.isfinite(arr)] = np.nan
    return arr


def _read_class_counts(path: Path | None) -> tuple[np.ndarray, tuple[int, ...], np.ndarray, int]:
    """(counts per class, class codes, valid mask, samples per pixel) from the aligned class-count raster; fails loudly if absent."""
    if path is None or not Path(path).exists():
        raise LandEligibilityError("the aligned land-cover class counts (F2a `land_cover_counts`) are missing; rerun grid_alignment")
    with safe_raster_open(path) as src:
        counts = src.read()
        tags = src.tags()
        nodata = src.nodata
    classes = tuple(int(c) for c in tags["worldcover_classes"].split(","))
    outside = (counts == nodata).all(axis=0)
    counts[:, outside] = 0
    return counts, classes, ~outside & (counts.sum(axis=0, dtype=np.uint32) > 0), int(tags["samples_per_pixel"])


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


def _clipped(path: Path | None, name: str, country_gdf: gpd.GeoDataFrame, interim: Path) -> gpd.GeoDataFrame | None:
    """The vector clipped to the country, through a cache keyed by the source identity and the polygon."""
    if path is None or not Path(path).exists():
        return None
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


def _iucn_subset(protected: gpd.GeoDataFrame | None, categories: tuple[str, ...]) -> gpd.GeoDataFrame | None:
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


def _key(*parts) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


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
    transform = rasterio.Affine(CELL_DEG, 0, CELL_ORIGIN_LON + col0 * CELL_DEG, 0, -CELL_DEG, CELL_ORIGIN_LAT - row0 * CELL_DEG)
    with safe_raster_write(
        path, driver="GTiff", dtype=dtype, width=n_c, height=n_r, count=1, crs="EPSG:4326", transform=transform, nodata=nodata
    ) as dst:
        dst.write(values.astype(dtype), 1)
    return path


def _pixel_raster(path: Path, values: np.ndarray, like: Path) -> Path:
    with safe_raster_open(like) as ref:
        profile = {"crs": ref.crs, "transform": ref.transform}
    with safe_raster_write(
        path, driver="GTiff", dtype="float32", width=values.shape[1], height=values.shape[0], count=1, nodata=NODATA_FLOAT, **profile
    ) as dst:
        dst.write(np.where(np.isfinite(values), values, NODATA_FLOAT).astype("float32"), 1)
    return path


def build_eligibility(
    iso: str,
    experiments_yaml: Path,
    grid_result: GridAlignmentResult,
    siting_result: SitingLayersResult,
    country_gdf: gpd.GeoDataFrame,
    protected_path: Path | None,
    lakes_path: Path | None,
    rivers_path: Path | None,
    technologies: list[str] | None = None,
) -> EligibilitySummary:
    """Eligibility, cells and candidate tables for every configured technology (nominal parameter set)."""
    la: LandAvailability = load_land_availability(experiments_yaml)
    techs = technologies or sorted(la.technologies)
    out = artifacts_dir(iso)
    interim = core_paths.interim(iso, "land_eligibility")
    interim.mkdir(parents=True, exist_ok=True)

    slope_counts, slope_valid = _read_slope_counts(grid_result.slope_counts)
    population = _read(grid_result.population, "population")
    land_cover_counts, land_cover_classes, land_cover_valid, samples_per_pixel = _read_class_counts(grid_result.land_cover_counts)
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
    id_parts = (transform, shape, DOMINANT_CODES)
    lakes_fraction = _fraction_cache(
        interim / "lakes_fraction.npz",
        _key("lakes", lakes_path, Path(lakes_path).stat().st_mtime_ns if lakes_path else 0, *id_parts),
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
            _key("protected", protected_path, Path(protected_path).stat().st_mtime_ns if protected_path else 0, cats, *id_parts),
            lambda cats=cats: {"a": polygon_coverage_fraction(_iucn_subset(protected_gdf, cats), transform, shape)},
        )
        protected_fraction[cats] = arrays["a"]
    thr = sorted(thresholds)
    discharges = riparian_discharges_m3s(la)
    rip = _fraction_cache(
        interim / "riparian_fraction.npz",
        _key("rivers", rivers_path, Path(rivers_path).stat().st_mtime_ns if rivers_path else 0, thr, discharges, *id_parts),
        lambda: {f"q{q}_t{t}": a for (q, t), a in river_fractions(rivers_gdf, transform, shape, thr, discharges).items()},
    )
    riparian_fraction = {(q, t): rip[f"q{q}_t{t}"] for q in discharges for t in thr}

    flags = {
        "dist_grid_capped_share": _read(grid_result.grid_distance_capped, "grid_distance_capped") == 1,
        "dist_road_capped_share": _read(grid_result.roads_distance_capped, "roads_distance_capped") == 1,
    }

    summaries: dict[str, TechSummary] = {}
    for tech in techs:
        params: ParameterSet = nominal_set(la.technologies[tech])
        resource_paths = _required_resources(tech, siting_result.layers)
        resources = {name: _read(path, name) for name, path in resource_paths.items()}
        layers = EligibilityLayers(
            country_mask=country_mask,
            pixel_area_km2=pixel_area,
            slope_counts=slope_counts,
            slope_valid=slope_valid,
            population_count=population,
            land_cover_counts=land_cover_counts,
            land_cover_classes=land_cover_classes,
            land_cover_valid=land_cover_valid,
            samples_per_pixel=samples_per_pixel,
            lakes_fraction=lakes_fraction,
            protected_fraction=protected_fraction,
            riparian_fraction=riparian_fraction,
            required_valid={name: np.isfinite(a) for name, a in resources.items()},
        )
        eligible, excl = eligible_fraction(layers, params)
        cells = aggregate_to_cells(
            transform, country_mask, eligible, excl, resources=resources, flags=flags
        )
        _check_invariants(tech, cells, eligible, pixel_area, country_mask)
        cells["candidate"] = cells["eligible_area_km2"] >= params.min_eligible_area_km2
        candidates = candidate_cells(cells, params.min_eligible_area_km2).drop(columns="candidate")

        base = out / f"{{}}_{tech}"
        cells_path = Path(str(base).format("cells") + ".parquet")
        cand_path = Path(str(base).format("candidates") + ".parquet")
        coarse_path = Path(str(base).format("cells_0p1deg") + ".parquet")
        cells.to_parquet(cells_path, index=False)
        candidates.to_parquet(cand_path, index=False)
        _coarse(cells).to_parquet(coarse_path, index=False)
        rasters = _write_rasters(out, tech, eligible, cells, transform, grid_ref)

        valid = valid_pixels(layers)
        total_area = float(cells["cell_area_km2"].sum())
        summaries[tech] = TechSummary(
            technology=tech,
            parameter_set={k: (list(v) if isinstance(v, tuple) else v) for k, v in params.__dict__.items()},
            n_cells=len(cells),
            n_candidates=len(candidates),
            cell_area_km2=total_area,
            eligible_area_km2=float(cells["eligible_area_km2"].sum()),
            eligible_share=float(cells["eligible_area_km2"].sum() / total_area),
            excluded_share_by_constraint={
                name: float(cells[f"excluded_area_km2_{name}"].sum() / total_area) for name in EXCLUSION_NAMES
            },
            invalid_pixel_share=float(1.0 - np.count_nonzero(valid) / max(1, np.count_nonzero(country_mask))),
            candidates=cand_path,
            cells=cells_path,
            cells_0p1deg=coarse_path,
            rasters=rasters,
        )
        logger.info(
            "%s %s: %d cells, %d candidates, %.1f%% of the land eligible", iso, tech, len(cells), len(candidates),
            100 * summaries[tech].eligible_share,
        )
    return EligibilitySummary(country_code=iso, technologies=summaries)


def _check_invariants(tech: str, cells: pd.DataFrame, eligible: np.ndarray, pixel_area: np.ndarray, mask: np.ndarray) -> None:
    """V-03: eligible area never above cell area; the cell total equals the pixel total."""
    if (cells["eligible_area_km2"] > cells["cell_area_km2"] * (1 + 1e-6)).any():
        raise LandEligibilityError(f"{tech}: a cell has more eligible area than cell area (V-03)")
    pixel_total = float((eligible * pixel_area * mask).sum())
    cell_total = float(cells["eligible_area_km2"].sum())
    if abs(pixel_total - cell_total) > 1e-6 * max(1.0, pixel_total):
        raise LandEligibilityError(f"{tech}: cell eligible area {cell_total} differs from the pixel total {pixel_total} (V-03)")


def _coarse(cells: pd.DataFrame) -> pd.DataFrame:
    """V-07: the 0.05 degree cells grouped into 0.1 degree cells (areas add up exactly)."""
    df = cells.assign(cell_0p1deg_id=coarse_cell_id(cells["cell_id"].to_numpy()))
    cols = ["cell_area_km2", "eligible_area_km2"] + [c for c in cells.columns if c.startswith("excluded_area_km2_")]
    g = df.groupby("cell_0p1deg_id", as_index=False)[cols].sum()
    g["n_cells_0p05deg"] = df.groupby("cell_0p1deg_id").size().to_numpy()
    return g


def _write_rasters(out: Path, tech: str, eligible: np.ndarray, cells: pd.DataFrame, transform, grid_ref: Path) -> dict[str, Path]:
    row0, col0 = int(cells["row"].min()), int(cells["col"].min())
    n_r, n_c = int(cells["row"].max()) - row0 + 1, int(cells["col"].max()) - col0 + 1
    area = np.full((n_r, n_c), NODATA_FLOAT, dtype="float32")
    dominant = np.zeros((n_r, n_c), dtype="uint8")
    r, c = cells["row"].to_numpy() - row0, cells["col"].to_numpy() - col0
    area[r, c] = cells["eligible_area_km2"].to_numpy()
    dominant[r, c] = cells["dominant_exclusion"].map(DOMINANT_CODES).fillna(0).astype("uint8").to_numpy()
    return {
        "eligible_fraction": _pixel_raster(out / f"eligible_fraction_{tech}.tif", eligible, grid_ref),
        "eligible_area_km2": _cell_raster(out / f"eligible_area_km2_{tech}.tif", area, row0, col0, "float32", NODATA_FLOAT),
        "dominant_exclusion": _cell_raster(out / f"dominant_exclusion_{tech}.tif", dominant, row0, col0, "uint8", 255),
    }
