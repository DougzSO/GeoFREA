"""Unit tests for geofrea.data_acquisition.fetchers.wind.

Network is fully mocked (monkeypatch on get_with_retry) — no real HTTP
traffic in this file.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from geofrea.core import paths
from geofrea.data_acquisition.fetchers import wind


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    # fetch_wind() resolves its destination through
    # paths.fetched_raw("gwa", country_code), i.e. GEOFREA_DATA_DIR/raw/
    # gwa/<country_code> (METHODOLOGY A-08) — not the outputs_dir
    # argument these tests still pass (kept for call-site symmetry, see
    # phase.py's lambdas, but unused internally now).
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))


@pytest.mark.unit
def test_fetch_wind_happy_path_saves_file(tmp_path, monkeypatch):
    resp = Mock(content=b"\x00fake-tiff-bytes")
    monkeypatch.setattr(wind, "get_with_retry", Mock(return_value=resp))

    result = wind.fetch_wind(tmp_path, "PRT")

    assert result == paths.fetched_raw("gwa", "PRT") / "PRT_wind_speed_100m.tif"
    assert result.read_bytes() == b"\x00fake-tiff-bytes"


@pytest.mark.unit
def test_fetch_wind_url_uses_country_code_and_height(tmp_path, monkeypatch):
    mock_get = Mock(return_value=Mock(content=b"x"))
    monkeypatch.setattr(wind, "get_with_retry", mock_get)

    wind.fetch_wind(tmp_path, "BRA", height_m=200)

    called_url = mock_get.call_args.args[0]
    assert called_url == "https://globalwindatlas.info/api/gis/country/BRA/wind-speed/200"


@pytest.mark.unit
def test_fetch_wind_idempotent_skips_network_if_already_present(tmp_path, monkeypatch):
    dest = paths.fetched_raw("gwa", "BRA") / "BRA_wind_speed_100m.tif"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"already here")

    mock_get = Mock()
    monkeypatch.setattr(wind, "get_with_retry", mock_get)

    result = wind.fetch_wind(tmp_path, "BRA")

    mock_get.assert_not_called()
    assert result == dest


@pytest.mark.unit
def test_fetch_wind_network_error_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(wind, "get_with_retry", Mock(side_effect=requests.ConnectionError("down")))

    result = wind.fetch_wind(tmp_path, "PRT")

    assert result is None


@pytest.mark.unit
def test_fetch_wind_http_error_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(wind, "get_with_retry", Mock(side_effect=requests.HTTPError("404")))

    result = wind.fetch_wind(tmp_path, "PRT")

    assert result is None


@pytest.mark.unit
def test_fetch_gwa_product_url_uses_product_slug_and_height(tmp_path, monkeypatch):
    mock_get = Mock(return_value=Mock(content=b"x"))
    monkeypatch.setattr(wind, "get_with_retry", mock_get)

    wind.fetch_gwa_product(tmp_path, "BRA", "air_density", 200)

    called_url = mock_get.call_args.args[0]
    assert called_url == "https://globalwindatlas.info/api/gis/country/BRA/air-density/200"


@pytest.mark.unit
def test_fetch_gwa_product_existence_confirmed_on_final_response_after_redirect(
    tmp_path, monkeypatch
):
    # No real network call: get_with_retry() (core/http_retry.py) already
    # follows any redirect internally and calls raise_for_status() against
    # the FINAL response before returning — from fetch_gwa_product()'s
    # point of view, a successful mocked return value here IS "the final
    # response after the redirect", exercising exactly what it trusts
    # (never the redirect itself, which it never sees).
    final_response = Mock(content=b"\x00real-tiff-bytes-after-redirect", status_code=200)
    monkeypatch.setattr(wind, "get_with_retry", Mock(return_value=final_response))

    result = wind.fetch_gwa_product(tmp_path, "PRT", "weibull_a", 150)

    assert result == paths.fetched_raw("gwa", "PRT") / "PRT_weibull_a_150m.tif"
    assert result.read_bytes() == b"\x00real-tiff-bytes-after-redirect"


@pytest.mark.unit
def test_fetch_gwa_product_missing_product_raises_instead_of_returning_none(tmp_path, monkeypatch):
    # M-F1-03 / A-09: a product that does not exist fails loud, never
    # registered as silently absent. Mirrors the real failure observed
    # live (F1-2 probe): the API redirects to a CDN URL that then
    # answers 403 "AccessDenied" — get_with_retry()'s raise_for_status()
    # against that final response raises requests.HTTPError, which this
    # wraps into a named, product/height-identifying error.
    monkeypatch.setattr(
        wind, "get_with_retry", Mock(side_effect=requests.HTTPError("403 Client Error"))
    )

    with pytest.raises(wind.GwaProductNotFoundError):
        wind.fetch_gwa_product(tmp_path, "PRT", "air_density", 999)


@pytest.mark.unit
def test_fetch_gwa_product_idempotent_skips_network_if_already_present(tmp_path, monkeypatch):
    dest = paths.fetched_raw("gwa", "BRA") / "BRA_weibull_k_100m.tif"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"already here")

    mock_get = Mock()
    monkeypatch.setattr(wind, "get_with_retry", mock_get)

    result = wind.fetch_gwa_product(tmp_path, "BRA", "weibull_k", 100)

    mock_get.assert_not_called()
    assert result == dest


# ─── coverage of the country mask and completion from the neighbours (OQ-062, COMMAND 58) ────────────────────────────────────────────────────

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Polygon, box

RES = 0.01


def _write_gwa(path, lon0, lat1, cols, rows, value, nodata=-999.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.full((rows, cols), value, dtype="float32")
    with rasterio.open(
        path, "w", driver="GTiff", height=rows, width=cols, count=1, dtype="float32", crs="EPSG:4326",
        transform=from_origin(lon0, lat1, RES, RES), nodata=nodata,
    ) as dst:  # fmt: skip
        dst.write(data, 1)
    return path


def _mask(tmp_path, polygon=None):
    gdf = gpd.GeoDataFrame(
        {"n": [1]}, geometry=[polygon or box(0.0, 0.0, 2.0, 1.0)], crs="EPSG:4326"
    )
    path = tmp_path / "mask.gpkg"
    gdf.to_file(path, driver="GPKG")
    return gdf, path


@pytest.fixture
def setup(tmp_path, monkeypatch):
    """A country file over lon 0-1.5 (value 5), a neighbour file over lon 1-2 (value 7), a mask over lon 0-2, lat 0-1."""
    from geofrea.data_acquisition.fetchers import gadm

    mask, mask_path = _mask(tmp_path)
    monkeypatch.setattr(gadm, "fetch_borders", lambda outputs_dir, iso: mask_path)
    monkeypatch.setattr(wind, "neighbours_of", lambda iso: ["NEI"])
    own = _write_gwa(
        paths.fetched_raw("gwa", "CTY") / "CTY_wind_speed_100m.tif", 0.0, 1.0, 150, 100, 5.0
    )
    nei = _write_gwa(
        paths.fetched_raw("gwa", "NEI") / "NEI_wind_speed_100m.tif", 1.0, 1.0, 100, 100, 7.0
    )
    return mask, own, nei


@pytest.mark.unit
def test_mask_coverage_is_the_share_of_mask_pixels_with_a_valid_value(setup):
    mask, own, nei = setup
    assert wind.mask_coverage_pct(own, mask) == pytest.approx(75.0, abs=1.0)
    assert wind.mask_coverage_pct(nei, mask) == pytest.approx(50.0, abs=1.0)


@pytest.mark.unit
def test_a_file_that_covers_the_mask_is_returned_as_it_is_and_no_neighbour_is_fetched(
    setup, tmp_path, monkeypatch
):
    _gdf, _own, _nei = setup
    full = _write_gwa(
        paths.fetched_raw("gwa", "CTY") / "CTY_air_density_100m.tif", -0.1, 1.1, 230, 120, 1.2
    )
    fetch = Mock()
    monkeypatch.setattr(wind, "fetch_gwa_product", fetch)
    assert wind.complete_gwa_to_mask(tmp_path, "CTY", "air_density", 100, full) == full
    fetch.assert_not_called()


@pytest.mark.unit
def test_a_file_that_misses_the_mask_is_completed_from_the_neighbour_and_cut_to_the_mask(
    tmp_path, monkeypatch, setup
):
    _gdf, own, _nei = setup
    # a mask with a diagonal edge: the upper right triangle of the rectangle is outside
    triangle = Polygon([(0, 0), (2, 0), (2, 0.5), (0, 1)])
    mask2, mask_path = _mask(tmp_path, triangle)
    from geofrea.data_acquisition.fetchers import gadm

    monkeypatch.setattr(gadm, "fetch_borders", lambda outputs_dir, iso: mask_path)
    result = wind.complete_gwa_to_mask(tmp_path, "CTY", "wind_speed", 100, own)
    assert result == paths.fetched_raw("gwa", "CTY") / "CTY_wind_speed_100m_mask.tif"
    assert own.exists() and own.stat().st_size > 0  # the country file is kept
    assert wind.mask_coverage_pct(result, mask2) == pytest.approx(100.0, abs=0.5)
    with rasterio.open(result) as src:
        data = src.read(1)
        assert src.nodata == -999.0 and src.crs.to_string() == "EPSG:4326"
        x = lambda lon: round((lon - src.transform.c) / RES)
        y = lambda lat: round((src.transform.f - lat) / RES)
        assert data[y(0.2), x(0.2)] == 5.0  # the country file where it has a value
        assert data[y(0.2), x(1.2)] == 5.0  # and in the overlap
        assert data[y(0.2), x(1.8)] == 7.0  # the neighbour where the country file has none
        assert data[y(0.95), x(1.9)] == -999.0  # outside the mask: no data
        assert src.transform.c == pytest.approx(0.0) and abs(src.transform.a) == pytest.approx(RES)
    again = wind.complete_gwa_to_mask(tmp_path, "CTY", "wind_speed", 100, own)
    assert again == result


@pytest.mark.unit
def test_the_derived_file_is_reused_while_its_sources_are_unchanged_and_rebuilt_when_one_changes(
    setup, tmp_path
):
    _mask, own, nei = setup
    result = wind.complete_gwa_to_mask(tmp_path, "CTY", "wind_speed", 100, own)
    first = result.stat().st_mtime_ns
    assert wind.complete_gwa_to_mask(tmp_path, "CTY", "wind_speed", 100, own) == result
    assert result.stat().st_mtime_ns == first
    _write_gwa(nei, 1.0, 1.0, 100, 100, 9.0)
    wind.complete_gwa_to_mask(tmp_path, "CTY", "wind_speed", 100, own)
    with rasterio.open(result) as src:
        assert src.read(1)[50, 190] == 9.0


@pytest.mark.unit
def test_a_neighbour_off_the_lattice_is_skipped_and_the_country_file_is_returned(
    setup, tmp_path, monkeypatch
):
    _mask, own, nei = setup
    off = _write_gwa(
        paths.fetched_raw("gwa", "NEI") / "NEI_wind_speed_100m.tif", 1.003, 1.0, 100, 100, 7.0
    )
    assert off == nei
    assert wind.complete_gwa_to_mask(tmp_path, "CTY", "wind_speed", 100, own) == own


@pytest.mark.unit
def test_without_declared_neighbours_the_country_file_is_returned_and_the_gap_is_logged(
    setup, tmp_path, monkeypatch, caplog
):
    _gdf, own, _nei = setup
    monkeypatch.setattr(wind, "neighbours_of", lambda iso: [])
    with caplog.at_level("WARNING"):
        assert wind.complete_gwa_to_mask(tmp_path, "CTY", "wind_speed", 100, own) == own
    assert "declares no `gwa_neighbours`" in caplog.text


@pytest.mark.unit
def test_a_neighbour_file_that_cannot_be_fetched_is_logged_and_the_country_file_is_returned(
    setup, tmp_path, monkeypatch, caplog
):
    _mask, own, nei = setup
    nei.unlink()
    monkeypatch.setattr(
        wind,
        "fetch_gwa_product",
        Mock(
            side_effect=wind.GwaProductNotFoundError("NEI", "wind_speed", 100, RuntimeError("403"))
        ),
    )
    with caplog.at_level("WARNING"):
        assert wind.complete_gwa_to_mask(tmp_path, "CTY", "wind_speed", 100, own) == own
    assert "neighbour NEI" in caplog.text


@pytest.mark.unit
def test_nothing_to_complete_without_a_country_file(tmp_path):
    assert wind.complete_gwa_to_mask(tmp_path, "CTY", "wind_speed", 100, None) is None


@pytest.mark.unit
def test_the_registry_handlers_complete_every_wind_layer_to_the_mask(monkeypatch, tmp_path):
    from geofrea.data_acquisition import phase

    calls = []
    monkeypatch.setattr(phase, "fetch_wind", lambda outputs_dir, iso: Path("own_wind"))
    monkeypatch.setattr(
        phase, "fetch_gwa_product", lambda outputs_dir, iso, p, h: Path(f"own_{p}_{h}")
    )
    monkeypatch.setattr(
        phase,
        "complete_gwa_to_mask",
        lambda outputs_dir, iso, p, h, own: calls.append((p, h, own)) or own,
    )
    ctx = Mock(outputs_dir=tmp_path, country_code="CTY")
    assert phase._FETCHED_LAYER_HANDLERS["wind"](ctx) == Path("own_wind")
    assert phase._FETCHED_LAYER_HANDLERS["weibull_k_150m"](ctx) == Path("own_weibull_k_150")
    assert calls == [
        ("wind_speed", 100, Path("own_wind")),
        ("weibull_k", 150, Path("own_weibull_k_150")),
    ]
