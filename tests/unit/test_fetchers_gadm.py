"""Unit tests for geofrea.data_acquisition.fetchers.gadm.

Network is fully mocked (monkeypatch on get_with_retry) — no real HTTP
traffic in this file. Zip content IS real (built with the stdlib
zipfile module) — GADM's real zips are flat (unlike HydroSHEDS', which
nest one directory level deep, see test_fetchers_hydrosheds.py), so
fixture zips here mirror that flat layout: gadm41_<CODE>_0.shp,
_1.shp, _2.shp side by side.
"""

import io
import sys
import types
import zipfile
from unittest.mock import Mock

import geopandas as gpd
import pytest
import requests
from shapely.geometry import box

from geofrea.core import paths
from geofrea.data_acquisition.fetchers import gadm


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    # fetch_borders()/fetch_admin1() resolve their destination through
    # paths.fetched_raw("gadm", country_code), i.e. GEOFREA_DATA_DIR/raw/
    # gadm/<country_code> (METHODOLOGY A-08) — not the outputs_dir
    # argument these tests still pass (kept for call-site symmetry, see
    # phase.py's lambdas, but unused internally now).
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    # Isolate GEOFREA_SHARED_RAW_DIR too, same reasoning as
    # GEOFREA_DATA_DIR above: fetch_borders()/fetch_admin1() now check
    # the local database first (METHODOLOGY M-F1-07). Without this, a
    # session where some other test has already imported main.py (whose
    # module-level load_dotenv(override=False) runs at collection time,
    # before conftest's session fixture sets a default) leaks the real
    # developer .env's GEOFREA_SHARED_RAW_DIR into these tests, making
    # them see Douglas's real local GADM files instead of test fixtures.
    monkeypatch.setenv("GEOFREA_SHARED_RAW_DIR", str(tmp_path / "shared_raw_unused"))


def _make_gadm_zip_bytes(country_code: str, levels: tuple[int, ...] = (0, 1, 2)) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for level in levels:
            zf.writestr(f"gadm41_{country_code}_{level}.shp", f"fake-shp-level-{level}".encode())
            zf.writestr(f"gadm41_{country_code}_{level}.dbf", b"fake-dbf")
    return buf.getvalue()


@pytest.mark.unit
def test_fetch_borders_happy_path_downloads_extracts_and_returns_level0(tmp_path, monkeypatch):
    zip_bytes = _make_gadm_zip_bytes("PRT")
    monkeypatch.setattr(gadm, "get_with_retry", Mock(return_value=Mock(content=zip_bytes)))

    result = gadm.fetch_borders(tmp_path, "PRT")

    expected = paths.fetched_raw("gadm", "PRT") / "gadm41_PRT_shp" / "gadm41_PRT_0.shp"
    assert result == expected
    assert result.read_bytes() == b"fake-shp-level-0"
    # The zip itself is kept on disk — same idempotency convention as hydrosheds.py.
    assert (paths.fetched_raw("gadm", "PRT") / "gadm41_PRT_shp.zip").exists()


@pytest.mark.unit
def test_fetch_admin1_locates_level1_from_the_same_extraction(tmp_path, monkeypatch):
    zip_bytes = _make_gadm_zip_bytes("BRA")
    mock_get = Mock(return_value=Mock(content=zip_bytes))
    monkeypatch.setattr(gadm, "get_with_retry", mock_get)

    borders_result = gadm.fetch_borders(tmp_path, "BRA")
    admin1_result = gadm.fetch_admin1(tmp_path, "BRA")

    assert borders_result.name == "gadm41_BRA_0.shp"
    assert admin1_result.name == "gadm41_BRA_1.shp"
    # admin1 must reuse borders' already-extracted zip, not fetch again.
    mock_get.assert_called_once()


@pytest.mark.unit
def test_fetch_admin1_alone_triggers_its_own_extraction_if_needed(tmp_path, monkeypatch):
    # fetch_admin1() must be self-sufficient — correct even if called
    # without fetch_borders() first in the same run.
    zip_bytes = _make_gadm_zip_bytes("PRT")
    monkeypatch.setattr(gadm, "get_with_retry", Mock(return_value=Mock(content=zip_bytes)))

    result = gadm.fetch_admin1(tmp_path, "PRT")

    assert result == paths.fetched_raw("gadm", "PRT") / "gadm41_PRT_shp" / "gadm41_PRT_1.shp"


@pytest.mark.unit
def test_fetch_admin1_returns_none_when_country_has_no_level1(tmp_path, monkeypatch):
    # A country whose GADM zip only has level 0 (no admin1 data) — no
    # NaturalEarth-equivalent fallback exists for admin1 (see module
    # docstring), so this must return None cleanly, not raise.
    zip_bytes = _make_gadm_zip_bytes("XYZ", levels=(0,))
    monkeypatch.setattr(gadm, "get_with_retry", Mock(return_value=Mock(content=zip_bytes)))

    assert gadm.fetch_admin1(tmp_path, "XYZ") is None


