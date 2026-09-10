"""Pixel-exact regression for suitability_criteria (Fase 2b).

Each criterion's compute function is run on the FROZEN legacy aligned
rasters ($GEOWORLD_BASELINE_DIR/data/processed/<ISO>/*_aligned.tif) and
compared cell-for-cell against the frozen legacy criterion raster
(outputs_baseline_fc7b43d/<ISO>/criteria_builder/tif/<name>.tif).

This isolates Fase 2b from GeoFREA's own grid_alignment (Bloqueio 3
decision (a), 2026-09-10): the legacy aligned rasters are exactly what
produced the frozen baseline, so any difference here is a Fase 2b port
defect, not a grid-regeneration artifact.

Package 1 criteria (road/river/solar/wind) are checked against PRT.
Package 2 criteria (terrain_score, slope_degrees, lc_biomass,
biomass_resource) are checked against PRT AND BRA — terrain_score
especially, because its slope denominator is per-country (PRT=10,
BRA=12, see docs/DECISIONS.md 2026-09-10).
"""

from pathlib import Path

import numpy as np
import pytest
import rasterio

from geofrea.core.config_loader import load_parameters
from geofrea.core.constants import NODATA_FLOAT
from geofrea.suitability_criteria.criteria_functions import (
    compute_biomass_resource,
    compute_grid_suitability,
    compute_lakes_exclusion,
    compute_lc_biomass,
    compute_population_suitability,
    compute_protected_areas,
    compute_river_suitability,
    compute_road_suitability,
    compute_seismic_suitability,
    compute_slope_degrees,
    compute_solar_resource,
    compute_terrain_score,
    compute_wind_resource,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PARAMS = load_parameters(REPO_ROOT / "config" / "parameters.json")
CRITERIA = PARAMS.criteria

# pop_suitability is deliberately NOT bit-exact against the frozen
# baseline under production config: parameters.json sets
# pop_density_threshold = 200.0 (DECISIONS.md 2026-09-10 calibration,
# lowered from the legacy's 300.0). To check that the FORMULA was ported
# faithfully, the regression overrides the threshold back to 300.0 — the
# value the frozen baseline was generated with.
_CRITERIA_POP_300 = CRITERIA.model_copy(deep=True)
_CRITERIA_POP_300.pop_density_threshold = _CRITERIA_POP_300.pop_density_threshold.model_copy(
    update={"value": 300.0}
)

# protected_areas has NO bit-exact parity with the frozen baseline (the
# baseline is graded IUCN scoring; GeoFREA's approved contract, sec 5, is
# a binary mask — a post-baseline decision, not a port gap). Its
# regression lives in test_protected_areas_* below and checks the
# mainland footprint + binary structure, not cell values.
_ISO_TO_COUNTRY_DIR = {"PRT": "Portugal", "BRA": "Brazil"}


def _country_criteria(iso: str):
    return PARAMS.countries[iso].criteria


# name -> (countries, builder(processed_dir, iso) -> (score, ...))
# processed_dir is .../data/processed/<ISO>/ ; legacy land_cover file is
# `<ISO>_lc_aligned.tif` (the legacy filename, not `_land_cover_`).
def _terrain(pdir: Path, iso: str):
    return compute_terrain_score(
        str(pdir / f"{iso}_slope_aligned.tif"),
        str(pdir / f"{iso}_elevation_aligned.tif"),
        CRITERIA,
        _country_criteria(iso).terrain_slope_threshold_deg.value,
    )


CASES: dict[str, tuple[tuple[str, ...], object]] = {
    "road_suitability": (
        ("PRT",),
        lambda pdir, iso: compute_road_suitability(str(pdir / f"{iso}_roads_aligned.tif"), CRITERIA),
    ),
    "river_biomass": (
        ("PRT",),
        lambda pdir, iso: compute_river_suitability(
            str(pdir / f"{iso}_rivers_aligned.tif"), CRITERIA, "biomass"
        ),
    ),
    "solar_resource": (
        ("PRT",),
        lambda pdir, iso: compute_solar_resource(str(pdir / f"{iso}_solar_aligned.tif"), CRITERIA),
    ),
    "wind_resource": (
        ("PRT",),
        lambda pdir, iso: compute_wind_resource(str(pdir / f"{iso}_wind_aligned.tif"), CRITERIA),
    ),
    "terrain_score": (("PRT", "BRA"), _terrain),
    "slope_degrees": (
        ("PRT", "BRA"),
        lambda pdir, iso: compute_slope_degrees(str(pdir / f"{iso}_slope_aligned.tif")),
    ),
    "lc_biomass": (
        ("PRT", "BRA"),
        lambda pdir, iso: compute_lc_biomass(
            str(pdir / f"{iso}_lc_aligned.tif"), CRITERIA.land_suitability.value
        ),
    ),
    "biomass_resource": (
        ("PRT", "BRA"),
        lambda pdir, iso: compute_biomass_resource(
            str(pdir / f"{iso}_lc_aligned.tif"),
            _country_criteria(iso).yield_by_land_cover.value,
            CRITERIA,
        ),
    ),
    "grid_suitability": (
        ("PRT", "BRA"),
        lambda pdir, iso: compute_grid_suitability(str(pdir / f"{iso}_grid_aligned.tif"), CRITERIA),
    ),
    "river_solar": (
        ("PRT", "BRA"),
        lambda pdir, iso: compute_river_suitability(
            str(pdir / f"{iso}_rivers_aligned.tif"), CRITERIA, "solar"
        ),
    ),
    "river_wind": (
        ("PRT", "BRA"),
        lambda pdir, iso: compute_river_suitability(
            str(pdir / f"{iso}_rivers_aligned.tif"), CRITERIA, "wind"
        ),
    ),
    "lakes_exclusion": (
        ("PRT", "BRA"),
        lambda pdir, iso: compute_lakes_exclusion(str(pdir / f"{iso}_lakes_aligned.tif")),
    ),
    "seismic_suitability": (
        ("PRT", "BRA"),
        lambda pdir, iso: compute_seismic_suitability(
            str(pdir / f"{iso}_seismic_aligned.tif"), CRITERIA
        ),
    ),
    # threshold forced back to the legacy's 300.0 (see _CRITERIA_POP_300)
    "pop_suitability": (
        ("PRT", "BRA"),
        lambda pdir, iso: compute_population_suitability(
            str(pdir / f"{iso}_population_aligned.tif"), _CRITERIA_POP_300
        ),
    ),
}

PARAMS_LIST = [
    pytest.param(name, iso, id=f"{name}-{iso}")
    for name, (countries, _) in CASES.items()
    for iso in countries
]


def _valid(a: np.ndarray) -> np.ndarray:
    return np.isfinite(a) & (a != NODATA_FLOAT) & (a >= 0)


@pytest.mark.regression
@pytest.mark.parametrize(("name", "iso"), PARAMS_LIST)
def test_criterion_matches_frozen_baseline(name, iso, baseline_dir, legacy_processed_root):
    pdir = legacy_processed_root / iso
    if not pdir.is_dir():
        pytest.skip(f"legacy aligned rasters for {iso} not found at {pdir}")

    frozen_path = baseline_dir / iso / "criteria_builder" / "tif" / f"{name}.tif"
    if not frozen_path.exists():
        pytest.skip(f"frozen baseline missing: {frozen_path}")
    with rasterio.open(frozen_path) as src:
        frozen = src.read(1).astype(np.float32)

    _countries, builder = CASES[name]
    try:
        score, _transform, _crs = builder(pdir, iso)
    except FileNotFoundError as exc:
        pytest.skip(f"legacy aligned input missing: {exc}")

    assert score.shape == frozen.shape, f"{name}/{iso}: shape {score.shape} != {frozen.shape}"

    fv, sv = _valid(frozen), _valid(score)
    assert np.array_equal(fv, sv), (
        f"{name}/{iso}: valid-pixel mask differs "
        f"(frozen={int(fv.sum())}, geofrea={int(sv.sum())}, "
        f"symmetric_diff={int(np.logical_xor(fv, sv).sum())})"
    )

    diff = np.abs(frozen[fv] - score[fv])
    max_abs = float(diff.max()) if diff.size else 0.0
    rmse = float(np.sqrt(np.mean(diff**2))) if diff.size else 0.0
    n_exact = int((diff == 0).sum())

    assert max_abs == 0.0, (
        f"{name}/{iso}: not pixel-exact vs frozen baseline — "
        f"max|delta|={max_abs:.3e}, RMSE={rmse:.3e}, exact={n_exact}/{diff.size}"
    )


# ── protected_areas — footprint + binary structure (NOT bit-exact) ──────

def _grid_meta(pdir: Path, iso: str) -> tuple:
    import json

    from rasterio.transform import Affine

    m = json.loads((pdir / f"{iso}_grid_metadata.json").read_text())
    return Affine(*m["transform"]), m["width"], m["height"], m["crs"], m["n_valid_pixels"]


def _wdpa_dir(raw_root: Path, iso: str) -> Path | None:
    d = raw_root / "protected_areas" / _ISO_TO_COUNTRY_DIR[iso]
    return d if d.is_dir() else None


def _mainland(raw_root: Path, iso: str):
    from geofrea.core.geo_utils import load_mainland_boundary

    shp = raw_root / "countries_borders" / _ISO_TO_COUNTRY_DIR[iso] / f"gadm41_{iso}_0.shp"
    if not shp.exists():
        pytest.skip(f"GADM boundary missing: {shp}")
    return load_mainland_boundary(shp)


@pytest.mark.regression
@pytest.mark.parametrize("iso", ["PRT", "BRA"])
def test_protected_areas_footprint_matches_frozen(
    iso, baseline_dir, legacy_processed_root, raw_data_root
):
    """protected_areas: mainland footprint identical to the frozen valid
    mask, values strictly binary {0.0, 1.0}, source == 'wdpa'.

    No bit-exact value check: the frozen baseline is graded IUCN scoring,
    GeoFREA's approved contract (audit sec 5) is a binary mask. This is
    the ONE canonical criterion without outputs_baseline_fc7b43d parity,
    by a deliberate post-baseline contract decision.
    """
    pdir = legacy_processed_root / iso
    if not pdir.is_dir():
        pytest.skip(f"legacy aligned rasters for {iso} not found at {pdir}")

    frozen_path = baseline_dir / iso / "criteria_builder" / "tif" / "protected_areas.tif"
    if not frozen_path.exists():
        pytest.skip(f"frozen baseline missing: {frozen_path}")
    with rasterio.open(frozen_path) as src:
        frozen = src.read(1).astype(np.float32)

    transform, width, height, crs, n_valid = _grid_meta(pdir, iso)
    mainland_gdf = _mainland(raw_data_root, iso)
    wdpa = _wdpa_dir(raw_data_root, iso)
    if wdpa is None:
        pytest.skip(f"WDPA directory missing for {iso}")

    score, _t, _c, source = compute_protected_areas(
        wdpa, mainland_gdf, transform, width, height, crs, list(CRITERIA.iucn_strict_categories.value)
    )

    assert score.shape == frozen.shape
    assert source == "wdpa"

    fv, sv = _valid(frozen), _valid(score)
    assert np.array_equal(fv, sv), (
        f"protected_areas/{iso}: footprint differs from frozen "
        f"(frozen={int(fv.sum())}, geofrea={int(sv.sum())})"
    )
    assert int(sv.sum()) == n_valid, f"{int(sv.sum())} != grid_metadata n_valid {n_valid}"

    inside = score[sv]
    assert set(np.unique(inside).tolist()) <= {0.0, 1.0}, "protected_areas is not binary"
    assert (inside == 0.0).any(), f"no strict-category exclusions burned for {iso}"
