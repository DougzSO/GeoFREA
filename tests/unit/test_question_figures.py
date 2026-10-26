"""The figures that answer the questions of the thesis (`technical_potential/question_figures.py`, COMMAND 69; spec v2 T-15 items 1 to 4): the supply
curve against the capacity factor, the interval of land availability, the change by SSP and window with the sign agreement, and the comparison of the
countries on shared axes."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import yaml

from geofrea.core import paths as core_paths
from geofrea.core.constants import HOURS_PER_YEAR
from geofrea.land_eligibility.cells import cell_id
from geofrea.technical_potential import question_figures as T
from geofrea.viz import mapstyle as ms
from geofrea.viz.context import country_geometry, map_context

pytestmark = pytest.mark.unit

ROWS = [1000, 1001, 1002]
COLS = [2000, 2001, 2002, 2003]
IDS = cell_id(*(a.ravel() for a in np.meshgrid(ROWS, COLS, indexing="ij")))
N = IDS.size
GCMS = ("gcm_a", "gcm_b", "gcm_c")
SSPS = ("SSP1-2.6", "SSP5-8.5")
WINDOWS = ("2041-2070", "2071-2100")
AREA = 25.0
LAND = {"restrictive": 0.2, "central": 0.5, "permissive": 0.9}


def _members():
    return [
        (f"m_{g}_{s.replace('-', '').replace('.', '')}_{w}", g, s, w)
        for g in GCMS
        for s in SSPS
        for w in WINDOWS
    ]


def stage(iso: str, tech: str = "solar", scale: float = 1.0, shift: float = 0.0):
    """The tables of a synthetic country: `N` cells, three land scenarios, a reference member and a member for each GCM, SSP and window."""
    potential = core_paths.phase_dir(iso, "technical_potential", "artifacts")
    land = core_paths.phase_dir(iso, "land_eligibility", "artifacts")
    climate = core_paths.phase_dir(iso, "climate_forcing", "artifacts")
    for folder in (potential, land, climate):
        folder.mkdir(parents=True, exist_ok=True)
    base_cf = 0.15 + 0.01 * np.arange(N) + shift
    members = _members()
    aggregates = []
    for scenario, share in LAND.items():
        pieces = []
        for member, gcm, ssp, _window in [("m0", "", "", "")] + members:
            factor = (
                1.0
                if member == "m0"
                else 1.0 + 0.02 * (GCMS.index(gcm) - 1) + (0.01 if ssp == SSPS[1] else 0.0)
            )
            cf = base_cf * factor
            p = np.full(N, share * 10.0 * AREA * scale)
            pieces.append(
                pd.DataFrame(
                    {
                        "cell_id": IDS,
                        "member": member,
                        "P_MW": p,
                        "CF": cf,
                        "E_MWh": p * cf * HOURS_PER_YEAR,
                    }
                )
            )
        table = pd.concat(pieces, ignore_index=True)
        table["member"] = table["member"].astype("category")
        table.to_parquet(potential / f"potential_{tech}__{scenario}.parquet")
        reference = table[table["member"] == "m0"]
        for member, group in table.groupby("member", observed=True):
            aggregates.append(
                {
                    "scenario": scenario,
                    "member": str(member),
                    "P_GW": group["P_MW"].sum() / 1e3,
                    "E_TWh": group["E_MWh"].sum() / 1e6,
                    "delta_E_pct_vs_m0_like_for_like": 100.0
                    * (group["E_MWh"].sum() / reference["E_MWh"].sum() - 1.0),
                }
            )
        pd.DataFrame(
            {"cell_id": IDS, "cell_area_km2": AREA, "eligible_area_km2": share * AREA}
        ).to_parquet(land / f"cells_{tech}__{scenario}.parquet")
    pd.DataFrame(aggregates).to_parquet(potential / f"potential_aggregates_{tech}.parquet")
    document = {
        "members": [{"member": "m0"}]
        + [
            {
                "member": m,
                "gcm": g,
                "ssp": s,
                "window": w,
                "native_grid": {"lat_resolution_deg": 1.0, "lon_resolution_deg": 1.0},
            }
            for m, g, s, w in members
        ]
    }
    (climate / "members.yaml").write_text(yaml.safe_dump(document), encoding="utf-8")


def members_of(iso: str):
    return T.read_members(
        core_paths.phase_dir(iso, "climate_forcing", "artifacts") / "members.yaml"
    )


def ctx():
    return map_context(country_geometry(None, IDS), None)


def test_the_supply_curve_runs_from_the_highest_capacity_factor_and_adds_up_to_the_total():
    stage("ZZZ")
    data = T.read_tech("ZZZ", "solar")
    cf, gw, twh = T.supply_curve(data.reference["central"])
    assert (np.diff(cf) <= 0).all() and (np.diff(gw) >= 0).all()
    assert gw[-1] == pytest.approx(T.totals(data)["central"][0])
    assert twh[-1] == pytest.approx(T.totals(data)["central"][1])
    assert cf[0] == pytest.approx(0.15 + 0.01 * (N - 1))


def test_a_long_curve_is_thinned_with_its_ends_kept():
    n = T.MAX_POINTS * 3
    table = pd.DataFrame({"P_MW": np.ones(n), "CF": np.linspace(0.5, 0.1, n), "E_MWh": np.ones(n)})
    cf, gw, _ = T.supply_curve(table)
    assert cf.size <= T.MAX_POINTS
    assert cf[0] == pytest.approx(0.5) and gw[-1] == pytest.approx(n / 1e3)


def test_the_capacity_factor_axis_is_a_multiple_of_five_hundredths_around_the_data():
    low = pd.DataFrame({"P_MW": [1.0, 1.0], "CF": [0.12, 0.31]})
    assert T.cf_limits([low]) == pytest.approx((0.10, 0.35))


def test_the_supply_chart_has_a_line_per_land_scenario_and_declares_the_missing_cut(tmp_path):
    stage("ZZZ")
    chart = T.supply_chart("ZZZ", T.read_tech("ZZZ", "solar"), "capacity")
    assert len(chart.artists["curves"]) == 3
    assert chart.ax.xaxis_inverted()
    path = ms.save_png(chart, tmp_path / T.supply_name("ZZZ", "capacity", "solar"))
    meta = ms.read_png_metadata(path)
    assert "no resource cut" in meta["Description"]
    assert meta["Title"].endswith("Supply curve, cumulative capacity against capacity factor")
    assert ms.validate_filename(path.name)


def test_the_land_range_is_the_restrictive_to_the_permissive_value_with_the_central_inside():
    stage("ZZZ")
    data = T.read_tech("ZZZ", "solar")
    area = T._range_values(data, "area")
    assert area == pytest.approx([a * N * AREA / 1e3 for a in LAND.values()])
    for quantity in ("capacity", "energy"):
        low, mid, high = T._range_values(data, quantity)
        assert low < mid < high
    chart = T.land_range_chart("ZZZ", {"solar": data})
    assert len(chart.axes) == 3


def test_the_totals_of_the_change_are_the_mean_and_the_range_over_the_gcms():
    stage("ZZZ")
    table = T.change_totals(T.read_tech("ZZZ", "solar"), members_of("ZZZ"))
    assert len(table) == len(SSPS) * len(WINDOWS) and (table["n_gcms"] == len(GCMS)).all()
    row = table[(table["ssp"] == SSPS[0]) & (table["window"] == WINDOWS[0])].iloc[0]
    assert row["mean"] == pytest.approx(0.0, abs=1e-9)  # the three GCMs are -2 %, 0 and +2 %
    assert row["low"] == pytest.approx(-2.0) and row["high"] == pytest.approx(2.0)


def test_the_change_sheet_has_a_map_per_ssp_and_window_one_scale_and_the_stipple_note(tmp_path):
    stage("ZZZ")
    sheet = T.change_sheet(ctx(), "ZZZ", T.read_tech("ZZZ", "solar"), members_of("ZZZ"))
    assert len(sheet.panels) == len(SSPS) * len(WINDOWS)
    path = ms.save_png(sheet, tmp_path / T.change_sheet_name("ZZZ", "solar"))
    meta = ms.read_png_metadata(path)
    assert "same percentage" in meta["Description"]
    assert meta["geofrea_agreement_threshold"].startswith("0.667")
    assert meta["geofrea_scale_mode"] == "shared"


def test_the_change_of_a_cell_is_the_ratio_of_its_capacity_factors():
    stage("ZZZ")
    data = T.read_tech("ZZZ", "solar")
    info = members_of("ZZZ")
    grids, lattice = T.change_grids(data, info, data.reference["central"]["cell_id"].to_numpy())
    first = info[0]
    grid = grids[first.member]["change"]
    assert grid.shape == lattice.shape and np.isfinite(grid).all()
    rows = data.members["central"]
    rows = rows[rows["member"].astype(str) == first.member]
    expected = 100.0 * (rows["CF"].to_numpy() / data.reference["central"]["CF"].to_numpy() - 1.0)
    assert np.sort(grid.ravel()) == pytest.approx(np.sort(expected), rel=1e-4, abs=1e-4)


def test_the_figures_of_a_country_are_named_after_the_keys_of_the_phase(tmp_path):
    stage("ZZZ", "solar")
    stage("ZZZ", "wind", scale=0.2)
    written = T.build_question_figures("ZZZ", ("solar", "wind"), ctx(), tmp_path / "figures")
    assert list(written) == list(T.question_figure_keys(("solar", "wind")))
    assert {p.name for p in written.values()} == set(
        T.question_figure_names("ZZZ", ("solar", "wind")).values()
    )
    assert (tmp_path / "figures" / "figures_index.json").is_file()
    for path in written.values():
        meta = ms.read_png_metadata(path)
        assert meta["geofrea_data_source"].startswith("F5")
        assert meta["geofrea_status"] == "thesis"


def test_the_comparison_puts_the_countries_on_shared_axes_and_skips_a_lone_country(tmp_path):
    stage("ZZZ")
    assert T.build_comparison(["ZZZ"], ("solar",), out_dir=tmp_path / "one") == []
    stage("XXX", scale=2.0, shift=0.05)
    written = T.build_comparison(["ZZZ", "XXX", "YYY"], ("solar",), out_dir=tmp_path / "cmp")
    assert [p.name for p in written] == [
        "ALL_F5_comparison_solar_land-scenarios_ref.png",
        "ALL_F5_supply-curve-per-area_solar_land-scenarios_ref.png",
    ]
    meta = ms.read_png_metadata(written[0])
    assert meta["geofrea_countries"] == "ZZZ,XXX"  # YYY has no tables: left out
    assert "area of the cells of the country" in meta["Description"]


def test_the_capacity_per_area_is_per_area_of_the_country_not_absolute():
    stage("ZZZ", scale=1.0)
    stage("XXX", scale=3.0)
    a, b = T.read_tech("ZZZ", "solar"), T.read_tech("XXX", "solar")
    density_a = T.totals(a)["central"][0] * 1e3 / a.country_area_km2
    density_b = T.totals(b)["central"][0] * 1e3 / b.country_area_km2
    assert density_b == pytest.approx(3.0 * density_a)
    assert a.country_area_km2 == pytest.approx(N * AREA)