@pytest.mark.unit
def test_fetch_borders_idempotent_skips_everything_if_already_extracted(tmp_path, monkeypatch):
    extract_dir = paths.fetched_raw("gadm", "PRT") / "gadm41_PRT_shp"
    extract_dir.mkdir(parents=True)
    shp_path = extract_dir / "gadm41_PRT_0.shp"
    shp_path.write_bytes(b"already extracted")
    mock_get = Mock()
    monkeypatch.setattr(gadm, "get_with_retry", mock_get)

    result = gadm.fetch_borders(tmp_path, "PRT")

    mock_get.assert_not_called()
    assert result == shp_path


@pytest.mark.unit
def test_fetch_borders_reuses_already_downloaded_zip_without_refetching(tmp_path, monkeypatch):
    dest_dir = paths.fetched_raw("gadm", "PRT")
    dest_dir.mkdir(parents=True)
    (dest_dir / "gadm41_PRT_shp.zip").write_bytes(_make_gadm_zip_bytes("PRT"))
    mock_get = Mock()
    monkeypatch.setattr(gadm, "get_with_retry", mock_get)

    result = gadm.fetch_borders(tmp_path, "PRT")

    mock_get.assert_not_called()
    assert result is not None
    assert result.name == "gadm41_PRT_0.shp"


@pytest.mark.unit
def test_fetch_borders_network_error_falls_back_to_none_when_naturalearth_unavailable(
    tmp_path, monkeypatch
):
    # geodatasets is genuinely not a GeoFREA dependency (see module
    # docstring) — this confirms the real behavior in this environment:
    # GADM failure with no optional fallback package installed yields
    # None, not a crash.
    monkeypatch.setattr(
        gadm, "get_with_retry", Mock(side_effect=requests.ConnectionError("down"))
    )
    monkeypatch.delitem(sys.modules, "geodatasets", raising=False)

    assert gadm.fetch_borders(tmp_path, "PRT") is None


@pytest.mark.unit
def test_fetch_borders_falls_back_to_naturalearth_when_geodatasets_available(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        gadm, "get_with_retry", Mock(side_effect=requests.ConnectionError("down"))
    )

    # Fake a minimal 'geodatasets' module exposing get_path(), pointing
    # at a tiny local GeoJSON shaped like NaturalEarth's real output
    # (an iso_a3 column) — no real geodatasets install needed to
    # exercise this fallback branch.
    world_path = tmp_path / "fake_naturalearth.geojson"
    gpd.GeoDataFrame(
        {"iso_a3": ["PRT", "ESP"]},
        geometry=[box(-9, 39, -8, 40), box(-3, 40, -2, 41)],
        crs="EPSG:4326",
    ).to_file(world_path, driver="GeoJSON")
    fake_geodatasets = types.ModuleType("geodatasets")
    fake_geodatasets.get_path = lambda name: str(world_path)
    monkeypatch.setitem(sys.modules, "geodatasets", fake_geodatasets)

    result = gadm.fetch_borders(tmp_path, "PRT")

    assert result is not None
    assert result.name == "PRT_naturalearth_fallback.shp"
    fallback_gdf = gpd.read_file(result)
    assert len(fallback_gdf) == 1


@pytest.mark.unit
def test_fetch_borders_naturalearth_fallback_returns_none_for_unmatched_country(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        gadm, "get_with_retry", Mock(side_effect=requests.ConnectionError("down"))
    )

    world_path = tmp_path / "fake_naturalearth.geojson"
    gpd.GeoDataFrame(
        {"iso_a3": ["ESP"]}, geometry=[box(-3, 40, -2, 41)], crs="EPSG:4326"
    ).to_file(world_path, driver="GeoJSON")
    fake_geodatasets = types.ModuleType("geodatasets")
    fake_geodatasets.get_path = lambda name: str(world_path)
    monkeypatch.setitem(sys.modules, "geodatasets", fake_geodatasets)

    assert gadm.fetch_borders(tmp_path, "PRT") is None


@pytest.mark.unit
def test_fetch_borders_rejects_zip_slip_and_writes_nothing_outside_target(tmp_path, monkeypatch):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../evil.txt", b"pwned")
    monkeypatch.setattr(gadm, "get_with_retry", Mock(return_value=Mock(content=buf.getvalue())))
    monkeypatch.delitem(sys.modules, "geodatasets", raising=False)

    result = gadm.fetch_borders(tmp_path, "PRT")

    assert result is None
    assert not (paths.fetched_raw("gadm", "PRT") / "evil.txt").exists()
    assert not (tmp_path / "evil.txt").exists()


@pytest.mark.unit
def test_fetch_borders_malformed_zip_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(
        gadm, "get_with_retry", Mock(return_value=Mock(content=b"not-a-zip-at-all"))
    )
    monkeypatch.delitem(sys.modules, "geodatasets", raising=False)

    assert gadm.fetch_borders(tmp_path, "PRT") is None


