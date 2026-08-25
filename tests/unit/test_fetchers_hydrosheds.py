"""Unit tests for geofrea.data_acquisition.fetchers.hydrosheds.

Network is fully mocked (monkeypatch on get_with_retry) — no real HTTP
traffic in this file.
"""

from unittest.mock import Mock

import pytest
import requests

from geofrea.data_acquisition.fetchers import hydrosheds


@pytest.mark.unit
def test_fetch_lakes_happy_path_saves_global_file(tmp_path, monkeypatch):
    resp = Mock(content=b"fake-zip-bytes")
    monkeypatch.setattr(hydrosheds, "get_with_retry", Mock(return_value=resp))

    result = hydrosheds.fetch_lakes(tmp_path)

    assert result == tmp_path / "_global" / "raw" / "HydroLAKES_polys_v10_shp.zip"
    assert result.read_bytes() == b"fake-zip-bytes"


@pytest.mark.unit
def test_fetch_lakes_idempotent_skips_network_if_already_present(tmp_path, monkeypatch):
    dest = tmp_path / "_global" / "raw" / "HydroLAKES_polys_v10_shp.zip"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"already here")
    mock_get = Mock()
    monkeypatch.setattr(hydrosheds, "get_with_retry", mock_get)

    result = hydrosheds.fetch_lakes(tmp_path)

    mock_get.assert_not_called()
    assert result == dest


@pytest.mark.unit
def test_fetch_lakes_network_error_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(
        hydrosheds, "get_with_retry", Mock(side_effect=requests.ConnectionError("down"))
    )

    assert hydrosheds.fetch_lakes(tmp_path) is None


@pytest.mark.unit
@pytest.mark.parametrize("country_code,region", [("PRT", "eu"), ("BRA", "sa")])
def test_fetch_rivers_happy_path_uses_correct_region_tile(tmp_path, monkeypatch, country_code, region):
    mock_get = Mock(return_value=Mock(content=b"fake-zip-bytes"))
    monkeypatch.setattr(hydrosheds, "get_with_retry", mock_get)

    result = hydrosheds.fetch_rivers(tmp_path, country_code)

    called_url = mock_get.call_args.args[0]
    assert called_url == f"https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_{region}_shp.zip"
    assert result == tmp_path / country_code / "raw" / f"HydroRIVERS_v10_{region}_shp.zip"
    assert result.read_bytes() == b"fake-zip-bytes"


@pytest.mark.unit
def test_fetch_rivers_idempotent_skips_network_if_already_present(tmp_path, monkeypatch):
    dest = tmp_path / "PRT" / "raw" / "HydroRIVERS_v10_eu_shp.zip"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"already here")
    mock_get = Mock()
    monkeypatch.setattr(hydrosheds, "get_with_retry", mock_get)

    result = hydrosheds.fetch_rivers(tmp_path, "PRT")

    mock_get.assert_not_called()
    assert result == dest


@pytest.mark.unit
def test_fetch_rivers_network_error_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(
        hydrosheds, "get_with_retry", Mock(side_effect=requests.ConnectionError("down"))
    )

    assert hydrosheds.fetch_rivers(tmp_path, "PRT") is None


@pytest.mark.unit
def test_fetch_rivers_unmapped_country_raises_keyerror(tmp_path, monkeypatch):
    # Config gap, not a transient failure — must raise, not degrade to
    # None, so it surfaces loudly instead of silently producing an
    # incomplete acquisition. See module docstring.
    mock_get = Mock()
    monkeypatch.setattr(hydrosheds, "get_with_retry", mock_get)

    with pytest.raises(KeyError):
        hydrosheds.fetch_rivers(tmp_path, "ZZZ")

    mock_get.assert_not_called()
