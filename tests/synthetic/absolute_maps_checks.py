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
    names = absolute_map_names(iso, tech)
    assert len(names) == 7  # 2 densities per cell, 2 sheets by state, 2 rankings and the limits file (the maps per cell are off by default)
    for name in names.values():
        assert (figures / name).is_file() and (figures / name).stat().st_size > 0, name
    pngs = [n for n in names.values() if n.endswith(".png")]
    assert len(pngs) == 6
    from PIL import Image

    for name in pngs:
        with Image.open(figures / name) as image:
            assert round(image.info["dpi"][0]) == 300, name

    content = json.loads((figures / names[f"potential_breaks_{tech}"]).read_text(encoding="utf-8"))
    parts = [content["per_state"]["capacity_density"], content["per_state"]["energy_density"]]
    for part in parts:
        limits = part["upper_limits"]
        assert (
            limits and limits == sorted(set(limits)) and limits[0] > 0
        )  # monotone, no repeated limit
        assert part["classes_final"] == len(limits) + (1 if part["last_class_open"] else 0)
        assert part["classes_final"] <= part["classes_requested"]
        intervals = part["intervals"]
        assert intervals[0][0] == 0 and all(a[1] == b[0] for a, b in itertools.pairwise(intervals))
        assert (intervals[-1][1] is None) == part["last_class_open"]
        assert part["last_class_open"] and part["method"] == "fisher_jenks"
    assert content["per_state"]["capacity_density"]["classes_requested"] == 6
    assert content["resolution"]["cell_deg"] == 0.05
    assert content["per_cell_classed"] is None

    aggregates = pd.read_parquet(artifacts / f"potential_aggregates_{tech}.parquet")
    aggregates = aggregates[aggregates["member"].astype(str) == "m0"].set_index("scenario")
    for scenario in SCENARIOS:
        table = pd.read_parquet(artifacts / f"potential_{tech}__{scenario}.parquet")
        m0 = table[table["member"].astype(str) == "m0"]
        cells = pd.read_parquet(
            land / f"cells_{tech}__{scenario}.parquet",
            columns=["cell_id", "admin1_id", "cell_area_km2"],
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
        if scenario == "central":
            area = cells.groupby("admin1_id")["cell_area_km2"].sum()
            central_density = (
                by_state["P_MW"] / area.reindex(by_state.index)
            ).to_numpy()  # MW per km2
        for quantity in ("capacity_gw", "energy_twh"):
            for what in ("cells", "states"):
                assert content["sum_checks"][scenario][quantity][what]["ok"]
        assert content["national_totals_f5"][scenario]["P_GW"] == aggregates.loc[scenario, "P_GW"]
    # the state limits are those of the central scenario alone, recomputed here with mapclassify and python's two-figure format
    import mapclassify
    import numpy as np

    values = central_density[central_density > 0]
    k = min(6, len(np.unique(values)))
    expected = []
    for b in mapclassify.FisherJenks(values, k=k).bins[:-1]:
        v = float(f"{b:.2g}")
        if not expected or v > expected[-1]:
            expected.append(v)
    assert content["per_state"]["capacity_density"]["upper_limits"] == expected

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    for key in names:
        assert (
            key in manifest["artifacts"] and manifest["artifacts"][key]["phase"] == "potential_maps"
        )
    return content
