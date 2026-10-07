"""Unit tests for J-3: members, per-cell forcing and members.yaml (M-F4-01, M-F4-03, M-F4-04, M-F4-06)."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
import xarray as xr
from shapely.geometry import box

from geofrea.climate_forcing import forcing as fc
from geofrea.climate_forcing import members as mem
from geofrea.data_acquisition.cmip6_registry import Cmip6NativeGrid, Cmip6Registry, Cmip6RegistryEntry
from geofrea.land_eligibility.cells import cell_id, cell_row_col

ENSEMBLE = mem.Ensemble(
    gcms=(
        mem.Gcm("GFDL-ESM4", "gfdl_esm4", hazard_channel=True),
        mem.Gcm("IPSL-CM6A-LR", "ipsl_cm6a_lr", hazard_channel=True, tcr_ar6_k=2.32, tcr_exception=True),
    ),
    ssps=("SSP1-2.6", "SSP3-7.0"),
    windows=((2041, 2070), (2071, 2100)),
)

LAT = np.arange(-1.0, 6.01, 1.0)
LON = np.arange(18.0, 24.01, 1.0)


def _write(path, variable, years, value_fn, realization="r1i1p1f1"):
    times = pd.date_range(f"{years[0]}-01-01", f"{years[1]}-12-01", freq="MS")
    data = np.empty((len(times), len(LAT), len(LON)))
    for i, t in enumerate(times):
        data[i] = value_fn(t.year)(LAT[:, None], LON[None, :])
    xr.Dataset(
        {variable: (("time", "lat", "lon"), data)}, coords={"time": times, "lat": LAT, "lon": LON}
    ).to_netcdf(path)


def _registry(tmp_path, *, rsds_ratio=1.1, dt=2.0, mismatch=False, skip=None):
    """Registry whose files give delta_rsds = rsds_ratio, delta_wind = 1.05, dT = dt everywhere."""
    reg = Cmip6Registry()
    grid = Cmip6NativeGrid(lat_resolution_deg=1, lon_resolution_deg=1, lat_min=-1, lat_max=6, lon_min=18, lon_max=24, n_lat=8, n_lon=7)
    for g in ENSEMBLE.gcms:
        for experiment in ("historical", "ssp126", "ssp370"):
            years = (1995, 2014) if experiment == "historical" else (2041, 2100)
            for variable, hist, scen in (
                ("rsds", 200.0, 200.0 * rsds_ratio),
                ("sfcWind", 4.0, 4.0 * 1.05),
                ("tas", 290.0, 290.0 + dt),
            ):
                if skip == (g.cds_name, experiment, variable):
                    continue
                base = hist if experiment == "historical" else scen
                path = tmp_path / f"{g.cds_name}_{experiment}_{variable}.nc"
                _write(path, variable, years, lambda y, b=base: (lambda la, lo: b + 0.0 * la))
                realization = "r2i1p1f1" if (mismatch and experiment == "ssp370" and g.cds_name == "gfdl_esm4") else "r1i1p1f1"
                e = Cmip6RegistryEntry(
                    model=g.cds_name, experiment=experiment, variable=variable, status="registered",
                    global_path=str(path), source_sha256="ab" * 32, realization=realization, native_grid=grid,
                )
                reg.entries[e.key] = e
    return reg


@pytest.mark.unit
def test_members_are_the_reference_plus_the_full_factorial_with_unique_ids():
    members = mem.resolve_members(ENSEMBLE)

    assert members[0].member_id == "m0" and members[0].gcm is None
    assert len(members) == 1 + 2 * 2 * 2
    assert len({m.member_id for m in members}) == len(members)
    assert "m_ipsl_cm6a_lr_ssp370_2071_2100" in {m.member_id for m in members}


@pytest.mark.unit
def test_load_ensemble_reads_the_real_experiments_yaml():
    from pathlib import Path

    ens = mem.load_ensemble(Path(__file__).resolve().parents[2] / "config" / "experiments.yaml")

    assert [g.cds_name for g in ens.gcms] == [
        "gfdl_esm4", "miroc6", "access_cm2", "ipsl_cm6a_lr", "cnrm_cm6_1", "mri_esm2_0",
    ]
    assert len(mem.resolve_members(ens)) == 1 + 6 * 3 * 2
    assert [g.name for g in ens.gcms if g.tcr_exception] == ["IPSL-CM6A-LR"]
    assert [g.name for g in ens.gcms if g.hazard_channel] == ["GFDL-ESM4", "IPSL-CM6A-LR", "MRI-ESM2-0"]


@pytest.mark.unit
def test_members_manifest_declares_channels_provenance_and_the_tcr_exception(tmp_path):
    manifest = mem.members_manifest(mem.resolve_members(ENSEMBLE), _registry(tmp_path))

    by_id = {m["member"]: m for m in manifest["members"]}
    ipsl = by_id["m_ipsl_cm6a_lr_ssp126_2041_2070"]
    assert manifest["n_members"] == 9
    assert ipsl["tcr_exception"] is True and ipsl["channels"] == {"resource": True, "hazard": True}
    assert ipsl["realization"] == "r1i1p1f1"
    assert len(ipsl["sources"]) == 6 and ipsl["sources"]["historical/tas"]["sha256"] == "ab" * 32
    assert "tcr_exception" not in by_id["m_gfdl_esm4_ssp126_2041_2070"]
    assert by_id["m0"]["channels"]["resource"] is True


@pytest.mark.unit
def test_members_manifest_fails_loud_on_a_realization_mismatch_or_a_missing_file(tmp_path):
    members = mem.resolve_members(ENSEMBLE)

    with pytest.raises(mem.MemberResolutionError, match="realizations differ"):
        mem.members_manifest(members, _registry(tmp_path, mismatch=True))
    with pytest.raises(mem.MemberResolutionError, match="not registered"):
        mem.members_manifest(members, _registry(tmp_path, skip=("ipsl_cm6a_lr", "ssp126", "tas")))


@pytest.mark.unit
def test_country_cells_are_the_lattice_cells_that_intersect_the_polygon():
    mainland = gpd.GeoDataFrame(geometry=[box(20.0, 1.0, 20.12, 1.07)], crs="EPSG:4326")

    cells = fc.country_cells(mainland)

    # lon 20.00-20.12 touches columns of 0.05 deg: 20.00-20.05, 20.05-20.10, 20.10-20.15 ; lat 1.00-1.07: two rows
    assert len(cells) == 6
    row, col = cell_row_col(cells["lat_c"].to_numpy(), cells["lon_c"].to_numpy())
    assert (cell_id(row, col) == cells["cell_id"].to_numpy()).all()
    assert cells["cell_id"].is_monotonic_increasing and cells["cell_id"].is_unique


@pytest.mark.unit
def test_forcing_gives_the_known_factors_for_every_cell_and_member_and_identity_for_m0(tmp_path):
    reg = _registry(tmp_path, rsds_ratio=1.1, dt=2.0)
    mainland = gpd.GeoDataFrame(geometry=[box(20.0, 1.0, 20.3, 1.2)], crs="EPSG:4326")
    cells = fc.country_cells(mainland)
    members = mem.resolve_members(ENSEMBLE)

    out = tmp_path / "forcing.parquet"
    n = fc.write_forcing(fc.forcing_frames(cells, members, reg), out)

    df = pq.read_table(out).to_pandas()
    assert n == len(df) == len(cells) * len(members)
    assert set(df.columns) == {"cell_id", "member", "delta_rsds", "dT", "delta_wind"}
    real = df[df["member"] != "m0"]
    np.testing.assert_allclose(real["delta_rsds"], 1.1, rtol=1e-6)
    np.testing.assert_allclose(real["delta_wind"], 1.05, rtol=1e-6)
    np.testing.assert_allclose(real["dT"], 2.0, rtol=1e-6)
    ref = df[df["member"] == "m0"]
    assert (ref["delta_rsds"] == 1).all() and (ref["delta_wind"] == 1).all() and (ref["dT"] == 0).all()


@pytest.mark.unit
def test_forcing_interpolates_bilinearly_between_native_cells(tmp_path):
    reg = _registry(tmp_path)
    # make the scenario rsds vary linearly in longitude: ratio 1 + 0.01 * (lon - 18)
    for g in ENSEMBLE.gcms:
        path = tmp_path / f"{g.cds_name}_ssp126_rsds.nc"
        _write(path, "rsds", (2041, 2100), lambda y: (lambda la, lo: 200.0 * (1 + 0.01 * (lo - 18.0)) + 0.0 * la))
    mainland = gpd.GeoDataFrame(geometry=[box(20.0, 1.0, 20.1, 1.1)], crs="EPSG:4326")
    cells = fc.country_cells(mainland)
    members = [m for m in mem.resolve_members(ENSEMBLE) if m.member_id == "m_gfdl_esm4_ssp126_2041_2070"]

    frame = next(fc.forcing_frames(cells, members, reg))

    expected = 1 + 0.01 * (cells["lon_c"].to_numpy() - 18.0)
    np.testing.assert_allclose(frame["delta_rsds"], expected, rtol=1e-5)


@pytest.mark.unit
def test_a_cell_outside_the_native_field_fails_loud_instead_of_being_filled(tmp_path):
    reg = _registry(tmp_path)
    far = gpd.GeoDataFrame(geometry=[box(40.0, 1.0, 40.1, 1.1)], crs="EPSG:4326")  # lon 40 is beyond the file
    cells = fc.country_cells(far)
    members = [m for m in mem.resolve_members(ENSEMBLE) if m.member_id == "m_gfdl_esm4_ssp126_2041_2070"]

    with pytest.raises((fc.ForcingGapError, ValueError, IndexError)):
        next(fc.forcing_frames(cells, members, reg))
