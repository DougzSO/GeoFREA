"""The external_inputs check: every CMIP6, ISIMIP3b and ERA5 file F4 needs is registered, present and intact (A-09)."""

from __future__ import annotations

import pytest
import yaml

from geofrea.climate_forcing.external_inputs import ExternalInputError, check_external_inputs
from geofrea.data_acquisition.cmip6_registry import Cmip6Registry, Cmip6RegistryEntry, sha256_file
from geofrea.data_acquisition.era5_registry import Era5Registry, Era5RegistryEntry
from geofrea.data_acquisition.isimip3b_registry import Isimip3bRegistry, Isimip3bRegistryEntry

ISO = "ZZZ"


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def experiments(tmp_path):
    path = tmp_path / "experiments.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "gcm_ensemble": {
                    "gcms": [
                        {"name": "GFDL-ESM4", "cds_name": "gfdl_esm4", "hazard_channel": True}
                    ],
                    "ssps": ["SSP3-7.0"],
                    "windows": ["2041-2070"],
                    "hazard_windows_available": ["2041-2070"],
                }
            }
        ),
        encoding="utf-8",
    )
    return path


def _file(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _build(data, *, skip_cmip6=None, corrupt_era5=False, skip_isimip=False):
    raw = data / "raw"
    cmip6 = Cmip6Registry()
    for experiment in ("historical", "ssp370"):
        for variable in ("rsds", "sfcWind", "tas"):
            if skip_cmip6 == (experiment, variable):
                continue
            p = _file(
                raw / "cmip6" / "_global" / f"gfdl_{experiment}_{variable}.nc",
                f"{experiment}{variable}",
            )
            cmip6.entries[f"cmip6/gfdl_esm4/{experiment}/{variable}"] = Cmip6RegistryEntry(
                model="gfdl_esm4",
                experiment=experiment,
                variable=variable,
                status="registered",
                global_path=str(p),
                source_sha256=sha256_file(p),
                realization="r1i1p1f1",
            )
    cmip6.save(raw / "cmip6" / "_global" / "cmip6_registry.json")

    isimip = Isimip3bRegistry()
    if not skip_isimip:
        for scenario in ("historical", "ssp370"):
            for variable in ("tasmax", "pr"):
                p = _file(
                    raw / "isimip3b" / ISO / f"gfdl-esm4_{scenario}_{variable}_{ISO}.nc", "isimip"
                )
                entry = Isimip3bRegistryEntry(
                    gcm="gfdl-esm4",
                    scenario=scenario,
                    variable=variable,
                    country_code=ISO,
                    path=str(p),
                    source_sha256=sha256_file(p),
                    size_bytes=p.stat().st_size,
                    copied_from="test",
                )
                isimip.entries[entry.key] = entry
    isimip.save(raw / "isimip3b" / "isimip3b_registry.json")

    era5 = Era5Registry()
    p = _file(raw / "era5" / ISO / f"{ISO}_fg10_annual_max.nc", "era5")
    era5.entries[f"era5/{ISO}/fg10"] = Era5RegistryEntry(
        country_code=ISO,
        status="registered",
        source_path=str(p),
        source_sha256=sha256_file(p),
        reduced_path=str(p),
        reduced_sha256=sha256_file(p),
    )
    era5.save(raw / "era5" / "_global" / "era5_registry.json")
    if corrupt_era5:
        p.write_text("changed", encoding="utf-8")


def test_complete_inputs_pass_and_are_counted(data_dir, experiments):
    _build(data_dir)
    report = check_external_inputs(ISO, experiments)
    assert (report.cmip6_files, report.isimip3b_files, report.era5_files) == (6, 4, 1)


def test_full_hash_verifies_the_large_files_too(data_dir, experiments):
    _build(data_dir)
    path = data_dir / "raw" / "cmip6" / "_global" / "gfdl_ssp370_tas.nc"
    path.write_text("altered", encoding="utf-8")
    check_external_inputs(ISO, experiments)  # the default check does not hash CMIP6
    with pytest.raises(ExternalInputError, match="gfdl_esm4/ssp370/tas: sha256 differs"):
        check_external_inputs(ISO, experiments, full_hash=True)


def test_every_problem_is_listed_in_one_error(data_dir, experiments):
    _build(data_dir, skip_cmip6=("ssp370", "rsds"), corrupt_era5=True, skip_isimip=True)
    with pytest.raises(ExternalInputError) as err:
        check_external_inputs(ISO, experiments)
    text = str(err.value)
    assert "cmip6/gfdl_esm4/ssp370/rsds: not registered" in text
    assert "isimip3b/gfdl-esm4/historical/tasmax/ZZZ" in text
    assert "era5/ZZZ/fg10: sha256" in text


def test_missing_registry_is_an_error(data_dir, experiments):
    with pytest.raises(ExternalInputError, match="registry missing"):
        check_external_inputs(ISO, experiments)
