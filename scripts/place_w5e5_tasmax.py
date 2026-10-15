"""Place the daily maximum temperature of W5E5 v2.0, 1995-2014, for BRA, PRT and IND in GEOFREA_DATA_DIR/raw/w5e5/<ISO3>/ (V-83; COMMAND 40).

W5E5 v2.0 is the observational reference of the bias adjustment of ISIMIP3b (ISIMIP3BASD v2.5.0, W5E5 v2.0: https://www.isimip.org/gettingstarted/isimip3b-bias-adjustment/,
data set DOI 10.48364/ISIMIP.342217), so the reference heat days of the hazard channel (`tx35_days_ref`, `tx40_days_ref`) are compared with it. The regional `tasmax` files
(`ncks` boxes of the ISIMIP repository, downloaded on 2026-09-30 into the CRAEI raw data and READ here, never written) are on the same 0.5 degree grid and the same daily calendar as
the ISIMIP3b country files in `raw/isimip3b/<ISO3>/`, so the cells that are copied are exactly the cells of those files and no regridding is involved.

Writes `raw/w5e5/<ISO3>/tasmax_W5E5v2.0_<ISO3>_19950101-20141231.nc` and `raw/w5e5/w5e5_registry.json` with the sha256 of every source file and of every file written.
Usage: python scripts/place_w5e5_tasmax.py [source directory of the regional files]
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import xarray as xr
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
SOURCE = Path(r"D:\Douglas\OUTROS\CRAEI_raw_data\raw\climate\w5e5v2.0\tasmax")
BOX = {  # country -> the box of the regional files that holds it
    "BRA": "lon-74.5to-34.0lat-34.5to6.0",
    "PRT": "lon-31.5to-6.0lat32.5to42.5",
    "IND": "lon68.0to98.0lat6.0to37.5",
}
PERIODS = ("19910101-20001231", "20010101-20101231", "20110101-20191231")
FIRST, LAST = "1995-01-01", "2014-12-31"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def main(argv: list[str]) -> int:
    load_dotenv(REPO / ".env", override=False)
    data = Path(os.environ["GEOFREA_DATA_DIR"])
    source = Path(argv[0]) if argv else SOURCE
    registry: dict = {
        "dataset": "W5E5 v2.0 (WFDE5 over land merged with ERA5 over the ocean), tasmax, daily, 0.5 degree",
        "doi": "10.48364/ISIMIP.342217",
        "why": "observational reference of the bias adjustment of ISIMIP3b (ISIMIP3BASD v2.5.0)",
        "source_directory": str(source),
        "placed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "countries": {},
    }
    for iso, box in BOX.items():
        template = xr.open_dataset(
            data / "raw" / "isimip3b" / iso / f"gfdl-esm4_historical_tasmax_{iso}.nc"
        )
        lat, lon = template["lat"].values, template["lon"].values
        parts, sources = [], {}
        for period in PERIODS[:3]:
            path = source / f"tasmax_W5E5v2.0_{period}_{box}.nc"
            sources[path.name] = sha256(path)
            ds = xr.open_dataset(path)
            parts.append(ds["tasmax"].sel(time=slice(FIRST, LAST)).sel(lat=lat, lon=lon))
        da = xr.concat([p for p in parts if p.sizes["time"]], dim="time").load()
        assert da.sizes["time"] == 7305, da.sizes  # 20 years of 365.25 days
        out = data / "raw" / "w5e5" / iso / f"tasmax_W5E5v2.0_{iso}_19950101-20141231.nc"
        out.parent.mkdir(parents=True, exist_ok=True)
        da.to_dataset(name="tasmax").assign_attrs(
            title="W5E5 v2.0 daily maximum near-surface air temperature, cut to the cells of raw/isimip3b",
            source=str(source),
        ).to_netcdf(out)
        registry["countries"][iso] = {
            "path": out.relative_to(data).as_posix(),
            "sha256": sha256(out),
            "size_bytes": out.stat().st_size,
            "cells": [int(da.sizes["lat"]), int(da.sizes["lon"])],
            "days": int(da.sizes["time"]),
            "period": [FIRST, LAST],
            "source_files_sha256": sources,
        }
        print(iso, out, da.shape)
    (data / "raw" / "w5e5" / "w5e5_registry.json").write_text(
        json.dumps(registry, indent=1), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
