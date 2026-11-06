"""COMMAND 100 scripts: the FABDEM zip name of a tile, and the slope bins of a plane whose slope is known."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


acq = load("acquire_fabdem_test_100")
dem = load("audit_slope_dem_test_100")


@pytest.mark.parametrize(
    ("tile", "zip_name"),
    [
        ("S18W051", "S20W060-S10W050_FABDEM_V1-2.zip"),
        ("N38W008", "N30W010-N40E000_FABDEM_V1-2.zip"),
        ("N26E080", "N20E080-N30E090_FABDEM_V1-2.zip"),
        ("S13W046", "S20W050-S10W040_FABDEM_V1-2.zip"),
    ],
)
def test_the_zip_of_a_tile_is_named_by_its_ten_degree_corners(tile, zip_name):
    assert acq.zip_name(tile) == zip_name


def test_a_flat_surface_has_every_sample_in_bin_zero_and_a_frame_of_two_samples_is_left_out():
    bins = dem.slope_bins(np.full((3600, 3600), 100.0, dtype=np.float32), 0)
    assert bins.shape == (41, 100, 100)
    assert bins[1:].sum() == 0
    assert bins[0].sum() == (3600 - 4) ** 2  # the frame of two samples all round


def test_a_plane_of_ten_percent_falls_in_the_bin_of_its_angle_and_is_steeper_than_five_percent_only():
    from geofrea.land_eligibility.eligibility import _steep_share

    lat = 0
    spacing_m = 111_319.49 / 3600.0  # about 30.9 m at the equator, east-west
    z = (np.arange(3600, dtype=np.float32)[None, :] * np.float32(0.10 * spacing_m)) * np.ones((3600, 1), dtype=np.float32)
    bins = dem.slope_bins(z, lat)
    angle = math.degrees(math.atan(0.10))  # 5.71 degrees
    assert bins[int(angle)].sum() == pytest.approx(bins.sum(), rel=0.01)
    interior = np.s_[2:98, 2:98]
    assert _steep_share(bins, math.degrees(math.atan(0.05)))[interior].min() == pytest.approx(1.0)
    assert _steep_share(bins, math.degrees(math.atan(0.20)))[interior].max() == pytest.approx(0.0)


def test_the_3x3_mean_leaves_a_plane_unchanged_inside_and_gives_nothing_at_the_edge_or_next_to_a_gap():
    z = (np.arange(3600, dtype=np.float32)[None, :] * np.ones((3600, 1), dtype=np.float32)).copy()
    z[1000, 1000] = np.nan
    s = dem.smooth_3x3(z)
    assert s[500, 500] == pytest.approx(z[500, 500])
    assert np.isnan(s[0, 5]) and np.isnan(s[1000, 1001]) and np.isnan(s[999, 999])
    assert np.isfinite(s[1000, 1003])
