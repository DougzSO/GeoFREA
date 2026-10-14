"""ERA5 daily maximum 2 m temperature for BRA, PRT and IND, 1995-2014 (V-83, 2026-10-14; METHODOLOGY M-F1-05 family, OQ-051).

Purpose: compare the reference heat-day counts of the ISIMIP3b hazard channel (`tx35_days_ref`, `tx40_days_ref`) with an
ERA5 count (addendum of `docs/_audit/2026-10_data_diagnostics.md`). The product is the CDS dataset
`derived-era5-single-levels-daily-statistics` (variable `2m_temperature`, statistic `daily_maximum`, hourly frequency, UTC), so
no hourly field is downloaded. One request per country and year, CDS-side bbox filtered with the bbox the gust acquisition used.

Resumable: a year whose file exists and whose sha256 is in the registry is skipped; a failed year is retried up to
MAX_ATTEMPTS times and then recorded in `permanently_failed_years` and the run goes on. Writes only under GEOFREA_DATA_DIR:

  raw/era5/_global/<ISO3>_t2m_dailymax_<year>.nc      one file per country and year (the download, hashed in the registry)
  raw/era5/<ISO3>/<ISO3>_t2m_dailymax.nc              the 20 years joined on the time axis (source_path of the registry entry)
  raw/era5/<ISO3>/<ISO3>_t2m_hot_days_annual.nc       days per year at or above 35 and 40 C per cell (reduced_path)
  raw/era5/_global/era5_registry.json                 entries `era5/<ISO3>/t2m_daily_max`, with sha256 per year

Run: `python scripts/acquire_era5_tmax_daily.py [ISO3 ...]` (default BRA PRT IND).
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path

import cdsapi
import xarray as xr
from dotenv import load_dotenv

from geofrea.core import paths as core_paths
from geofrea.data_acquisition.era5_registry import (
    Era5NativeGrid,
    Era5Registry,
    Era5RegistryEntry,
    sha256_file,
)
from geofrea.data_acquisition.fetchers import era5

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET = "derived-era5-single-levels-daily-statistics"
VARIABLE = "t2m_daily_max"
YEARS = range(1995, 2015)
HOT_THRESHOLDS_C = (35.0, 40.0)  # the thresholds of `hazards.py` (tx35, tx40)
MAX_ATTEMPTS = 3
BACKOFF_S = 120
REQUEST_TIMEOUT_S = 3 * 3600  # submit, queue, process and download of one country-year


def _request(year: int, bbox: list[float]) -> dict:
    return {
        "product_type": "reanalysis",
        "variable": ["2m_temperature"],
        "year": str(year),
        "month": [f"{m:02d}" for m in range(1, 13)],
        "day": [f"{d:02d}" for d in range(1, 32)],
        "daily_statistic": "daily_maximum",
        "time_zone": "utc+00:00",
        "frequency": "1_hourly",
        "area": bbox,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def _download(client, iso: str, year: int, bbox: list[float], out_dir: Path) -> Path:
    final = out_dir / f"{iso}_t2m_dailymax_{year}.nc"
    part = out_dir / f"{iso}_t2m_dailymax_{year}.part.nc"
    part.unlink(missing_ok=True)
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(lambda: client.retrieve(DATASET, _request(year, bbox), str(part)))
    try:
        future.result(timeout=REQUEST_TIMEOUT_S)
    except FutureTimeoutError as exc:
        raise TimeoutError(f"{iso}/{year}: no result after {REQUEST_TIMEOUT_S} s") from exc
    finally:
        pool.shutdown(wait=False)
    if not part.exists() or part.stat().st_size == 0:
        raise OSError(f"{iso}/{year}: the download produced no file")
    with xr.open_dataset(part) as ds:  # a file that does not open is a failed download
        var = next(v for v in ds.data_vars if "2m" in v)
        if ds[var].sizes.get("valid_time", ds[var].sizes.get("time", 0)) < 365:
            raise ValueError(f"{iso}/{year}: {ds[var].sizes} holds fewer than 365 days")
    final.unlink(missing_ok=True)
    part.rename(final)
    return final


def _join_and_reduce(
    iso: str, year_files: dict[int, Path], country_dir: Path
) -> tuple[Path, Path, Era5NativeGrid]:
    """Join the years, write the daily file (Celsius) and the annual counts of days at or above each threshold."""
    parts = []
    for year in sorted(year_files):
        with xr.open_dataset(year_files[year]) as ds:
            name = next(v for v in ds.data_vars if "2m" in v)
            da = ds[name].rename(valid_time="time") if "valid_time" in ds[name].dims else ds[name]
            parts.append(da.load())
    tmax = xr.concat(parts, dim="time").sortby("time") - 273.15
    tmax.name = "tmax_c"
    tmax.attrs.update(
        units="degC", long_name="ERA5 daily maximum 2 m temperature (UTC day)", source=DATASET
    )
    lat_name = "latitude" if "latitude" in tmax.dims else "lat"
    lon_name = "longitude" if "longitude" in tmax.dims else "lon"
    country_dir.mkdir(parents=True, exist_ok=True)
    daily_path = country_dir / f"{iso}_t2m_dailymax.nc"
    tmax.to_dataset().to_netcdf(daily_path)
    counts = xr.Dataset(
        {
            f"tx{int(t)}_days": (tmax >= t).groupby("time.year").sum("time").astype("float32")
            for t in HOT_THRESHOLDS_C
        }
    )
    reduced_path = country_dir / f"{iso}_t2m_hot_days_annual.nc"
    counts.to_netcdf(reduced_path)
    lat, lon = tmax[lat_name].values, tmax[lon_name].values
    grid = Era5NativeGrid(
        lat_resolution_deg=float(abs(lat[1] - lat[0])),
        lon_resolution_deg=float(abs(lon[1] - lon[0])),
        lat_min=float(lat.min()),
        lat_max=float(lat.max()),
        lon_min=float(lon.min()),
        lon_max=float(lon.max()),
        n_lat=len(lat),
        n_lon=len(lon),
    )
    return daily_path, reduced_path, grid


def acquire(iso: str, client, registry_path: Path, lock) -> str:
    global_dir = core_paths.fetched_raw("era5", "_global")
    country_dir = core_paths.fetched_raw("era5", iso)
    gadm = core_paths.fetched_raw("gadm", iso) / f"gadm41_{iso}_0_mainland.shp"
    bbox = era5.bbox_from_polygon(gadm)
    key = f"era5/{iso}/{VARIABLE}"

    def load_entry() -> Era5RegistryEntry | None:
        return Era5Registry.load(registry_path).entries.get(key)

    year_sha: dict[str, str] = dict(getattr(load_entry(), "year_sha256", {}) or {})
    failed: dict[str, str] = {}
    files: dict[int, Path] = {}
    for year in YEARS:
        path = global_dir / f"{iso}_t2m_dailymax_{year}.nc"
        if path.exists() and year_sha.get(str(year)) == sha256_file(path):
            files[year] = path
            print(f"[skip] {iso}/{year}: on disk and in the registry", flush=True)
            continue
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                files[year] = _download(client, iso, year, bbox, global_dir)
                year_sha[str(year)] = sha256_file(files[year])
                print(f"[ok] {iso}/{year}: {files[year].stat().st_size} bytes", flush=True)
                break
            except Exception as exc:  # noqa: BLE001 - recorded, then the run goes on
                print(
                    f"[retry] {iso}/{year}: attempt {attempt}/{MAX_ATTEMPTS}: {type(exc).__name__}: {exc}",
                    flush=True,
                )
                if attempt < MAX_ATTEMPTS:
                    time.sleep(BACKOFF_S)
                else:
                    failed[str(year)] = f"{type(exc).__name__}: {exc}"
        with lock:  # progress is kept after every year, so a crash re-does nothing that landed
            reg = Era5Registry.load(registry_path)
            old = reg.entries.get(key)
            if old is None or old.status == "missing":
                reg.entries[key] = Era5RegistryEntry(
                    country_code=iso,
                    variable=VARIABLE,
                    status="missing",
                    missing_reason="acquisition in progress (V-83)",
                    year_sha256=dict(year_sha),
                    permanently_failed_years=dict(failed),
                )
            else:
                reg.entries[key] = old.model_copy(
                    update={"year_sha256": dict(year_sha), "permanently_failed_years": dict(failed)}
                )
            reg.save(registry_path)
    if len(files) < len(list(YEARS)):
        return f"{iso}: {len(files)} of {len(list(YEARS))} years; failed {sorted(failed)}"
    daily, reduced, grid = _join_and_reduce(iso, files, country_dir)
    with lock:
        reg = Era5Registry.load(registry_path)
        reg.entries[key] = Era5RegistryEntry(
            country_code=iso,
            variable=VARIABLE,
            status="registered",
            bbox_path=None,
            source_path=str(daily),
            source_sha256=sha256_file(daily),
            reduced_path=str(reduced),
            reduced_sha256=sha256_file(reduced),
            reference_period_start=1995,
            reference_period_end=2014,
            native_grid=grid,
            year_sha256=dict(year_sha),
            permanently_failed_years={},
        )
        reg.save(registry_path)
    return f"{iso}: registered ({daily.name}, {reduced.name})"


def main(argv: list[str]) -> int:
    import threading

    load_dotenv(REPO_ROOT / ".env", override=False)
    countries = [c.upper() for c in argv] or ["BRA", "PRT", "IND"]
    client = cdsapi.Client()
    registry_path = core_paths.fetched_raw("era5", "_global") / "era5_registry.json"
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=len(countries)) as pool:
        for line in pool.map(lambda iso: acquire(iso, client, registry_path, lock), countries):
            print(line, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
