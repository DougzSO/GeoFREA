"""Unit tests for geofrea.data_acquisition.fetchers.power_plants.

Network is fully mocked (monkeypatch on get_with_retry) — no real HTTP
traffic in this file.
"""

from unittest.mock import Mock

import pytest
import requests

from geofrea.data_acquisition.fetchers import power_plants


@pytest.mark.unit
def test_fetch_power_plants_happy_path_saves_file(tmp_path, monkeypatch):
    resp = Mock(content=b"fuel,capacity_mw\nHydro,10.0\n")
    monkeypatch.setattr(power_plants, "get_with_retry", Mock(return_value=resp))

    result = power_plants.fetch_power_plants(tmp_path)

    assert result == tmp_path / "_global" / "raw" / "global_power_plant_database.csv"
    assert result.read_bytes() == b"fuel,capacity_mw\nHydro,10.0\n"


@pytest.mark.unit
def test_fetch_power_plants_uses_pinned_commit_url(tmp_path, monkeypatch):
    mock_get = Mock(return_value=Mock(content=b"x"))
    monkeypatch.setattr(power_plants, "get_with_retry", mock_get)

    power_plants.fetch_power_plants(tmp_path)

    called_url = mock_get.call_args.args[0]
    assert power_plants.PINNED_COMMIT_SHA in called_url
    assert "master" not in called_url


@pytest.mark.unit
def test_fetch_power_plants_idempotent_skips_network_if_already_present(tmp_path, monkeypatch):
    dest = tmp_path / "_global" / "raw" / "global_power_plant_database.csv"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"already here")

    mock_get = Mock()
    monkeypatch.setattr(power_plants, "get_with_retry", mock_get)

    result = power_plants.fetch_power_plants(tmp_path)

    mock_get.assert_not_called()
    assert result == dest
    assert result.read_bytes() == b"already here"


@pytest.mark.unit
def test_fetch_power_plants_network_error_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(
        power_plants, "get_with_retry", Mock(side_effect=requests.ConnectionError("down"))
    )

    result = power_plants.fetch_power_plants(tmp_path)

    assert result is None
    assert not (tmp_path / "_global" / "raw" / "global_power_plant_database.csv").exists()


@pytest.mark.unit
def test_fetch_power_plants_timeout_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(power_plants, "get_with_retry", Mock(side_effect=requests.Timeout("slow")))

    result = power_plants.fetch_power_plants(tmp_path)

    assert result is None
