"""The scale of a run: the cell size is a parameter, the code does not branch on it (M-F3-06, V-07; D-F3-013, D-F4-020)."""

from __future__ import annotations

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from geofrea.core import paths as core_paths
from geofrea.core.scale import (
    DEFAULT_SCALE,
    SCALE_DEPENDENT_PHASES,
    SCALES,
    UnknownScaleError,
    active_scale,
    get_scale,
    manifest_file_name,
    phase_directory_name,
    use_scale,
)
from geofrea.land_eligibility import cells
from geofrea.land_eligibility.cells import (
    GridNotOnLatticeError,
    aggregate_to_cells,
    cell_center,
    cell_id,
    cell_row_col,
    coarse_cell_id,
    lattice_window,
    pad_to_window,
    row_col_from_id,
)

LON0, LAT0 = 10.05, 5.05  # on the 0.05 degree lattice, not on the 0.1 degree one
H, W = 20, 30  # 4 x 6 cells of 0.05 degree, 2 x 3 of 0.1 degree plus the padding
TRANSFORM = from_origin(LON0, LAT0, 0.01, 0.01)


@pytest.mark.unit
def test_the_default_scale_is_the_decision_cell_of_s_06_and_the_coarse_one_is_twice_as_wide():
    assert active_scale() is DEFAULT_SCALE
    assert (DEFAULT_SCALE.cell_deg, DEFAULT_SCALE.nesting_pixels) == (0.05, 5)
    assert (DEFAULT_SCALE.n_rows, DEFAULT_SCALE.n_cols) == (3600, 7200)
    coarse = get_scale("0p1deg")
    assert (coarse.cell_deg, coarse.nesting_pixels) == (pytest.approx(0.1), 10)
    assert (coarse.n_rows, coarse.n_cols) == (1800, 3600)
    assert not coarse.is_default and DEFAULT_SCALE.is_default
    assert set(SCALES) == {"0p05deg", "0p1deg"}
    with pytest.raises(UnknownScaleError, match="0p2deg"):
        get_scale("0p2deg")


@pytest.mark.unit
def test_use_scale_restores_the_previous_scale_even_after_an_error():
    with pytest.raises(RuntimeError), use_scale("0p1deg"):
        assert active_scale().scale_id == "0p1deg"
        raise RuntimeError("boom")
    assert active_scale() is DEFAULT_SCALE


@pytest.mark.unit
def test_only_the_phases_that_depend_on_the_cell_size_change_directory_and_the_manifest_is_named_by_the_scale(
    tmp_path,
):
    assert phase_directory_name("land_eligibility") == "land_eligibility"
    assert manifest_file_name() == "manifest.json"
    with use_scale("0p1deg"):
        assert phase_directory_name("land_eligibility") == "land_eligibility__0p1deg"
        assert phase_directory_name("robustness_analysis") == "robustness_analysis__0p1deg"
        for pixel_phase in (
            "data_acquisition",
            "grid_alignment",
            "siting_layers",
            "external_inputs",
        ):
            assert pixel_phase not in SCALE_DEPENDENT_PHASES
            assert phase_directory_name(pixel_phase) == pixel_phase
        assert manifest_file_name() == "manifest__0p1deg.json"
        assert core_paths.phase_dir("ZZZ", "technical_potential", "artifacts").parts[-3:] == (
            "ZZZ",
            "technical_potential__0p1deg",
            "artifacts",
        )
        assert core_paths.manifest_path("ZZZ").name == "manifest__0p1deg.json"
    assert core_paths.manifest_path("ZZZ").name == "manifest.json"


