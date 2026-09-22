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

from geofrea.core import paths
from geofrea.data_acquisition.fetchers import protected_planet


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    # fetch_protected_areas() resolves its destination through
    # paths.fetched_raw("wdpa", country_code), i.e. GEOFREA_DATA_DIR/raw/
    # wdpa/<country_code> (METHODOLOGY A-08) — not the outputs_dir
    # argument these tests still pass (kept for call-site symmetry, see
    # phase.py's lambdas, but unused internally now).
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))


def _page_response(protected_areas: list[dict]) -> Mock:
    resp = Mock()
    resp.json = Mock(return_value={"protected_areas": protected_areas})
    return resp


def _pa(name: str, iucn_category: str, site_id: int, geom_lon: float = 0.0) -> dict:
    # Shape matches a real authenticated v4 response (verified live
    # 2026-09-11, BRA — see protected_planet.py's fetch loop comment):
    # iucn_category is a nested {"id", "name"} object, not a bare
    # string, and there is no top-level "wdpa_id" key at all — "site_id"
    # is the actual WDPA identifier field.
    return {
        "name": name,
        "site_id": site_id,
        "iucn_category": {"id": 1, "name": iucn_category},
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

    assert result == paths.fetched_raw("wdpa", "PRT") / "PRT_protected_areas_wdpa.geojson"
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
def test_fetch_protected_areas_extracts_name_from_nested_iucn_category(tmp_path, monkeypatch):
    # Regression test for the bug found 2026-09-11 against a real
    # authenticated response (see DECISIONS.md same date, "protected_
    # planet API activation"): iucn_category arrives as a nested
    # {"id", "name"} object. Dumping it whole into IUCN_CAT (instead of
    # extracting "name") would have made criteria_functions.py's
    # `cats.isin(strict)` string match never fire for any category.
    monkeypatch.setenv(protected_planet.TOKEN_ENV_VAR, "tok")
    page = _page_response([_pa("Parque Nacional Foo", "II", 2002)])
    monkeypatch.setattr(protected_planet, "get_with_retry", Mock(return_value=page))

    result = protected_planet.fetch_protected_areas(tmp_path, "BRA")

    saved = json.loads(result.read_text(encoding="utf-8"))
    assert saved["features"][0]["properties"]["IUCN_CAT"] == "II"
    assert saved["features"][0]["properties"]["wdpa_id"] == 2002


@pytest.mark.unit
def test_fetch_protected_areas_handles_missing_iucn_category(tmp_path, monkeypatch):
    # A feature with no iucn_category at all (null, per the live API for
    # some records) must not crash — IUCN_CAT ends up None, same as
    # today's "no IUCN column" fallback in compute_protected_areas
    # (criteria_functions.py: feature_scores = _IUCN_FREE_SCORE).
    monkeypatch.setenv(protected_planet.TOKEN_ENV_VAR, "tok")
    no_category = {
        "name": "Unclassified Area",
        "site_id": 3003,
        "iucn_category": None,
        "geojson": {
            "type": "Feature",
            "properties": {},
            "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
        },
    }
    monkeypatch.setattr(
        protected_planet, "get_with_retry", Mock(return_value=_page_response([no_category]))
    )

    result = protected_planet.fetch_protected_areas(tmp_path, "BRA")

    saved = json.loads(result.read_text(encoding="utf-8"))
    assert saved["features"][0]["properties"]["IUCN_CAT"] is None


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
