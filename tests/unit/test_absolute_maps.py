"""Maps of the potential in capacity and energy: the class limits, the sums and the files (D-F5-029)."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from geofrea.core.config_schemas import AbsoluteMapsConfig
from geofrea.core.constants import CELL_ORIGIN_LAT, CELL_ORIGIN_LON
from geofrea.land_eligibility.cells import cell_id
from geofrea.technical_potential.absolute_maps import (
    AbsoluteMapsError,
    absolute_map_names,
    build_absolute_maps,
    class_breaks,
    format_limit,
    round_significant,
)

CFG = AbsoluteMapsConfig.model_validate(
    {
        "per_cell": False,
        "per_cell_classes": {"method": "quantile", "classes": 7},
        "per_state": {
            "method": "fisher_jenks",
            "classes": 6,
            "basis": "central",
            "open_last_class": True,
        },
        "significant_figures": 2,
        "palette": "viridis",
    }
)
CFG_WITH_CELLS = CFG.model_copy(update={"per_cell": True})


# ─── the limits ──────────────────────────────────────────────────────────


@pytest.mark.unit
def test_rounding_to_two_significant_figures_and_the_last_limit_upwards():
    assert round_significant(1234.0, 2) == 1200.0
    assert round_significant(1234.0, 2, up=True) == 1300.0
    assert round_significant(0.01234, 2) == 0.012
    assert round_significant(19188.47, 2, up=True) == 20000.0
    assert round_significant(20000.0, 2, up=True) == 20000.0  # exact values do not move up
    assert round_significant(0.3, 2, up=True) == 0.3


@pytest.mark.unit
@pytest.mark.parametrize("method", ["quantile", "fisher_jenks"])
def test_limits_are_positive_strictly_increasing_and_hold_the_largest_value(method):
    rng = np.random.default_rng(3)
    values = np.concatenate([rng.lognormal(1.0, 1.5, 4000), np.zeros(500), [np.nan, -3.0]])
    breaks = class_breaks(values, method, 7, 2)
    limits = np.asarray(breaks.limits)
    assert breaks.n_classes == 7 and (limits > 0).all() and (np.diff(limits) > 0).all()
    assert limits[-1] >= np.nanmax(values)  # the largest value is inside the last class
    assert breaks.n_values == 4000  # zeros, NaN and negatives are not classified
    classes = breaks.assign(values)
    assert classes[values > 0].min() == 0 and classes[values > 0].max() == 6
    assert (classes[~(values > 0) | ~np.isfinite(values)] == -1).all()
    intervals = breaks.intervals()
    assert intervals[0][0] == 0.0 and all(a[1] == b[0] for a, b in itertools.pairwise(intervals))


@pytest.mark.unit
def test_quantile_classes_hold_about_the_same_number_of_values():
    values = np.random.default_rng(1).lognormal(0.0, 2.0, 7000)
    counts = np.bincount(class_breaks(values, "quantile", 7, 3).assign(values))
    assert counts.min() > 0.9 * counts.mean() and counts.max() < 1.1 * counts.mean()


@pytest.mark.unit
def test_fisher_jenks_puts_a_limit_between_two_separated_groups():
    values = np.concatenate([np.linspace(1, 2, 20), np.linspace(100, 110, 20)])
    limits = class_breaks(values, "fisher_jenks", 2, 2).limits
    assert limits[0] < 100 and limits[0] >= 2 and limits[1] >= 110


@pytest.mark.unit
def test_classes_that_collapse_after_the_rounding_are_dropped_and_recorded():
    values = np.linspace(1.0, 1.04, 500)  # every quantile is 1.0 at two significant figures
    breaks = class_breaks(values, "quantile", 7, 2)
    assert 1 <= breaks.n_classes < 7
    assert np.all(np.diff(breaks.limits) > 0) and breaks.limits[-1] >= 1.04
    assert any("merged" in note for note in breaks.notes)
    assert breaks.as_json()["collapsed"] is True


@pytest.mark.unit
def test_fewer_distinct_values_than_classes_gives_fewer_classes_and_a_note():
    breaks = class_breaks(np.array([1.0, 1.0, 2.0, 3.0, 3.0, 3.0]), "fisher_jenks", 6, 2)
    assert breaks.n_classes == 3 and breaks.limits == (1.0, 2.0, 3.0)
    assert any("3 distinct values" in note for note in breaks.notes)
    empty = class_breaks(np.zeros(5), "quantile", 7, 2)
    assert empty.n_classes == 0 and empty.n_values == 0


@pytest.mark.unit
def test_the_labels_of_the_limits():
    assert [format_limit(x) for x in (0.0012, 0.5, 1.2, 12.0, 1500.0, 20000.0)] == [
        "0.0012",
        "0.5",
        "1.2",
        "12",
        "1,500",
        "20,000",
    ]


@pytest.mark.unit
def test_an_open_last_class_holds_every_value_above_the_last_limit():
    central = np.array([1.0, 2.0, 2.5, 8.0, 9.0, 10.0, 40.0, 41.0, 90.0])
    breaks = class_breaks(central, "fisher_jenks", 4, 2, open_last=True)
    assert breaks.n_classes == 4 and len(breaks.limits) == 3 and breaks.open_last
    assert np.all(np.diff(breaks.limits) > 0) and breaks.limits[-1] < central.max()
    classes = breaks.assign(
        np.array([central.max(), central.max() * 100, breaks.limits[-1] * 1.001, 0.5])
    )
    assert list(classes) == [3, 3, 3, 0]
    intervals = breaks.intervals()
    assert intervals[-1] == (breaks.limits[-1], None) and len(intervals) == 4
    as_json = breaks.as_json()
    assert (
        as_json["last_class_open"]
        and as_json["classes_final"] == 4
        and as_json["intervals"][-1][1] is None
    )
    closed = class_breaks(central, "fisher_jenks", 4, 2)
    assert not closed.open_last and closed.n_classes == 4 and len(closed.limits) == 4
    assert closed.limits[:-1] == breaks.limits  # the same breaks; only the last limit is dropped


@pytest.mark.unit
def test_an_open_last_class_with_one_class_only_stays_closed():
    breaks = class_breaks(np.array([3.0, 3.0]), "fisher_jenks", 6, 2, open_last=True)
    assert (
        breaks.n_classes == 1
        and not breaks.open_last
        and breaks.assign(np.array([3.0, 99.0])).tolist() == [0, 0]
    )


@pytest.mark.unit
def test_the_configuration_accepts_only_known_methods():
    with pytest.raises(ValueError):
        AbsoluteMapsConfig.model_validate(
            {**CFG.model_dump(), "per_cell_classes": {"method": "equal", "classes": 7}}
        )
    with pytest.raises(ValueError):
        AbsoluteMapsConfig.model_validate({**CFG.model_dump(), "palette": "jet"})


# ─── the maps on a small country ─────────────────────────────────────────

ROWS, COLS = range(100, 104), range(2000, 2006)  # 4 x 6 cells of the lattice
SCENARIO_SCALE = {"central": 1.0, "restrictive": 0.4, "permissive": 1.7}


def _world(tmp_path: Path):
    """Potential tables (m0 and one other member), F3 cell tables with admin1 and the F5 aggregates, for 24 cells in six states (one per column)."""
    pot, land = tmp_path / "pot", tmp_path / "land"
    pot.mkdir()
    land.mkdir()
    rows, cols = np.meshgrid(list(ROWS), list(COLS), indexing="ij")
    ids = cell_id(rows.ravel(), cols.ravel())
    state = np.array([f"ZZZ.{c - 1999}_1" for c in cols.ravel()])
    base = np.linspace(1.0, 24.0, len(ids)) ** 2
    for tech, f in (("solar", 1.0), ("wind", 0.6)):
        aggregates = []
        for scenario, k in SCENARIO_SCALE.items():
            candidate = (
                (np.arange(len(ids)) % 4 != 0)
                if scenario != "permissive"
                else np.ones(len(ids), bool)
            )
            p_mw = base * f * k
            tables = []
            for member, m in (("m0", 1.0), ("m1", 1.1)):
                tables.append(
                    pd.DataFrame(
                        {
                            "cell_id": ids[candidate],
                            "member": member,
                            "P_MW": p_mw[candidate],
                            "CF": 0.2,
                            "E_MWh": p_mw[candidate] * 1900.0 * m,
                        }
                    )
                )
            pd.concat(tables).to_parquet(pot / f"potential_{tech}__{scenario}.parquet")
            pd.DataFrame({"cell_id": ids, "admin1_id": state, "cell_area_km2": 20.0}).to_parquet(
                land / f"cells_{tech}__{scenario}.parquet"
            )
            aggregates.append(
                {
                    "scenario": scenario,
                    "member": "m0",
                    "P_GW": float(p_mw[candidate].sum() / 1e3),
                    "E_TWh": float(p_mw[candidate].sum() * 1900.0 / 1e6),
                }
            )
        pd.DataFrame(aggregates).to_parquet(pot / f"potential_aggregates_{tech}.parquet")
    west = CELL_ORIGIN_LON + 2000 * 0.05
    north = CELL_ORIGIN_LAT - 100 * 0.05
    units = gpd.GeoDataFrame(
        {"admin1_id": [f"ZZZ.{i}_1" for i in range(1, 7)], "admin1_name": list("ABCDEF")},
        geometry=[
            box(west + 0.05 * i, north - 0.2, west + 0.05 * (i + 1), north) for i in range(6)
        ],
        crs="EPSG:4326",
    )
    return pot, land, units


@pytest.mark.unit
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_eight_maps_and_the_limits_file_per_technology_with_sums_that_match_f5(tmp_path, tech):
    pot, land, units = _world(tmp_path)
    figures = tmp_path / "figures"
    written, content = build_absolute_maps("ZZZ", tech, pot, land, figures, units, CFG)
    names = absolute_map_names(tech)
    assert set(written) == set(names) and len(names) == 9
    for key, name in names.items():
        assert written[key] == figures / name and (figures / name).stat().st_size > 0
    pngs = [n for n in names.values() if n.endswith(".png")]
    assert len(pngs) == 8  # 2 densities per cell + 6 per state
    assert not any(
        "_cell_" in n for n in pngs
    )  # the maps of MW and GWh per cell are off by default
    on_disk = json.loads((figures / names[f"potential_breaks_{tech}"]).read_text(encoding="utf-8"))
    assert on_disk == json.loads(json.dumps(content))
    for scenario in SCENARIO_SCALE:
        checks = content["sum_checks"][scenario]
        for quantity in ("capacity_gw", "energy_twh"):
            assert checks[quantity]["cells"]["ok"] and checks[quantity]["states"]["ok"]
            assert checks[quantity]["states"]["relative_difference"] < 1e-9
    for part in (content["per_state"]["capacity_density"], content["per_state"]["energy_density"]):
        limits = part["upper_limits"]
        assert limits == sorted(set(limits)) and limits[0] > 0
        assert part["classes_final"] == len(limits) + (1 if part["last_class_open"] else 0)
        assert part["classes_final"] <= part["classes_requested"]
        assert part["method"] == "fisher_jenks"
        assert part["last_class_open"] and part["intervals"][-1][1] is None
        assert part["intervals"][-1][0] == part["upper_limits"][-1]
    assert content["per_cell_classed"] is None
    assert content["resolution"]["cell_deg"] == 0.05
    cells = content["density_cells"]
    assert (
        cells["capacity_density"]["unit"] == "MW per km²"
        and cells["energy_density"]["unit"] == "GWh per km² per year"
    )
    # the cells as they are, or a declared display smoothing when a cell is more than 4 pixels of the image (COMMAND 67b)
    assert (
        cells["capacity_density"]["interpolation"].startswith("none")
        or cells["capacity_density"]["interpolation"] == "display smoothing"
    )


@pytest.mark.unit
def test_the_per_cell_maps_are_drawn_only_when_the_configuration_asks_for_them(tmp_path):
    pot, land, units = _world(tmp_path)
    assert len(absolute_map_names("solar")) == 9
    assert len(absolute_map_names("solar", per_cell=True)) == 11
    written, content = build_absolute_maps(
        "ZZZ", "solar", pot, land, tmp_path / "f", units, CFG_WITH_CELLS
    )
    assert {"potential_capacity_cell_solar", "potential_energy_cell_solar"} <= set(written)
    assert (
        tmp_path / "f" / "potential_capacity_mw_cell_solar_central__ref__na__na.png"
    ).stat().st_size > 0
    cell = content["per_cell_classed"]
    assert cell["capacity"]["method"] == "quantile" and not cell["capacity"]["last_class_open"]


@pytest.mark.unit
def test_the_state_density_is_the_total_over_the_land_area_not_the_total(tmp_path):
    pot, land, units = _world(tmp_path)
    _, content = build_absolute_maps("ZZZ", "solar", pot, land, tmp_path / "f", units, CFG)
    reference = pd.read_parquet(pot / "potential_solar__central.parquet").query("member == 'm0'")
    cells = pd.read_parquet(
        land / "cells_solar__central.parquet"
    )  # every cell of the state counts in its area, candidate or not
    joined = cells.merge(reference, on="cell_id", how="left")
    by_state = joined.groupby("admin1_id").agg(p=("P_MW", "sum"), area=("cell_area_km2", "sum"))
    density = by_state["p"] / by_state["area"]  # MW per km2
    import mapclassify

    bins = mapclassify.FisherJenks(density.to_numpy(), k=6).bins
    expected = []
    for b in bins[:-1]:
        v = float(f"{b:.2g}")
        if not expected or v > expected[-1]:
            expected.append(v)
    assert content["per_state"]["capacity_density"]["upper_limits"] == expected


@pytest.mark.unit
def test_the_state_totals_are_the_sum_of_their_cells(tmp_path):
    pot, land, units = _world(tmp_path)
    _, content = build_absolute_maps("ZZZ", "solar", pot, land, tmp_path / "f", units, CFG)
    table = pd.read_parquet(pot / "potential_solar__central.parquet")
    table = table[table["member"] == "m0"].merge(
        pd.read_parquet(land / "cells_solar__central.parquet"), on="cell_id"
    )
    by_state = table.groupby("admin1_id")["P_MW"].sum() / 1e3
    assert by_state.sum() == pytest.approx(
        content["national_totals_f5"]["central"]["P_GW"], rel=1e-12
    )

    # the classes are those of the central scenario and the permissive scenario has states above the last limit (the open class)
    def densities(scenario):
        t = (
            pd.read_parquet(pot / f"potential_solar__{scenario}.parquet")
            .query("member == 'm0'")
            .merge(pd.read_parquet(land / f"cells_{'solar'}__{scenario}.parquet"), on="cell_id")
        )
        g = t.groupby("admin1_id").agg(p=("P_MW", "sum"), a=("cell_area_km2", "sum"))
        return g["p"] / g["a"]

    last = content["per_state"]["capacity_density"]["upper_limits"][-1]
    assert densities("permissive").max() > densities("central").max() > last * 0.99
    assert (densities("permissive") > last).sum() >= (densities("central") > last).sum()


@pytest.mark.unit
def test_a_total_that_does_not_add_up_stops_the_maps(tmp_path):
    pot, land, units = _world(tmp_path)
    aggregates = pd.read_parquet(pot / "potential_aggregates_solar.parquet")
    aggregates.loc[aggregates["scenario"] == "restrictive", "P_GW"] *= (
        1.01  # 1% against the 0.1% tolerance
    )
    aggregates.to_parquet(pot / "potential_aggregates_solar.parquet")
    with pytest.raises(AbsoluteMapsError, match="do not add up"):
        build_absolute_maps("ZZZ", "solar", pot, land, tmp_path / "f", units, CFG)
    assert not (tmp_path / "f").exists() or not list((tmp_path / "f").glob("*.png"))


@pytest.mark.unit
def test_an_admin1_unit_the_layer_does_not_have_is_an_error(tmp_path):
    pot, land, units = _world(tmp_path)
    with pytest.raises(AbsoluteMapsError, match="not in the admin1 layer"):
        build_absolute_maps("ZZZ", "solar", pot, land, tmp_path / "f", units.iloc[:1], CFG)