@pytest.mark.unit
def test_cell_ids_and_centers_follow_the_lattice_of_the_scale():
    lat, lon = np.array([5.04, -33.512]), np.array([10.04, -70.3])
    for scale_id in SCALES:
        with use_scale(scale_id) as scale:
            row, col = cell_row_col(lat, lon)
            ids = cell_id(row, col)
            assert (ids // scale.n_cols == row).all() and (ids % scale.n_cols == col).all()
            r2, c2 = row_col_from_id(ids)
            assert (r2 == row).all() and (c2 == col).all()
            lat_c, lon_c = cell_center(row, col)
            assert (np.abs(lat_c - lat) <= scale.cell_deg / 2 + 1e-9).all()
            assert (np.abs(lon_c - lon) <= scale.cell_deg / 2 + 1e-9).all()
    row5, col5 = cell_row_col(np.array([5.04]), np.array([10.04]))
    with use_scale("0p1deg"):
        row1, col1 = cell_row_col(np.array([5.04]), np.array([10.04]))
    assert (row1, col1) == (
        row5 // 2,
        col5 // 2,
    )  # the 0.05 degree lattice nests the 0.1 degree one
    assert coarse_cell_id(cell_id(row5, col5)) == row1 * 3600 + col1


@pytest.mark.unit
def test_a_grid_that_starts_inside_a_coarse_cell_is_padded_to_whole_cells():
    window = lattice_window(TRANSFORM, H, W)  # the default scale: whole 5 x 5 cells, nothing to pad
    assert (window.pad_top, window.pad_left, window.n_rows, window.n_cols) == (0, 0, 4, 6)
    with use_scale("0p1deg"):
        window = lattice_window(TRANSFORM, H, W)
        assert (window.k, window.pad_top, window.pad_left) == (10, 5, 5)
        assert (window.n_rows, window.n_cols) == (3, 4)  # 5 + 20 pixels -> 3 cells, 5 + 30 -> 4
        padded = pad_to_window(np.ones((H, W)), window)
        assert padded.shape == (30, 40) and padded.sum() == H * W
        assert padded[:5].sum() == 0 and padded[:, :5].sum() == 0
    with pytest.raises(GridNotOnLatticeError):
        lattice_window(from_origin(LON0 + 0.013, LAT0, 0.01, 0.01), H, W)


def _world(seed: int = 1):
    rng = np.random.default_rng(seed)
    mask = rng.random((H, W)) > 0.15
    eligible = np.where(mask, rng.random((H, W)), 0.0)
    exclusions = {f"E{i}": rng.random((H, W)) * mask for i in (1, 2)}
    resources = {"r": np.where(mask, rng.uniform(1, 9, (H, W)), np.nan)}
    flags = {"capped": rng.random((H, W)) > 0.7}
    return mask, eligible, exclusions, resources, flags


@pytest.mark.unit
def test_coarse_cells_are_the_exact_sums_and_area_weighted_means_of_the_fine_cells():
    """The same function at the two scales: areas add up exactly, a weighted mean is the weighted mean of the fine means (V-07)."""
    mask, eligible, exclusions, resources, flags = _world()
    fine = aggregate_to_cells(TRANSFORM, mask, eligible, exclusions, resources, flags)
    with use_scale("0p1deg"):
        coarse = aggregate_to_cells(TRANSFORM, mask, eligible, exclusions, resources, flags)
    fine = fine.assign(parent=coarse_cell_id(fine["cell_id"].to_numpy()))
    fine["w_r"] = fine["r"].fillna(0) * fine["eligible_area_km2"]
    fine["w_f"] = fine["capped"].fillna(0) * fine["eligible_area_km2"]
    sums = fine.groupby("parent")[
        [
            "cell_area_km2",
            "eligible_area_km2",
            "excluded_area_km2_E1",
            "excluded_area_km2_E2",
            "w_r",
            "w_f",
        ]
    ].sum()
    got = coarse.set_index("cell_id").loc[sums.index]
    assert len(coarse) == len(sums)
    for column in (
        "cell_area_km2",
        "eligible_area_km2",
        "excluded_area_km2_E1",
        "excluded_area_km2_E2",
    ):
        np.testing.assert_allclose(got[column], sums[column], rtol=1e-12)
    el = sums["eligible_area_km2"]
    with np.errstate(invalid="ignore", divide="ignore"):
        np.testing.assert_allclose(got["r"], (sums["w_r"] / el).where(el > 0), rtol=1e-12)
        np.testing.assert_allclose(got["capped"], (sums["w_f"] / el).where(el > 0), rtol=1e-12)
    assert (
        coarse["row"].max() - coarse["row"].min() == 2
    )  # three coarse cell rows cover the padded grid
    total = lambda t: t["cell_area_km2"].sum()
    assert total(coarse) == pytest.approx(total(fine), rel=1e-12)


@pytest.mark.unit
def test_the_cells_of_a_country_mask_at_the_coarse_scale_are_the_parents_of_the_fine_cells(
    tmp_path,
):
    from geofrea.climate_forcing.forcing import country_cells

    mask, *_ = _world(2)
    path = tmp_path / "mask.tif"
    with rasterio.open(
        path, "w", driver="GTiff", height=H, width=W, count=1, dtype="float32",
        crs="EPSG:4326", transform=TRANSFORM, nodata=-9999.0,
    ) as dst:  # fmt: skip
        dst.write(np.where(mask, 1.0, -9999.0).astype("float32"), 1)
    fine = country_cells(path)
    with use_scale("0p1deg"):
        coarse = country_cells(path)
    assert set(coarse["cell_id"]) == set(coarse_cell_id(fine["cell_id"].to_numpy()))
    assert len(coarse) < len(fine)
    lon_c = coarse["lon_c"].to_numpy()
    assert np.allclose((lon_c + 180.0) / 0.1 % 1, 0.5)
    assert np.allclose((90.0 - coarse["lat_c"].to_numpy()) / 0.1 % 1, 0.5)


@pytest.mark.unit
def test_no_module_branches_on_the_scale_by_name():
    """The code reads the active scale; a test of `scale_id` or a `0p1deg` literal outside `core/scale.py` would be a special branch (V-07)."""
    import re
    from pathlib import Path

    src = Path(cells.__file__).resolve().parents[1]
    offenders = []
    for py in src.rglob("*.py"):
        if py.name == "scale.py":
            continue
        for number, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if (
                re.search(r"scale_id\s*(==|!=|in\b)|[\"']0p1deg[\"']", code)
                and "cells_0p1deg" not in code
            ):
                offenders.append(f"{py.relative_to(src)}:{number}: {line.strip()}")
    assert offenders == []
