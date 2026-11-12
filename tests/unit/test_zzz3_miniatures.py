"""The three miniatures of COMMAND 132 (ZZZ3, ZZZ3b, ZZZ3c = country codes ZZA, ZZB, ZZC): values computed by hand (`scripts/zzz3_world.py`).

ZZA: 45 degrees west, only the required keys in `countries.yaml`, a grid with no voltage attribute. ZZB: straddles the Greenwich meridian, climate in 0..360, and the
change factors must equal, bit for bit, those of the same field written in -180..180. ZZC: 65 degrees north, pixel and cell area from the ellipsoid. A country
that crosses 180 degrees is refused by the guard.
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
import yaml
from shapely.geometry import box

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import zzz3_world as world

from geofrea.climate_forcing import forcing as fc
from geofrea.climate_forcing import members as mem
from geofrea.climate_forcing.change_factors import bilinear_to_points
from geofrea.core.country_guard import (
    AntimeridianCountryError,
    CountryEntry,
    polygon_crosses_antimeridian,
    refuse_antimeridian_countries,
    validate_countries_config,
)

pytestmark = pytest.mark.unit

GCM = mem.Gcm("GFDL-ESM4", "gfdl_esm4", hazard_channel=True)
WINDOW = (2041, 2070)


def _countries() -> dict:
    return yaml.safe_load((REPO / "config" / "countries.yaml").read_text(encoding="utf-8"))


# -- the entries --------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("iso", ["ZZA", "ZZB", "ZZC"])
def test_each_miniature_has_its_own_entry_with_a_fixture_root_and_validates(iso):
    raw = _countries()
    entries = validate_countries_config(raw)
    assert iso in entries and raw[iso]["synthetic_fixture_root"] == f"fixtures/synthetic_{iso.lower()}/raw"


@pytest.mark.parametrize("iso", ["ZZA", "ZZB", "ZZC"])
def test_a_miniature_entry_has_no_optional_key(iso):
    required = {name for name, f in CountryEntry.model_fields.items() if f.is_required()}
    assert set(_countries()[iso]) == required | {"synthetic_fixture_root"}


def test_the_synthetic_fetched_layers_resolve_under_the_own_code(tmp_path, monkeypatch):
    from geofrea.data_acquisition import local_layers

    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    raw = tmp_path / "fixtures" / "synthetic_zza" / "raw"
    written = world.write_borders(raw, "ZZA")
    assert local_layers.resolve_synthetic_fetched_layer("ZZA", "borders") == written
    assert written.name == "gadm41_ZZA_0.shp"


def test_the_miniature_codes_are_in_the_name_file():
    names = yaml.safe_load((REPO / "config" / "country_names.yaml").read_text(encoding="utf-8"))
    for iso in ("ZZA", "ZZB", "ZZC"):
        assert iso in names["en"] and iso in names["pt"]


# -- ZZA: 45 degrees west -------------------------------------------------------------------------------------------------------------------


def test_zza_forcing_at_minus_45_from_a_0_360_file_is_the_closed_form(tmp_path):
    lat = np.arange(-2.0, 3.01, 1.0)
    lon_true = np.arange(-50.0, -39.9, 1.0)  # stored as 310..320
    registry = world.write_climate(tmp_path, "0..360", lat, lon_true)
    fields = fc.member_factor_fields(registry, GCM, "ssp126", WINDOW, (0.0, 0.2), (-45.15, -44.85))
    plat = np.array([0.05, 0.10, 0.15, 0.20])
    plon = np.array([-45.125, -45.025, -44.925, -44.875])
    np.testing.assert_allclose(bilinear_to_points(fields["dT"], plat, plon), world.dt_field(plat, plon), rtol=0, atol=1e-9)
    np.testing.assert_allclose(bilinear_to_points(fields["delta_rsds"], plat, plon), world.RSDS_RATIO, rtol=0, atol=1e-12)
    np.testing.assert_allclose(bilinear_to_points(fields["delta_wind"], plat, plon), world.WIND_RATIO, rtol=0, atol=1e-12)


def test_zza_grid_without_a_voltage_attribute_gives_no_eligible_substation_and_no_poi_layer(tmp_path):
    from geofrea.grid_alignment.poi import select_poi
    from geofrea.grid_alignment.vector_alignment import rasterize_linear_distance

    frame = gpd.read_file(world.write_grid_without_voltage(tmp_path, "ZZA"))
    assert "voltage" not in frame.columns
    points, counts = select_poi(frame, 138.0, 50.0)
    assert counts.total == 1 and counts.with_tag == 0 and counts.excluded_no_voltage == 1 and counts.eligible == 0 and len(points) == 0
    country = gpd.GeoDataFrame(geometry=[box(-45.15, 0, -44.85, 0.2)], crs="EPSG:4326")
    assert rasterize_linear_distance(None, tmp_path / "poi.tif", country, None, "poi", 100.0) is None


# -- ZZB: the Greenwich meridian ---------------------------------------------------------------------------------------------------------


def _greenwich_fields(tmp_path, convention):
    lat = np.arange(-2.0, 3.01, 1.0)
    lon_true = np.arange(-5.0, 5.01, 1.0)
    sub = tmp_path / convention.replace("..", "_")
    sub.mkdir()
    registry = world.write_climate(sub, convention, lat, lon_true)
    return fc.member_factor_fields(registry, GCM, "ssp126", WINDOW, (0.0, 0.2), (-0.15, 0.15))


PLAT = np.array([0.025, 0.075, 0.125, 0.175, 0.2])
PLON = np.array([-0.125, -0.075, -0.025, 0.0, 0.025, 0.075, 0.125])


def test_zzb_forcing_from_a_0_360_file_equals_the_one_from_a_minus_180_180_file_bit_for_bit(tmp_path):
    a = _greenwich_fields(tmp_path, "0..360")
    b = _greenwich_fields(tmp_path, "-180..180")
    assert list(a) == list(b)
    lat2, lon2 = np.meshgrid(PLAT, PLON)
    for name in a:
        assert np.array_equal(a[name].values, b[name].values), name
        assert np.array_equal(a[name]["lon"].values, b[name]["lon"].values), name
        va = bilinear_to_points(a[name], lat2.ravel(), lon2.ravel())
        vb = bilinear_to_points(b[name], lat2.ravel(), lon2.ravel())
        assert np.array_equal(va, vb), name
        assert np.isfinite(va).all(), name


def test_zzb_forcing_across_the_seam_is_the_closed_form(tmp_path):
    a = _greenwich_fields(tmp_path, "0..360")
    lat2, lon2 = np.meshgrid(PLAT, PLON)
    np.testing.assert_allclose(bilinear_to_points(a["dT"], lat2.ravel(), lon2.ravel()), world.dt_field(lat2.ravel(), lon2.ravel()), rtol=0, atol=1e-9)
    assert float(a["dT"]["lon"].min()) < 0 < float(a["dT"]["lon"].max())  # the axis is continuous across Greenwich


def test_a_box_that_does_not_cross_the_seam_is_subset_as_before(tmp_path):
    lat = np.arange(-2.0, 3.01, 1.0)
    lon_true = np.arange(-50.0, -39.9, 1.0)
    registry = world.write_climate(tmp_path, "0..360", lat, lon_true)
    da = fc._load_variable(registry.entries["cmip6/gfdl_esm4/ssp126/tas"], "tas", (0.0, 0.2), (-45.15, -44.85))
    values = list(da["lon"].values)  # the file's own values, no shift: -45.15 is 314.85, and the margin of native cells is kept on each side
    assert values == sorted(values) and 314.0 in values and 316.0 in values and min(values) > 180.0 and len(values) == len(set(values))


def test_the_cmip6_crop_of_a_country_across_greenwich_puts_the_axis_in_minus_180_180(tmp_path):
    import xarray as xr

    from geofrea.data_acquisition.fetchers.cmip6 import crop_to_country_polygon

    lat = np.arange(-2.0, 3.01, 1.0)
    lon_true = np.arange(-5.0, 5.01, 1.0)
    registry = world.write_climate(tmp_path, "0..360", lat, lon_true)
    source = registry.entries["cmip6/gfdl_esm4/ssp126/tas"].global_path
    polygon = tmp_path / "poly.shp"
    gpd.GeoDataFrame(geometry=[box(-1.5, -0.5, 1.5, 1.5)], crs="EPSG:4326").to_file(polygon)
    out = tmp_path / "crop.nc"
    crop_to_country_polygon(Path(source), polygon, out)
    with xr.open_dataset(out) as ds:
        assert list(ds["lon"].values) == [-1.0, 0.0, 1.0]
        assert not np.isnan(ds["tas"].values).any()
        np.testing.assert_allclose(ds["tas"].isel(time=0, lat=1).values, 290.0 + world.dt_field(1.0, np.array([-1.0, 0.0, 1.0])))  # the row is lat 1.0


def test_the_cmip6_crop_of_a_country_that_does_not_cross_the_seam_keeps_the_file_axis(tmp_path):
    import xarray as xr

    from geofrea.data_acquisition.fetchers.cmip6 import crop_to_country_polygon

    lat = np.arange(-2.0, 3.01, 1.0)
    lon_true = np.arange(-50.0, -39.9, 1.0)
    registry = world.write_climate(tmp_path, "0..360", lat, lon_true)
    polygon = tmp_path / "poly.shp"
    gpd.GeoDataFrame(geometry=[box(-45.5, -0.5, -43.5, 1.5)], crs="EPSG:4326").to_file(polygon)
    out = tmp_path / "crop.nc"
    crop_to_country_polygon(Path(registry.entries["cmip6/gfdl_esm4/ssp126/tas"].global_path), polygon, out)
    with xr.open_dataset(out) as ds:
        assert list(ds["lon"].values) == [315.0, 316.0]  # still 0..360, as every country cropped before


# -- ZZC: 65 degrees north ---------------------------------------------------------------------------------------------------------------

A_WGS84, E2 = 6378137.0, 0.00669437999014  # semi-major axis (m) and first eccentricity squared


def _pixel_km2_exact(lat_deg: float, d_deg: float = 0.01) -> float:
    """Meridian radius times the arc of latitude by the prime-vertical radius times cos(lat) times the arc of longitude, in km2 (closed form)."""
    s = np.sin(np.radians(lat_deg))
    m = A_WGS84 * (1 - E2) / (1 - E2 * s * s) ** 1.5
    n = A_WGS84 / np.sqrt(1 - E2 * s * s)
    return float(m * np.radians(d_deg) * n * np.cos(np.radians(lat_deg)) * np.radians(d_deg) / 1e6)


def test_zzc_pixel_area_at_65_north_is_the_hand_value():
    from geofrea.land_eligibility.cells import pixel_row_area_km2

    transform = rasterio.Affine(0.01, 0, 10.00, 0, -0.01, 65.20)
    areas = pixel_row_area_km2(transform, 20)
    # top row, centre at 65.195: 1.1125 km (0.01 degree of latitude) by 0.4693 km (0.01 degree of longitude) = 0.5221 km2; the hand value to 15 digits is
    # the closed form above at that latitude
    assert areas[0] == pytest.approx(0.522148688014309, rel=5e-6)  # the Bowring series of the code is within 1e-6 of the exact ellipsoid
    assert areas[19] == pytest.approx(0.5258743515524604, rel=5e-6)  # row 19, centre 65.005
    for r in (0, 7, 19):
        assert areas[r] == pytest.approx(_pixel_km2_exact(65.195 - 0.01 * r), rel=5e-6)  # the series of the code against the closed form
    assert areas[0] < areas[19]  # a pixel is smaller toward the pole


def test_zzc_decision_cell_area_is_the_sum_of_its_25_pixels_and_the_exact_band_area():
    from geofrea.land_eligibility.cells import pixel_row_area_km2

    transform = rasterio.Affine(0.01, 0, 10.00, 0, -0.01, 65.20)
    cell = float(pixel_row_area_km2(transform, 20)[:5].sum() * 5)  # the top cell row: 5 pixel rows of 5 pixels
    assert cell == pytest.approx(13.063528350511788, rel=5e-6)
    # the exact area of the band between 65.15 and 65.20 over 0.05 degrees (authalic formula): the pixel series is within 1e-6
    e = np.sqrt(E2)

    def q(lat):
        s = np.sin(np.radians(lat))
        return (1 - E2) * (s / (1 - E2 * s * s) - np.log((1 - e * s) / (1 + e * s)) / (2 * e))

    exact = A_WGS84**2 / 2 * np.radians(0.05) * (q(65.20) - q(65.15)) / 1e6
    assert cell == pytest.approx(exact, rel=5e-6)
    assert 13.06 < cell < 13.07  # 5.56 km by 2.35 km


# -- the antimeridian ---------------------------------------------------------------------------------------------------------------------


def test_a_country_that_crosses_180_degrees_is_refused_by_the_guard(tmp_path):
    shapes = {
        "ZZP": [box(179.85, 0, 180.15, 0.2)],  # drawn past 180
        "ZZQ": [box(179.85, 0, 180.0, 0.2), box(-180.0, 0, -179.85, 0.2)],  # cut at the seam
        "ZZR": [box(-179.9, 0, 179.9, 0.2)],  # drawn the long way round
    }
    entries = {}
    for iso, geometry in shapes.items():
        shp = tmp_path / iso / f"gadm41_{iso}_shp" / f"gadm41_{iso}_0.shp"
        shp.parent.mkdir(parents=True)
        gpd.GeoDataFrame(geometry=geometry, crs="EPSG:4326").to_file(shp)
        entries[iso] = CountryEntry(hydrosheds_region=None, grip4_region_dir=None, grip4_region_file=None, gadm_dir=iso)
        with pytest.raises(AntimeridianCountryError, match=iso):
            refuse_antimeridian_countries([iso], entries, tmp_path)
    for iso in ("ZZA", "ZZB", "ZZC"):  # the three miniatures are well inside -180..180
        west, south, east, north = world.BOXES[iso]
        assert polygon_crosses_antimeridian(gpd.GeoDataFrame(geometry=[box(west, south, east, north)], crs="EPSG:4326")) is None
