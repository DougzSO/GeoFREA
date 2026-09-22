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
Package 2 criteria (slope_degrees, lc_biomass, biomass_resource) are
checked against PRT AND BRA. terrain_score is ALSO checked against both
(its slope denominator is per-country — PRT=10, BRA=12, see
docs/DECISIONS.md 2026-09-10) but has its own dedicated test below,
bit-exact only away from the nodata elevation boundary — see
docs/DECISIONS.md 2026-09-11, "TRI contamination guard".
"""

from pathlib import Path

import numpy as np
import pytest
import rasterio
from scipy.ndimage import binary_dilation

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
    # terrain_score is NOT in this blind-parity table (docs/DECISIONS.md
    # 2026-09-11, "TRI contamination guard"): its own dedicated test
    # below (test_terrain_score_matches_frozen_baseline_away_from_nodata_boundary)
    # checks bit-exact parity only AWAY from pixels whose TRI stencil
    # touches a nodata elevation cell -- a deliberate divergence there,
    # same class as derive_slope_from_dem's own nodata-adjacency fix.
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


# pop_suitability is NOT bit-exact in CI (Linux, numpy 2.5.3) despite being
# bit-exact locally (Windows, numpy 2.5.2) -- confirmed root cause 2026-09-14
# (see docs/DECISIONS.md same date): sub-ULP float32 log1p rounding noise
# between numpy's vectorized kernel and the platform libm, NOT a threshold
# comparison or a logic defect (0/1154 PRT and 0/18434 BRA differing pixels
# have pop >= threshold; max delta = 0.75 float32 ULP). Every other
# criterion in CASES stays bit-exact (atol=0.0) -- this tolerance is scoped
# to pop_suitability alone.
_POP_SUITABILITY_ATOL = 2e-7  # ~2x the observed max delta (8.941e-08)


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

    atol = _POP_SUITABILITY_ATOL if name == "pop_suitability" else 0.0
    assert max_abs <= atol, (
        f"{name}/{iso}: not pixel-exact vs frozen baseline — "
        f"max|delta|={max_abs:.3e} (tolerance={atol:.3e}), RMSE={rmse:.3e}, "
        f"exact={n_exact}/{diff.size}"
    )


# ── terrain_score — bit-exact AWAY from the nodata boundary only ────────
#
# docs/DECISIONS.md 2026-09-11, "TRI contamination guard": compute_terrain_
# score now excludes NaN/nodata elevation neighbours from the TRI stencil
# explicitly (instead of feeding the raw nodata sentinel into the
# neighbour differencing, which is what BOTH the legacy and GeoFREA's own
# pre-fix code did). This deliberately changes the result at any pixel
# whose 3x3 TRI stencil touches a nodata elevation cell -- the exact same
# class of fix already accepted for derive_slope_from_dem
# (2026-09-11 too). Confirmed live (this session) against both frozen
# PRT/BRA baselines: bit-exact holds perfectly everywhere ELSE.


@pytest.mark.regression
@pytest.mark.parametrize("iso", ["PRT", "BRA"])
def test_terrain_score_matches_frozen_baseline_away_from_nodata_boundary(
    iso, baseline_dir, legacy_processed_root
):
    pdir = legacy_processed_root / iso
    if not pdir.is_dir():
        pytest.skip(f"legacy aligned rasters for {iso} not found at {pdir}")

    frozen_path = baseline_dir / iso / "criteria_builder" / "tif" / "terrain_score.tif"
    if not frozen_path.exists():
        pytest.skip(f"frozen baseline missing: {frozen_path}")
    with rasterio.open(frozen_path) as src:
        frozen = src.read(1).astype(np.float32)

    try:
        score, _transform, _crs = _terrain(pdir, iso)
    except FileNotFoundError as exc:
        pytest.skip(f"legacy aligned input missing: {exc}")

    assert not np.isnan(score).any(), f"terrain_score/{iso}: a NaN leaked into the output"

    elev_path = pdir / f"{iso}_elevation_aligned.tif"
    with rasterio.open(elev_path) as src:
        elev = src.read(1)
        elev_nodata = src.nodata
    invalid_elev = ~np.isfinite(elev) | (elev == elev_nodata)
    # 3x3 dilation: any pixel whose TRI stencil touches an invalid
    # elevation cell -- exactly the set this fix is allowed to change.
    nodata_boundary = binary_dilation(invalid_elev, structure=np.ones((3, 3), dtype=bool))
    away = ~nodata_boundary

    fv, sv = _valid(frozen), _valid(score)
    assert np.array_equal(fv & away, sv & away), (
        f"terrain_score/{iso}: valid-pixel mask differs away from the nodata "
        f"boundary (frozen={int((fv & away).sum())}, geofrea={int((sv & away).sum())}) "
        "-- this must stay bit-exact"
    )

    both_valid_away = fv & sv & away
    diff = np.abs(frozen[both_valid_away] - score[both_valid_away])
    max_abs = float(diff.max()) if diff.size else 0.0
    assert max_abs == 0.0, (
        f"terrain_score/{iso}: not pixel-exact away from the nodata boundary — "
        f"max|delta|={max_abs:.3e} over {int(both_valid_away.sum())} compared pixels"
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

    score, _t, _c, source, _repair_report = compute_protected_areas(
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
