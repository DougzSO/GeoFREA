"""Unit tests for geofrea.data_acquisition.fetchers.wind.

Network is fully mocked (monkeypatch on get_with_retry) — no real HTTP
traffic in this file.
"""

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
def test_fetch_gwa_product_missing_product_raises_instead_of_returning_none(
    tmp_path, monkeypatch
):
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
