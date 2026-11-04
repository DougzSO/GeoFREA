"""Export the global 0.25 degree PVCZ-2019 land points (Karin et al. 2019) from the `pvcz` package to a CSV under GEOFREA_DATA_DIR (COMMAND 83).

usage: python scripts/export_pvcz_csv.py [--out PATH]

The package ships the dataset as a pandas pickle (`PVCZ-2019_ver0p2_world_PV_climate_stressors_and_zones.pkl`), not as a CSV. This script reads that
file (installed by `pip install pvcz`; a pickle is code, so it is read only from the installed package of the project environment) and writes the
columns the zone lookup needs: `lat`, `lon`, `T_equiv_rack_1p1eV` (deg C) and `T_equiv_rack_1p1eV_zone` (0 to 9, T1 to T10). It also checks that
`geofrea.core.pv_zones.classify_zone` reproduces the zone column of the package from the temperature (up to the float16 rounding of the
temperature, within 0.1 deg C of a limit), and prints the SHA-256 of the CSV for the manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from geofrea.core.pv_zones import ZONE_LIMITS_C, classify_zone

DEFAULT_OUT = Path("D:/Douglas/DOUTORADO/GeoFREA_data/external/pvcz/pvcz_2019_ver0p2_t_equiv_rack_1p1eV_zone.csv")
PICKLE = "PVCZ-2019_ver0p2_world_PV_climate_stressors_and_zones.pkl"
COLUMNS = ["lat", "lon", "T_equiv_rack_1p1eV", "T_equiv_rack_1p1eV_zone"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    import pvcz

    frame = pd.read_pickle(Path(pvcz.__file__).parent / PICKLE)[COLUMNS].astype("float32")
    temperature = frame["T_equiv_rack_1p1eV"].to_numpy()
    mine = classify_zone(temperature) - 1
    package = frame["T_equiv_rack_1p1eV_zone"].to_numpy()
    # The package stores the temperature as float16 (resolution about 0.016 deg C near 19 to 54) but computed the zone before rounding, so a point
    # within that resolution of a limit can fall on either side: the zone column of the package is the authority, the temperature is for checking.
    near_limit = np.abs(temperature[:, None] - np.asarray(ZONE_LIMITS_C)[None, :]).min(axis=1) <= 0.1
    differ = int((mine != package).sum())
    differ_away = int(((mine != package) & ~near_limit).sum())
    print(f"points: {len(frame)}; classify_zone differs from the package zone at {differ} points, {differ_away} of them more than 0.1 deg C from a limit")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.out, index=False, float_format="%.6f")
    digest = hashlib.sha256(args.out.read_bytes()).hexdigest()
    print(f"wrote {args.out} ({args.out.stat().st_size} bytes); sha256 {digest}")
    print("zone counts (0-9):", dict(zip(*np.unique(package, return_counts=True), strict=True)))
    return 1 if differ_away else 0


if __name__ == "__main__":
    raise SystemExit(main())
