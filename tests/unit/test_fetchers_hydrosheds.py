"""Unit tests for geofrea.data_acquisition.fetchers.hydrosheds.

Network is fully mocked (monkeypatch on get_with_retry) — no real HTTP
traffic in this file. Zip content IS real (built with the stdlib
zipfile module, not mocked) — the whole point of these fetchers is now
extraction (see hydrosheds.py's module docstring, "Zip internal
layout"), so a Mock() standing in for a zip would test nothing real
about that behavior. Fixture zips mirror the real HydroSHEDS layout
confirmed live 2026-08-25: shapefile nested one directory level under a
name matching the zip's own stem, plus an unrelated top-level file.
"""

import zipfile
from unittest.mock import Mock

import pytest
import requests

from geofrea.core import paths
from geofrea.data_acquisition.fetchers import hydrosheds


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    # fetch_lakes()/fetch_rivers() resolve their destination through
    # paths.fetched_raw("hydrosheds", scope), i.e. GEOFREA_DATA_DIR/raw/
    # hydrosheds/<scope> (METHODOLOGY A-08) — not the outputs_dir
    # argument these tests still pass (kept for call-site symmetry, see
    # phase.py's lambdas, but unused internally now).
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))


def _make_zip_bytes(inner_dir: str, shp_basename: str) -> bytes:
    """Build a minimal zip mirroring HydroSHEDS' real nested layout.

    Real HydroSHEDS zips carry a full shapefile (.shp/.shx/.dbf/...);
    only .shp is faked here — _fetch_and_extract_shapefile() only ever
    globs for "*.shp", so the sidecar files are irrelevant to what
    these tests verify.
    """
    import io

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"{inner_dir}/{shp_basename}.shp", b"fake-shp-bytes")
        zf.writestr("SomeTechDoc.pdf", b"fake-pdf-bytes")
    return buf.getvalue()


@pytest.mark.unit
def test_fetch_lakes_happy_path_extracts_and_returns_shp_path(tmp_path, monkeypatch):
    zip_bytes = _make_zip_bytes("HydroLAKES_polys_v10_shp", "HydroLAKES_polys_v10")
    monkeypatch.setattr(
        hydrosheds, "get_with_retry", Mock(return_value=Mock(content=zip_bytes))
    )

    result = hydrosheds.fetch_lakes(tmp_path)

    expected = (
        paths.fetched_raw("hydrosheds", "_global")
        / "HydroLAKES_polys_v10_shp"
        / "HydroLAKES_polys_v10_shp"
        / "HydroLAKES_polys_v10.shp"
    )
    assert result == expected
    assert result.read_bytes() == b"fake-shp-bytes"
    # The downloaded zip itself is still kept on disk (not deleted after
    # extraction) — cheap idempotency for a re-extract without re-fetch.
    assert (paths.fetched_raw("hydrosheds", "_global") / "HydroLAKES_polys_v10_shp.zip").exists()


@pytest.mark.unit
def test_fetch_lakes_idempotent_skips_everything_if_already_extracted(tmp_path, monkeypatch):
    extract_dir = (
        paths.fetched_raw("hydrosheds", "_global")
        / "HydroLAKES_polys_v10_shp"
        / "HydroLAKES_polys_v10_shp"
    )
    extract_dir.mkdir(parents=True)
    shp_path = extract_dir / "HydroLAKES_polys_v10.shp"
    shp_path.write_bytes(b"already extracted")
    mock_get = Mock()
    monkeypatch.setattr(hydrosheds, "get_with_retry", mock_get)

    result = hydrosheds.fetch_lakes(tmp_path)

    mock_get.assert_not_called()
    assert result == shp_path


@pytest.mark.unit
def test_fetch_lakes_reuses_already_downloaded_zip_without_refetching(tmp_path, monkeypatch):
    # Simulates a prior run that downloaded successfully but crashed
    # before extraction — the zip is on disk, nothing is extracted yet.
    dest_dir = paths.fetched_raw("hydrosheds", "_global")
    dest_dir.mkdir(parents=True)
    zip_bytes = _make_zip_bytes("HydroLAKES_polys_v10_shp", "HydroLAKES_polys_v10")
    (dest_dir / "HydroLAKES_polys_v10_shp.zip").write_bytes(zip_bytes)
    mock_get = Mock()
    monkeypatch.setattr(hydrosheds, "get_with_retry", mock_get)

    result = hydrosheds.fetch_lakes(tmp_path)

    mock_get.assert_not_called()
    assert result is not None
    assert result.name == "HydroLAKES_polys_v10.shp"


@pytest.mark.unit
def test_fetch_lakes_network_error_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(
        hydrosheds, "get_with_retry", Mock(side_effect=requests.ConnectionError("down"))
    )

    assert hydrosheds.fetch_lakes(tmp_path) is None


@pytest.mark.unit
def test_fetch_lakes_malformed_zip_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(
        hydrosheds, "get_with_retry", Mock(return_value=Mock(content=b"not-a-zip-at-all"))
    )

    assert hydrosheds.fetch_lakes(tmp_path) is None


@pytest.mark.unit
def test_fetch_lakes_zip_with_no_shp_returns_none(tmp_path, monkeypatch):
    import io

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("SomeTechDoc.pdf", b"fake-pdf-bytes")
    monkeypatch.setattr(
        hydrosheds, "get_with_retry", Mock(return_value=Mock(content=buf.getvalue()))
    )

    assert hydrosheds.fetch_lakes(tmp_path) is None


@pytest.mark.unit
@pytest.mark.parametrize("country_code,region", [("PRT", "eu"), ("BRA", "sa")])
def test_fetch_rivers_happy_path_uses_correct_region_tile(
    tmp_path, monkeypatch, country_code, region
):
    zip_bytes = _make_zip_bytes(f"HydroRIVERS_v10_{region}_shp", f"HydroRIVERS_v10_{region}")
    mock_get = Mock(return_value=Mock(content=zip_bytes))
    monkeypatch.setattr(hydrosheds, "get_with_retry", mock_get)

    result = hydrosheds.fetch_rivers(tmp_path, country_code)

    called_url = mock_get.call_args.args[0]
    assert (
        called_url
        == f"https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_{region}_shp.zip"
    )
    expected = (
        paths.fetched_raw("hydrosheds", country_code)
        / f"HydroRIVERS_v10_{region}_shp"
        / f"HydroRIVERS_v10_{region}_shp"
        / f"HydroRIVERS_v10_{region}.shp"
    )
    assert result == expected


@pytest.mark.unit
def test_fetch_rivers_idempotent_skips_everything_if_already_extracted(tmp_path, monkeypatch):
    extract_dir = (
        paths.fetched_raw("hydrosheds", "PRT")
        / "HydroRIVERS_v10_eu_shp"
        / "HydroRIVERS_v10_eu_shp"
    )
    extract_dir.mkdir(parents=True)
    shp_path = extract_dir / "HydroRIVERS_v10_eu.shp"
    shp_path.write_bytes(b"already extracted")
    mock_get = Mock()
    monkeypatch.setattr(hydrosheds, "get_with_retry", mock_get)

    result = hydrosheds.fetch_rivers(tmp_path, "PRT")

    mock_get.assert_not_called()
    assert result == shp_path


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
