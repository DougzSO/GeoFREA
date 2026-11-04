"""Share of the eligible area and of the PV potential by PVCZ thermal zone, per country (COMMAND 84, sensitivity `pv_hot_zone_degradation`).

Uses the central solar candidates of F3 and the potential of F5 already on disk (read only); the zone is the one F3 will write as `pvcz_zone`
(`core/pv_zones.py`, nearest PVCZ land point). Zones above T7 count as T7 (M-F6-09). The potential is the capacity (MW) averaged over the climate
members of each cell.
Usage: python scripts/report_pv_zone_shares.py [BRA IND PRT]
Output: stdout and docs/_audit/pv_zone_shares_84.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from geofrea.core.config_loader import load_settings
from geofrea.core.pv_zones import ZoneSource, zones_for_cells

HOT_FROM = 7  # the sensitivity applies to cells of T7 or above


def _data_dir() -> Path:
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("GEOFREA_DATA_DIR="):
            return Path(line.split("=", 1)[1].strip().strip('"'))
    raise SystemExit("GEOFREA_DATA_DIR is not set in .env")


def shares(iso: str, source: ZoneSource, out: Path) -> pd.DataFrame:
    base = out / iso
    cand = pd.read_parquet(
        base / "land_eligibility" / "artifacts" / "candidates_solar__central.parquet"
    )
    pot = pd.read_parquet(
        base / "technical_potential" / "artifacts" / "potential_solar__central.parquet"
    )
    capacity = pot.groupby("cell_id")["P_MW"].mean().rename("P_MW")
    energy = pot.groupby("cell_id")["E_MWh"].mean().rename("E_MWh")
    frame = cand.merge(capacity, left_on="cell_id", right_index=True, how="left").merge(
        energy, left_on="cell_id", right_index=True, how="left"
    )
    zone = zones_for_cells(frame["lat_c"].to_numpy(), frame["lon_c"].to_numpy(), source)
    frame["zone"] = np.where(zone == 0, 0, np.minimum(zone, HOT_FROM))
    table = frame.groupby("zone").agg(
        cells=("cell_id", "size"),
        area=("eligible_area_km2", "sum"),
        mw=("P_MW", "sum"),
        mwh=("E_MWh", "sum"),
    )
    table["area_share"] = table["area"] / table["area"].sum()
    table["potential_share"] = table["mw"] / table["mw"].sum()
    table["energy_share"] = table["mwh"] / table["mwh"].sum()
    return table


def main(isos):
    out = _data_dir() / "outputs"
    geo = load_settings(REPO / "config" / "settings.yaml").geospatial
    source = ZoneSource(
        csv_path=_data_dir() / geo.pvcz_csv, max_distance_km=geo.pvcz_max_distance_km
    )
    md = [
        "# PV potential and eligible area by thermal zone (COMMAND 84)",
        "",
        (
            "Central scenario, solar. Zone of the cell = PVCZ-2019 nearest land point (T7 holds T7 and above; `no zone` = no land point within "
            f"{geo.pvcz_max_distance_km:g} km). Potential = capacity averaged over the climate members. The sensitivity `pv_hot_zone_degradation` "
            "(0.94 %/yr, Straub-Mueck 2025, global median) applies to the share in T7. Computed from existing F3 and F5 outputs; the `pvcz_zone` column "
            "itself is written by F3 at the next round."
        ),
        "",
    ]
    for iso in isos:
        t = shares(iso, source, out)
        print(iso)
        print(t.round(4).to_string(), flush=True)
        md += [
            f"## {iso}",
            "",
            "| Zone | Cells | Eligible area (km2) | Area share | Capacity (MW) | Potential share | Energy share |",
            "|---|---|---|---|---|---|---|",
        ]
        for z, r in t.iterrows():
            name = "no zone" if z == 0 else (f"T{z}" if z < HOT_FROM else "T7+")
            md.append(
                f"| {name} | {int(r['cells'])} | {r['area']:.0f} | {r['area_share']:.3%} | {r['mw']:.0f} | {r['potential_share']:.3%} | {r['energy_share']:.3%} |"
            )
        md.append("")
    (REPO / "docs" / "_audit" / "pv_zone_shares_84.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:] or ["BRA", "IND", "PRT"])
