"""Unit tests for geofrea.data_acquisition.cmip6_registry.

No network. Exercises the JSON-backed registry's resume logic and its
registered/missing distinction directly.
"""

from __future__ import annotations

import pytest

from geofrea.data_acquisition.cmip6_registry import (
    Cmip6NativeGrid,
    Cmip6Registry,
    Cmip6RegistryEntry,
    sha256_file,
)

_GRID = Cmip6NativeGrid(
    lat_resolution_deg=1.0,
    lon_resolution_deg=1.0,
    lat_min=-10.0,
    lat_max=10.0,
    lon_min=0.0,
    lon_max=20.0,
    n_lat=21,
    n_lon=21,
)


def _registered_entry(path) -> Cmip6RegistryEntry:
    return Cmip6RegistryEntry(
        model="gfdl_esm4",
        experiment="historical",
        variable="tas",
        status="registered",
        global_path=str(path),
        source_sha256=sha256_file(path),
        temporal_coverage_start=1995,
        temporal_coverage_end=2014,
        realization="r1i1p1f1",
        native_grid=_GRID,
    )


@pytest.mark.unit
def test_missing_entry_requires_a_reason_and_carries_no_file_fields():
    with pytest.raises(ValueError, match="missing_reason"):
        Cmip6RegistryEntry(model="miroc6", experiment="ssp126", variable="pr", status="missing")


@pytest.mark.unit
def test_missing_entry_cannot_carry_a_global_path():
    with pytest.raises(ValueError, match="must not carry"):
        Cmip6RegistryEntry(
            model="miroc6",
            experiment="ssp126",
            variable="pr",
            status="missing",
            missing_reason="HTTP 404",
            global_path="/some/path.nc",
        )


@pytest.mark.unit
def test_registered_entry_requires_global_path_hash_and_realization():
    with pytest.raises(ValueError, match="requires global_path"):
        Cmip6RegistryEntry(
            model="gfdl_esm4", experiment="historical", variable="tas", status="registered"
        )


@pytest.mark.unit
def test_registry_distinguishes_missing_from_registered(tmp_path):
    data_file = tmp_path / "file.nc"
    data_file.write_bytes(b"fake-netcdf-bytes")

    registry = Cmip6Registry()
    registry.entries["cmip6/gfdl_esm4/historical/tas"] = _registered_entry(data_file)
    registry.entries["cmip6/ipsl_cm6a_lr/ssp585/pr"] = Cmip6RegistryEntry(
        model="ipsl_cm6a_lr",
        experiment="ssp585",
        variable="pr",
        status="missing",
        missing_reason="model not in the approved set",
    )

    assert registry.entries["cmip6/gfdl_esm4/historical/tas"].status == "registered"
    assert registry.entries["cmip6/ipsl_cm6a_lr/ssp585/pr"].status == "missing"
    assert registry.entries["cmip6/ipsl_cm6a_lr/ssp585/pr"].global_path is None


@pytest.mark.unit
def test_is_complete_true_only_when_file_exists_and_hash_still_matches(tmp_path):
    data_file = tmp_path / "file.nc"
    data_file.write_bytes(b"fake-netcdf-bytes")

    registry = Cmip6Registry()
    registry.entries["cmip6/gfdl_esm4/historical/tas"] = _registered_entry(data_file)

    assert registry.is_complete("cmip6/gfdl_esm4/historical/tas") is True

    data_file.write_bytes(b"corrupted-bytes-different-hash")
    assert registry.is_complete("cmip6/gfdl_esm4/historical/tas") is False

    data_file.unlink()
    assert registry.is_complete("cmip6/gfdl_esm4/historical/tas") is False


@pytest.mark.unit
def test_is_complete_false_for_a_missing_entry_and_unknown_key(tmp_path):
    registry = Cmip6Registry()
    registry.entries["cmip6/ipsl_cm6a_lr/ssp585/pr"] = Cmip6RegistryEntry(
        model="ipsl_cm6a_lr",
        experiment="ssp585",
        variable="pr",
        status="missing",
        missing_reason="not attempted",
    )

    assert registry.is_complete("cmip6/ipsl_cm6a_lr/ssp585/pr") is False
    assert registry.is_complete("cmip6/does_not_exist/ssp585/pr") is False


@pytest.mark.unit
def test_registry_round_trips_through_save_and_load(tmp_path):
    data_file = tmp_path / "file.nc"
    data_file.write_bytes(b"fake-netcdf-bytes")

    registry = Cmip6Registry()
    registry.entries["cmip6/gfdl_esm4/historical/tas"] = _registered_entry(data_file)
    registry_path = tmp_path / "registry.json"
    registry.save(registry_path)

    reloaded = Cmip6Registry.load(registry_path)
    assert reloaded.is_complete("cmip6/gfdl_esm4/historical/tas") is True
