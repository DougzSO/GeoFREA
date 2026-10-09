"""The ERA5 dask-backed netCDF writes run on dask's synchronous scheduler (root cause of the merge stall, 2026-10-09).

With the threaded scheduler, xarray's netCDF4 backend could deadlock: one dask thread waited for the write lock in
`netCDF4_.py::__setitem__` while another waited for the read lock in `_getitem` (py-spy dump of a frozen merge worker;
about one hang in a dozen runs of `test_merge_yearly_files_concatenates_along_time`, ended only by the 15 minute watchdog).
The hang is probabilistic, so the guard is deterministic instead: the scheduler in force while the data is written must be the
synchronous one, which has no worker threads to deadlock.
"""

from __future__ import annotations

from types import SimpleNamespace

import dask
import numpy as np
import pandas as pd
import pytest
import xarray as xr

from geofrea.data_acquisition.fetchers import era5


def _write_daily(path, dates):
    data = np.random.default_rng(0).random((len(dates), 2, 2))
    xr.Dataset(
        {"fg10": (("valid_time", "latitude", "longitude"), data)},
        coords={
            "valid_time": pd.to_datetime(dates),
            "latitude": [0.0, 1.0],
            "longitude": [0.0, 1.0],
        },
    ).to_netcdf(path)


@pytest.mark.unit
def test_the_single_threaded_helper_sets_the_synchronous_scheduler_and_restores_the_previous_one():
    before = dask.config.get("scheduler", None)
    with era5._single_threaded_dask():
        assert dask.config.get("scheduler") == "synchronous"
    assert dask.config.get("scheduler", None) == before


@pytest.mark.unit
def test_the_merge_write_runs_on_the_synchronous_scheduler(tmp_path, monkeypatch):
    first, second = tmp_path / "a.nc", tmp_path / "b.nc"
    _write_daily(first, ["2010-01-01", "2010-01-02"])
    _write_daily(second, ["2011-01-01", "2011-01-02"])
    seen: list[str | None] = []
    original = xr.Dataset.to_netcdf

    def spy(self, *args, **kwargs):
        seen.append(dask.config.get("scheduler", None))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(xr.Dataset, "to_netcdf", spy)
    out = tmp_path / "merged.nc"
    era5._merge_worker([first, second], out, "test", SimpleNamespace(value=0))
    assert seen == ["synchronous"]
    with xr.open_dataset(out) as merged:
        assert merged.sizes["valid_time"] == 4


@pytest.mark.unit
def test_the_reduce_and_crop_writes_use_the_same_helper():
    """The three dask-backed writes of the module (merge, crop, reduce) are all inside `_single_threaded_dask()`."""
    import inspect

    for worker in (era5._merge_worker, era5._crop_worker, era5._reduce_worker):
        assert "_single_threaded_dask()" in inspect.getsource(worker), worker.__name__
