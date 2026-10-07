"""Unit tests for J-3: members, per-cell forcing and members.yaml (M-F4-01, M-F4-03, M-F4-04, M-F4-06)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
import rasterio
import xarray as xr

from geofrea.climate_forcing import forcing as fc
from geofrea.climate_forcing import members as mem
from geofrea.data_acquisition.cmip6_registry import (
    Cmip6NativeGrid,
    Cmip6Registry,
    Cmip6RegistryEntry,
)
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
    manifest = mem.members_manifest(mem.resolve_members(ENSEMBLE), _registry(tmp_path), ((2041, 2070),))

    by_id = {m["member"]: m for m in manifest["members"]}
    ipsl = by_id["m_ipsl_cm6a_lr_ssp126_2041_2070"]
    assert manifest["n_members"] == 9
    assert ipsl["tcr_exception"] is True and ipsl["channels"] == {"resource": True, "hazard": True}
    assert ipsl["realization"] == "r1i1p1f1"
    assert len(ipsl["sources"]) == 6 and ipsl["sources"]["historical/tas"]["sha256"] == "ab" * 32
    # the hazard channel exists only where ISIMIP3b daily data cover the window (2071-2100 not acquired)
    assert by_id["m_ipsl_cm6a_lr_ssp126_2071_2100"]["channels"] == {"resource": True, "hazard": False}
    assert by_id["m0"]["channels"]["hazard"] is False
    assert "tcr_exception" not in by_id["m_gfdl_esm4_ssp126_2041_2070"]
    assert by_id["m0"]["channels"]["resource"] is True


@pytest.mark.unit
def test_members_manifest_fails_loud_on_a_realization_mismatch_or_a_missing_file(tmp_path):
    members = mem.resolve_members(ENSEMBLE)

    with pytest.raises(mem.MemberResolutionError, match="realizations differ"):
        mem.members_manifest(members, _registry(tmp_path, mismatch=True))
    with pytest.raises(mem.MemberResolutionError, match="not registered"):
        mem.members_manifest(members, _registry(tmp_path, skip=("ipsl_cm6a_lr", "ssp126", "tas")))


def _mask_raster(tmp_path, valid_blocks, shape=(20, 30), origin=(1.2, 20.0)):
    """A 0.01 degree raster on the lattice (rows x cols multiple of 5); valid_blocks = [(r0, r1, c0, c1)] pixels."""
    from rasterio.transform import from_origin

    data = np.full(shape, -9999.0, dtype="float32")
    for r0, r1, c0, c1 in valid_blocks:
        data[r0:r1, c0:c1] = 1.0
    path = tmp_path / "mask.tif"
    with rasterio.open(
        path, "w", driver="GTiff", dtype="float32", width=shape[1], height=shape[0], count=1,
        crs="EPSG:4326", transform=from_origin(origin[1], origin[0], 0.01, 0.01), nodata=-9999.0,
    ) as dst:
        dst.write(data, 1)
    return path


@pytest.mark.unit
def test_country_cells_are_the_cells_with_at_least_one_in_country_pixel(tmp_path):
    # one in-country pixel in cell (0,0), a 5x5 block in cell (1,2), nothing elsewhere
    mask = _mask_raster(tmp_path, [(0, 1, 0, 1), (5, 10, 10, 15)])

    cells = fc.country_cells(mask)

    assert len(cells) == 2
    row, col = cell_row_col(cells["lat_c"].to_numpy(), cells["lon_c"].to_numpy())
    assert (cell_id(row, col) == cells["cell_id"].to_numpy()).all()
    assert cells["cell_id"].is_monotonic_increasing and cells["cell_id"].is_unique
    # centers: cell (0,0) of a grid whose NW corner is (lat 1.2, lon 20.0): lat 1.175, lon 20.025
    assert cells["lat_c"].round(3).tolist() == [1.175, 1.125] and cells["lon_c"].round(3).tolist() == [20.025, 20.125]


@pytest.mark.unit
def test_forcing_gives_the_known_factors_for_every_cell_and_member_and_identity_for_m0(tmp_path):
    reg = _registry(tmp_path, rsds_ratio=1.1, dt=2.0)
    cells = fc.country_cells(_mask_raster(tmp_path, [(0, 20, 0, 30)]))
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
    cells = fc.country_cells(_mask_raster(tmp_path, [(5, 15, 0, 10)]))
    members = [m for m in mem.resolve_members(ENSEMBLE) if m.member_id == "m_gfdl_esm4_ssp126_2041_2070"]

    frame = next(fc.forcing_frames(cells, members, reg))

    expected = 1 + 0.01 * (cells["lon_c"].to_numpy() - 18.0)
    np.testing.assert_allclose(frame["delta_rsds"], expected, rtol=1e-5)


@pytest.mark.unit
def test_a_cell_outside_the_native_field_fails_loud_instead_of_being_filled(tmp_path):
    reg = _registry(tmp_path)
    cells = fc.country_cells(_mask_raster(tmp_path, [(0, 10, 0, 10)], origin=(1.2, 40.0)))  # lon 40 is beyond the file
    members = [m for m in mem.resolve_members(ENSEMBLE) if m.member_id == "m_gfdl_esm4_ssp126_2041_2070"]

    with pytest.raises((fc.ForcingGapError, ValueError, IndexError)):
        next(fc.forcing_frames(cells, members, reg))


def _spike_registry(tmp_path):
    """Registry whose sfcWind file has one native cell with a near-zero reference (factor 250 per cell)."""
    reg = _registry(tmp_path)
    for g in ENSEMBLE.gcms:
        for experiment, years, base in (("historical", (1995, 2014), 4.0), ("ssp126", (2041, 2100), 4.2)):
            def fn(y, b=base, exp=experiment):
                def f(la, lo):
                    out = b + 0.0 * la
                    return np.where((la == 3.0) & (lo == 21.0), 0.002 if exp == "historical" else 0.5, out)
                return f
            _write(tmp_path / f"{g.cds_name}_{experiment}_sfcWind.nc", "sfcWind", years, fn)
    return reg


@pytest.mark.unit
def test_cells_whose_wind_factor_is_out_of_range_are_masked_declared_and_never_filled(tmp_path):
    reg = _spike_registry(tmp_path)
    cells = fc.country_cells(_mask_raster(tmp_path, [(0, 20, 0, 30)], origin=(3.2, 20.9)))
    members = [m for m in mem.resolve_members(ENSEMBLE) if m.member_id in ("m0", "m_gfdl_esm4_ssp126_2041_2070")]
    masked: list = []

    frames = list(fc.forcing_frames(cells, members, reg, None, (0.5, 1.5), masked))

    scen = frames[1]
    masked_df = pd.concat(masked)
    assert len(masked_df) > 0 and (masked_df["delta_wind"] > 1.5).all()
    assert set(masked_df["cell_id"]).isdisjoint(set(scen["cell_id"]))  # absent from forcing
    assert len(scen) + len(masked_df) == len(cells)  # every cell is either a row or declared
    assert scen["delta_wind"].between(0.5, 1.5).all()
    assert len(frames[0]) == len(cells)  # m0 is never masked


@pytest.mark.unit
def test_f5_guard_rejects_out_of_range_factors_and_undeclared_absences():
    forcing = pd.DataFrame(
        {"cell_id": [1, 1, 2], "member": ["a", "b", "a"], "delta_wind": [1.0, 1.1, 1.2], "delta_rsds": 1.0, "dT": 1.0}
    )
    masked = pd.DataFrame({"cell_id": [2], "member": ["b"], "delta_wind": [9.0]})
    members = ["a", "b"]

    fc.assert_forcing_usable(forcing, masked, [1, 2], members, (0.5, 1.5))  # complete and in range: passes

    with pytest.raises(fc.ForcingContractError, match="neither in forcing"):
        fc.assert_forcing_usable(forcing, masked.iloc[0:0], [1, 2], members, (0.5, 1.5))  # (2, b) undeclared
    bad = forcing.copy()
    bad.loc[0, "delta_wind"] = 78.0
    with pytest.raises(fc.ForcingContractError, match="outside"):
        fc.assert_forcing_usable(bad, masked, [1, 2], members, (0.5, 1.5))
