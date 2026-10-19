"""Checks of the maps of capacity and energy of a synthetic run (D-F5-029), shared by the ZZZ and ZZZ2 end-to-end tests.

Everything is recomputed from the F5 and F3 tables on disk, not from the code under test.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pandas as pd

from geofrea.technical_potential.absolute_maps import absolute_map_names

SCENARIOS = ("central", "restrictive", "permissive")


def check_absolute_maps(data: Path, iso: str, tech: str) -> dict:
    out = data / "outputs" / iso
    figures = out / "technical_potential" / "figures"
    artifacts = out / "technical_potential" / "artifacts"
    land = out / "land_eligibility" / "artifacts"
    names = absolute_map_names(tech)
    assert len(names) == 9  # 2 per cell + 6 per state + the limits file
    for name in names.values():
        assert (figures / name).is_file() and (figures / name).stat().st_size > 0, name
    pngs = [n for n in names.values() if n.endswith(".png")]
    assert len(pngs) == 8
    from PIL import Image

    for name in pngs:
        with Image.open(figures / name) as image:
            assert round(image.info["dpi"][0]) == 300, name

    content = json.loads((figures / names[f"potential_breaks_{tech}"]).read_text(encoding="utf-8"))
    parts = [
        content["per_cell"]["capacity"],
        content["per_cell"]["energy"],
        content["per_state"]["capacity"],
        content["per_state"]["energy"],
    ]
    for part in parts:
        limits = part["upper_limits"]
        assert (
            limits and limits == sorted(set(limits)) and limits[0] > 0
        )  # monotone, no repeated limit
        assert part["classes_final"] == len(limits) <= part["classes_requested"]
        intervals = part["intervals"]
        assert intervals[0][0] == 0 and all(a[1] == b[0] for a, b in itertools.pairwise(intervals))
    assert content["per_cell"]["capacity"]["classes_requested"] == 7
    assert content["per_state"]["capacity"]["classes_requested"] == 6

    aggregates = pd.read_parquet(artifacts / f"potential_aggregates_{tech}.parquet")
    aggregates = aggregates[aggregates["member"].astype(str) == "m0"].set_index("scenario")
    state_gw_max = 0.0
    for scenario in SCENARIOS:
        table = pd.read_parquet(artifacts / f"potential_{tech}__{scenario}.parquet")
        m0 = table[table["member"].astype(str) == "m0"]
        cells = pd.read_parquet(
            land / f"cells_{tech}__{scenario}.parquet", columns=["cell_id", "admin1_id"]
        )
        joined = m0.merge(cells, on="cell_id", validate="one_to_one")
        assert len(joined) == len(m0)
        gw, twh = m0["P_MW"].sum() / 1e3, m0["E_MWh"].sum() / 1e6
        by_state = joined.groupby("admin1_id")[["P_MW", "E_MWh"]].sum()
        assert abs(gw - aggregates.loc[scenario, "P_GW"]) <= 1e-3 * gw
        assert abs(twh - aggregates.loc[scenario, "E_TWh"]) <= 1e-3 * twh
        assert (
            abs(by_state["P_MW"].sum() / 1e3 - gw) <= 1e-3 * gw
        )  # the states add up to the national total
        assert abs(by_state["E_MWh"].sum() / 1e6 - twh) <= 1e-3 * twh
        state_gw_max = max(state_gw_max, float(by_state["P_MW"].max() / 1e3))
        for quantity in ("capacity_gw", "energy_twh"):
            for what in ("cells", "states"):
                assert content["sum_checks"][scenario][quantity][what]["ok"]
        assert content["national_totals_f5"][scenario]["P_GW"] == aggregates.loc[scenario, "P_GW"]
    # the state classes are those of the three scenarios together: the largest state of any scenario is inside the last class
    assert content["per_state"]["capacity"]["upper_limits"][-1] >= state_gw_max

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    for key in names:
        assert (
            key in manifest["artifacts"] and manifest["artifacts"][key]["phase"] == "potential_maps"
        )
    return content
