"""Unit tests for geofrea.data_acquisition.fetchers.protected_planet.

Network is fully mocked (monkeypatch on get_with_retry) — no real HTTP
traffic in this file. This fetcher is implemented but NOT wired into
run_acquisition_phase() (see phase.py's module docstring) — these
tests exercise the module directly.
"""

import json
from unittest.mock import Mock

import pytest
import requests

from geofrea.data_acquisition.fetchers import protected_planet


def _page_response(protected_areas: list[dict]) -> Mock:
    resp = Mock()
    resp.json = Mock(return_value={"protected_areas": protected_areas})
    return resp


def _pa(name: str, iucn_category: str, wdpa_id: int, geom_lon: float = 0.0) -> dict:
    return {
        "name": name,
        "wdpa_id": wdpa_id,
        "iucn_category": iucn_category,
        "geojson": {
            "type": "Feature",
            "properties": {"designation": "National Park"},
            "geometry": {"type": "Point", "coordinates": [geom_lon, 0.0]},
        },
    }


@pytest.mark.unit
def test_fetch_protected_areas_raises_clear_error_when_token_missing(tmp_path, monkeypatch):
    monkeypatch.delenv(protected_planet.TOKEN_ENV_VAR, raising=False)

    with pytest.raises(protected_planet.ProtectedPlanetTokenMissingError) as exc_info:
        protected_planet.fetch_protected_areas(tmp_path, "PRT")

    message = str(exc_info.value)
    assert protected_planet.TOKEN_ENV_VAR in message
    assert protected_planet.REGISTRATION_URL in message
    assert "50" in message  # pagination reminder (max 50/page)
    assert "country" in message.lower() or "per country" in message.lower() or "bulk" in message.lower()


@pytest.mark.unit
def test_fetch_protected_areas_accepts_explicit_token_without_env_var(tmp_path, monkeypatch):
    monkeypatch.delenv(protected_planet.TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(
        protected_planet, "get_with_retry", Mock(return_value=_page_response([]))
    )

    result = protected_planet.fetch_protected_areas(tmp_path, "PRT", api_token="explicit-token")

    assert result is not None


@pytest.mark.unit
def test_fetch_protected_areas_happy_path_single_page(tmp_path, monkeypatch):
    monkeypatch.setenv(protected_planet.TOKEN_ENV_VAR, "tok")
    page = _page_response([_pa("Serra da Estrela", "II", 1001)])
    monkeypatch.setattr(protected_planet, "get_with_retry", Mock(return_value=page))

    result = protected_planet.fetch_protected_areas(tmp_path, "PRT")

    assert result == tmp_path / "PRT" / "raw" / "PRT_protected_areas_wdpa.geojson"
    saved = json.loads(result.read_text(encoding="utf-8"))
    assert saved["type"] == "FeatureCollection"
    assert len(saved["features"]) == 1
    assert saved["features"][0]["properties"]["IUCN_CAT"] == "II"
    assert saved["features"][0]["properties"]["wdpa_id"] == 1001


@pytest.mark.unit
def test_fetch_protected_areas_paginates_until_short_page(tmp_path, monkeypatch):
    monkeypatch.setenv(protected_planet.TOKEN_ENV_VAR, "tok")
    full_page = _page_response([_pa(f"PA{i}", "II", i) for i in range(protected_planet._PER_PAGE)])
    short_page = _page_response([_pa("last", "IV", 999)])
    mock_get = Mock(side_effect=[full_page, short_page])
    monkeypatch.setattr(protected_planet, "get_with_retry", mock_get)

    result = protected_planet.fetch_protected_areas(tmp_path, "PRT")

    assert mock_get.call_count == 2
    saved = json.loads(result.read_text(encoding="utf-8"))
    assert len(saved["features"]) == protected_planet._PER_PAGE + 1


@pytest.mark.unit
def test_fetch_protected_areas_empty_result_saves_empty_feature_collection(tmp_path, monkeypatch):
    monkeypatch.setenv(protected_planet.TOKEN_ENV_VAR, "tok")
    monkeypatch.setattr(protected_planet, "get_with_retry", Mock(return_value=_page_response([])))

    result = protected_planet.fetch_protected_areas(tmp_path, "PRT")

    saved = json.loads(result.read_text(encoding="utf-8"))
    assert saved == {"type": "FeatureCollection", "features": []}


@pytest.mark.unit
def test_fetch_protected_areas_skips_features_with_no_geometry(tmp_path, monkeypatch):
    monkeypatch.setenv(protected_planet.TOKEN_ENV_VAR, "tok")
    malformed = {"name": "no geom", "wdpa_id": 1, "iucn_category": "II", "geojson": None}
    monkeypatch.setattr(
        protected_planet, "get_with_retry", Mock(return_value=_page_response([malformed]))
    )

    result = protected_planet.fetch_protected_areas(tmp_path, "PRT")

    saved = json.loads(result.read_text(encoding="utf-8"))
    assert saved["features"] == []


@pytest.mark.unit
def test_fetch_protected_areas_network_error_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv(protected_planet.TOKEN_ENV_VAR, "tok")
    monkeypatch.setattr(
        protected_planet, "get_with_retry", Mock(side_effect=requests.ConnectionError("down"))
    )

    assert protected_planet.fetch_protected_areas(tmp_path, "PRT") is None


@pytest.mark.unit
def test_fetch_protected_areas_malformed_json_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv(protected_planet.TOKEN_ENV_VAR, "tok")
    bad_resp = Mock()
    bad_resp.json = Mock(side_effect=ValueError("not json"))
    monkeypatch.setattr(protected_planet, "get_with_retry", Mock(return_value=bad_resp))

    assert protected_planet.fetch_protected_areas(tmp_path, "PRT") is None