@pytest.mark.unit
def test_fetch_borders_zip_with_no_shp_returns_none(tmp_path, monkeypatch):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", b"no shapefile in here")
    monkeypatch.setattr(gadm, "get_with_retry", Mock(return_value=Mock(content=buf.getvalue())))
    monkeypatch.delitem(sys.modules, "geodatasets", raising=False)

    assert gadm.fetch_borders(tmp_path, "PRT") is None


@pytest.mark.unit
def test_fetch_borders_falls_back_to_any_shp_when_no_level0_present(tmp_path, monkeypatch):
    # Mirrors legacy's DataManager._find_borders(): prefer the file
    # ending in "_0", but fall back to any .shp found rather than
    # nothing, matching an unusual-but-real GADM archive layout.
    zip_bytes = _make_gadm_zip_bytes("PRT", levels=(1, 2))
    monkeypatch.setattr(gadm, "get_with_retry", Mock(return_value=Mock(content=zip_bytes)))

    result = gadm.fetch_borders(tmp_path, "PRT")

    assert result is not None
    assert result.name in ("gadm41_PRT_1.shp", "gadm41_PRT_2.shp")


@pytest.mark.unit
def test_fetch_admin1_returns_none_when_gadm_itself_fails(tmp_path, monkeypatch):
    # admin1 has no NaturalEarth-equivalent fallback (see module
    # docstring) — GADM failing entirely must yield None directly.
    monkeypatch.setattr(
        gadm, "get_with_retry", Mock(side_effect=requests.ConnectionError("down"))
    )

    assert gadm.fetch_admin1(tmp_path, "PRT") is None


@pytest.mark.unit
def test_fetch_borders_naturalearth_fallback_reports_load_failure_as_none(tmp_path, monkeypatch):
    monkeypatch.setattr(
        gadm, "get_with_retry", Mock(side_effect=requests.ConnectionError("down"))
    )
    fake_geodatasets = types.ModuleType("geodatasets")
    fake_geodatasets.get_path = lambda name: str(tmp_path / "does_not_exist.geojson")
    monkeypatch.setitem(sys.modules, "geodatasets", fake_geodatasets)

    assert gadm.fetch_borders(tmp_path, "PRT") is None


# ─── local database, METHODOLOGY M-F1-07 ──────────────────────────────


def _write_local_gadm(shared_raw_dir, gadm_subdir, country_code, content=b"real-local-shp"):
    country_dir = shared_raw_dir / "countries_borders" / gadm_subdir
    country_dir.mkdir(parents=True)
    (country_dir / f"gadm41_{country_code}_0.shp").write_bytes(content)
    return country_dir, content


@pytest.mark.unit
def test_fetch_borders_local_database_hit_performs_no_network_call(tmp_path, monkeypatch):
    shared_raw_dir = tmp_path / "shared_raw"
    country_dir, content = _write_local_gadm(shared_raw_dir, "Portugal", "PRT")
    monkeypatch.setenv("GEOFREA_SHARED_RAW_DIR", str(shared_raw_dir))
    monkeypatch.setattr(
        gadm,
        "_load_countries_config",
        lambda: {
            "PRT": {
                "gadm_dir": "Portugal",
                "gadm_level0_sha256": gadm._sha256_file(country_dir / "gadm41_PRT_0.shp"),
            }
        },
    )
    mock_get = Mock()
    monkeypatch.setattr(gadm, "get_with_retry", mock_get)

    result = gadm.fetch_borders(tmp_path, "PRT")

    mock_get.assert_not_called()
    assert result == country_dir / "gadm41_PRT_0.shp"
    assert result.read_bytes() == content


@pytest.mark.unit
def test_fetch_borders_local_database_checksum_mismatch_raises(tmp_path, monkeypatch):
    shared_raw_dir = tmp_path / "shared_raw"
    _write_local_gadm(shared_raw_dir, "Portugal", "PRT")
    monkeypatch.setenv("GEOFREA_SHARED_RAW_DIR", str(shared_raw_dir))
    monkeypatch.setattr(
        gadm,
        "_load_countries_config",
        lambda: {"PRT": {"gadm_dir": "Portugal", "gadm_level0_sha256": "0" * 64}},
    )
    mock_get = Mock()
    monkeypatch.setattr(gadm, "get_with_retry", mock_get)

    with pytest.raises(gadm.GadmChecksumMismatchError):
        gadm.fetch_borders(tmp_path, "PRT")

    mock_get.assert_not_called()


@pytest.mark.unit
def test_fetch_borders_local_database_absent_falls_back_and_fetches(tmp_path, monkeypatch):
    # No GEOFREA_SHARED_RAW_DIR set at all — matches the module fixture
    # default. The local-database check must be a clean skip, not a
    # crash, and the layer's provenance ("fetched", per phase.py's
    # _LAYER_REGISTRY) is unaffected by which internal path resolved it.
    zip_bytes = _make_gadm_zip_bytes("PRT")
    mock_get = Mock(return_value=Mock(content=zip_bytes))
    monkeypatch.setattr(gadm, "get_with_retry", mock_get)

    result = gadm.fetch_borders(tmp_path, "PRT")

    mock_get.assert_called_once()
    assert result is not None
    assert result.name == "gadm41_PRT_0.shp"
