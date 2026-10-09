"""Derived sanity ranges of the F2b layers (V-04, H-6): ISO 2533 air density and the bounding-box bound on distances."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from geofrea.core.config_loader import load_audit_config
from geofrea.siting_layers.sanity import (
    SanityError,
    air_density_envelope,
    bbox_diagonal_km,
    country_geometry,
    dem30_extremes,
    derived_range,
    isa_density_kg_m3,
)

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.unit
def test_isa_density_matches_the_standard_atmosphere_table():
    """ISO 2533 troposphere: 1.225 at sea level, then the tabulated values to the 3rd decimal (1000, 5000, 8000, 11000 m)."""
    assert isa_density_kg_m3(0.0) == pytest.approx(1.2250, abs=5e-5)
    assert isa_density_kg_m3(1000.0) == pytest.approx(1.1117, abs=2e-4)
    assert isa_density_kg_m3(5000.0) == pytest.approx(0.7364, abs=5e-4)
    assert isa_density_kg_m3(11000.0) == pytest.approx(0.3648, abs=1e-3)
    assert isa_density_kg_m3(-1000.0) > 1.225  # below sea level the air is denser


@pytest.mark.unit
def test_isa_density_decreases_with_altitude_and_is_vectorized():
    z = np.linspace(-500.0, 9000.0, 50)
    rho = isa_density_kg_m3(z)
    assert rho.shape == z.shape and (np.diff(rho) < 0).all()


@pytest.mark.unit
def test_the_himalayan_density_of_ind_corresponds_to_about_8_km_of_altitude():
    """The lowest density of the IND layer, 0.51 kg/m3, is the standard atmosphere at about 8 km, i.e. at the highest peaks."""
    z = np.linspace(7000.0, 9500.0, 2501)
    altitude = z[np.argmin(np.abs(isa_density_kg_m3(z) - 0.51))]
    assert 8000.0 <= altitude <= 8700.0


@pytest.mark.unit
@pytest.mark.parametrize("z", [-5001.0, 11001.0])
def test_isa_density_refuses_altitudes_outside_the_troposphere(z):
    with pytest.raises(SanityError, match="troposphere"):
        isa_density_kg_m3(z)


@pytest.mark.unit
def test_density_envelope_is_ordered_and_follows_the_elevation_span_and_the_layer_height():
    low, high = air_density_envelope(0.0, 2000.0, 100.0)
    assert low < high
    assert high == pytest.approx(isa_density_kg_m3(100.0)) and low == pytest.approx(
        isa_density_kg_m3(2100.0)
    )
    higher_layer = air_density_envelope(0.0, 2000.0, 200.0)
    assert higher_layer[0] < low and higher_layer[1] < high  # a taller layer is thinner air
    with pytest.raises(SanityError):
        air_density_envelope(100.0, 0.0, 100.0)


@pytest.mark.unit
def test_bbox_diagonal_is_an_upper_bound_of_the_distance_across_the_box():
    # 1 degree square on the equator: sqrt(110.57^2 + 111.32^2) km
    assert bbox_diagonal_km(0.0, 0.0, 1.0, 1.0) == pytest.approx(156.9, abs=0.6)
    # the box of a mid-latitude country is wider in km at its southern edge: the bound uses the widest scale
    south_wider = bbox_diagonal_km(0.0, 30.0, 10.0, 40.0)
    assert south_wider > bbox_diagonal_km(0.0, 40.0, 10.0, 50.0)
    with pytest.raises(SanityError):
        bbox_diagonal_km(1.0, 0.0, 1.0, 1.0)


def _write_dem(path: Path, z: np.ndarray, origin=(10.0, 5.0)) -> None:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=z.shape[0],
        width=z.shape[1],
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(origin[0], origin[1], 0.01, 0.01),
        nodata=-9999.0,
    ) as dst:
        dst.write(z.astype("float32"), 1)


@pytest.mark.unit
def test_country_geometry_widens_the_aligned_dem_with_the_30_m_tiles_and_caches(tmp_path):
    aligned = tmp_path / "aligned.tif"
    _write_dem(aligned, np.array([[0.0, 100.0], [200.0, -9999.0]]))
    tiles = tmp_path / "tiles"
    tiles.mkdir()
    _write_dem(tiles / "t1.tif", np.array([[-5.0, 50.0], [3000.0, 20.0]]))
    plain = country_geometry(aligned)
    assert (plain.z_min_m, plain.z_max_m) == (0.0, 200.0)
    cache = tmp_path / "cache" / "extremes.json"
    widened = country_geometry(aligned, tiles, cache)
    assert (widened.z_min_m, widened.z_max_m) == (-5.0, 3000.0)
    assert json.loads(cache.read_text())["tiles"] == ["t1.tif"]
    (tiles / "t1.tif").unlink()
    _write_dem(tiles / "t1.tif", np.array([[1.0, 2.0], [3.0, 4.0]]))
    assert dem30_extremes(tiles, cache) == (-5.0, 3000.0)  # same tile names: the cache is used
    _write_dem(tiles / "t2.tif", np.array([[7000.0, 1.0], [1.0, 1.0]]))
    assert dem30_extremes(tiles, cache)[1] == 7000.0  # a new tile invalidates it
    with pytest.raises(SanityError, match="no 30 m DEM tile"):
        dem30_extremes(tmp_path / "empty")


@pytest.mark.unit
def test_derived_range_has_no_derivation_for_weibull_layers():
    geometry = country_geometry_stub()
    assert (
        derived_range("weibull_a", geometry) is None
        and derived_range("weibull_k", geometry) is None
    )
    assert derived_range("dist_grid_km", geometry)[0] == 0.0
    with pytest.raises(SanityError, match="height"):
        derived_range("air_density", geometry)


def country_geometry_stub():
    from geofrea.siting_layers.sanity import CountryGeometry

    return CountryGeometry(z_min_m=0.0, z_max_m=1000.0, west=0.0, south=0.0, east=2.0, north=2.0)


@pytest.mark.unit
def test_audit_yaml_declares_the_derivations_and_leaves_only_weibull_to_oq_053():
    cfg = load_audit_config(REPO / "config" / "audit.yaml")
    assert {k for k, v in cfg.derived_ranges.items() if v.derivation} == {
        "air_density",
        "dist_grid_km",
        "dist_road_km",
    }
    assert {k for k, v in cfg.derived_ranges.items() if not v.derivation} == {
        "weibull_a",
        "weibull_k",
    }
    assert all(
        v.open_question == "OQ-053"
        for k, v in cfg.derived_ranges.items()
        if k.startswith("weibull")
    )
    assert all(
        v.source for v in cfg.derived_ranges.values() if v.derivation
    )  # a derivation names its source
    assert cfg.layers["solar"].sanity_range == (0.7, 6.8)  # PVOUT keeps the product's own range
