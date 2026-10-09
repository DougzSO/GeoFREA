"""F5 end to end on a synthetic country (A-06, D-F5-013), the masked-cell contract (M-F4-07), V-03 invariants, fail-loud inputs, A-04.

The candidate tables are built here in the shape of the F3 output; the forcing is built here with round, known factors and one
declared masked cell-member (D13, option a). The parameters are the synthetic country's test values of `config/parameters.json`.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
import yaml

from geofrea.climate_forcing.forcing import ForcingContractError
from geofrea.core.config_loader import load_audit_config, load_parameters, load_technologies
from geofrea.core.config_schemas import IecClassBound, TechnologyConfig
from geofrea.core.constants import HOURS_PER_YEAR, RHO0_KG_M3
from geofrea.core.schemas import CountryParams
from geofrea.core.tables import read_schema_version
from geofrea.land_eligibility.cells import cell_id
from geofrea.land_eligibility.pipeline import WIND_HEIGHTS_M
from geofrea.siting_layers.sanity import CountryGeometry
from geofrea.technical_potential.aggregates import aggregate_scenario
from geofrea.technical_potential.cf_models import (
    CF_MODELS,
    CfModelError,
    MissingParameterError,
    get_cf_model,
)
from geofrea.technical_potential.iec_class import IecClassError, assign_by_mean_speed
from geofrea.technical_potential.input_ranges import (
    InputRangeError,
    resolve_input_ranges,
    validate_candidates,
)
from geofrea.technical_potential.pipeline import PROVENANCE_KEY, build_potential
from geofrea.technical_potential.power_curve import SyntheticCurveError, load_power_curve
from geofrea.technical_potential.table_schemas import POTENTIAL_TABLE_SCHEMA_VERSION
from geofrea.technical_potential.weibull_cf import equivalent_scale, wind_cf_member
from geofrea.technical_potential.wind_profile import HubHeightError, resource_at_hub_height

REPO = Path(__file__).resolve().parents[2]
PARAMETERS = REPO / "config" / "parameters.json"
TECHNOLOGIES = REPO / "config" / "technologies.yaml"
EXPERIMENTS = REPO / "config" / "experiments.yaml"
REAL_CURVES_DIR = REPO / "config" / "power_curves"
FIXTURE_CURVES = REPO / "tests" / "fixtures" / "power_curves"
# V-04: F5 validates the candidate tables against audit.yaml. The ZZZ override of PVOUT (a constant 4.5) is dropped because these
# tables carry a spread of PVOUT; the geometry is an elevation span of 0 to 1000 m inside a 10 degree box.
AUDIT = load_audit_config(REPO / "config" / "audit.yaml").model_copy(
    update={"country_overrides": {}}
)
GEOMETRY = CountryGeometry(z_min_m=0.0, z_max_m=1000.0, west=0.0, south=35.0, east=10.0, north=45.0)
RANGE_ARGS = {"audit_config": AUDIT, "geometry": GEOMETRY}

MEMBERS = ["m0", "m_gcmA_ssp245_2041-2070", "m_gcmB_ssp585_2071-2100"]
MASKED_CELL_INDEX = (
    3  # position in the central candidate set whose member MEMBERS[2] is declared masked
)
FACTORS = {  # member -> (delta_rsds, dT, delta_wind): round test values
    "m0": (1.0, 0.0, 1.0),
    MEMBERS[1]: (1.02, 1.5, 1.04),
    MEMBERS[2]: (0.98, 3.0, 0.95),
}
SCENARIO_AREAS = {  # eligible area of each of the 8 cells, km2
    "central": [10.0, 8.0, 6.0, 4.0, 12.0, 9.0, 7.0, 5.0],
    "restrictive": [5.0, 4.0, 3.0, 2.0, 6.0, 4.5, 3.5, 2.5],
    "permissive": [15.0, 12.0, 9.0, 6.0, 18.0, 13.5, 10.5, 7.5],
}
N_CELLS = 8
CELL_IDS = cell_id(np.full(N_CELLS, 1000), 2000 + np.arange(N_CELLS))
PVOUT = np.array([4.0, 4.5, 5.0, 5.5, 6.0, 5.2, 4.8, 5.8])  # kWh/kWp/day, test values
A100 = np.array([6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5])
A150, A200 = A100 * 1.08, A100 * 1.12
K100 = np.array([2.0, 2.1, 2.2, 2.3, 2.4, 2.0, 2.2, 2.4])
K150, K200 = K100 + 0.1, K100 + 0.2
RHO100 = np.linspace(1.10, 1.22, N_CELLS)
RHO150, RHO200 = RHO100 - 0.01, RHO100 - 0.02


def _candidates(scenario: str, technology_columns: dict[str, np.ndarray]) -> pd.DataFrame:
    area = np.array(SCENARIO_AREAS[scenario])
    frame = pd.DataFrame(
        {
            "cell_id": CELL_IDS,
            "row": 1000,
            "col": 2000 + np.arange(N_CELLS),
            "lat_c": 40.0,
            "lon_c": 10.0,
            "cell_area_km2": 25.0,
            "eligible_area_km2": area,
            **{f"excluded_area_km2_E{i}": 0.0 for i in range(1, 7)},
            "dominant_exclusion": None,
            "dist_grid_km": 5.0,
            "dist_road_km": 2.0,
            "dist_grid_capped_share": 0.0,
            "dist_road_capped_share": 0.0,
        }
    )
    for name, values in technology_columns.items():
        frame[name] = values
    return frame


def _write_inputs(root: Path, drop_forcing_rows: list[tuple[int, str]] = (), wind_override=None):
    """Candidate tables of the three scenarios for both technologies, forcing, forcing_masked and members.yaml."""
    land, climate = root / "land", root / "climate"
    land.mkdir(parents=True), climate.mkdir(parents=True)
    solar_cols = {"pvout_kwh_kwp_day": PVOUT}
    wind_cols = {}
    for h, a, k, rho in (
        (100, A100, K100, RHO100),
        (150, A150, K150, RHO150),
        (200, A200, K200, RHO200),
    ):
        wind_cols[f"weibull_a_{h}m"] = a
        wind_cols[f"weibull_k_{h}m"] = k
        wind_cols[f"air_density_{h}m"] = rho
    for scenario in SCENARIO_AREAS:
        _candidates(scenario, solar_cols).to_parquet(land / f"candidates_solar__{scenario}.parquet")
        _candidates(scenario, wind_cols).to_parquet(land / f"candidates_wind__{scenario}.parquet")
    # the F3 cell table holds every country cell: the candidates and two cells that are not candidates
    for tech, cols in (("solar", solar_cols), ("wind", wind_cols)):
        central = _candidates("central", cols)
        extra = central.iloc[:2].assign(
            cell_id=CELL_IDS[-1] + np.array([1, 2]), eligible_area_km2=0.0
        )
        pd.concat([central, extra], ignore_index=True).to_parquet(
            land / f"cells_{tech}__central.parquet"
        )
    rows, masked = [], []
    for member in MEMBERS:
        rsds, d_t, wind = FACTORS[member]
        for i, cid in enumerate(CELL_IDS):
            if member == MEMBERS[2] and i == MASKED_CELL_INDEX:
                masked.append(
                    {"cell_id": int(cid), "member": member, "delta_wind": 1.9, "reason": "test"}
                )
                continue
            if (i, member) in drop_forcing_rows:
                continue
            rows.append(
                {
                    "cell_id": int(cid),
                    "member": member,
                    "delta_rsds": rsds,
                    "dT": d_t,
                    "delta_wind": wind if wind_override is None else wind_override,
                }
            )
    pd.DataFrame(rows).to_parquet(climate / "forcing.parquet")
    pd.DataFrame(masked).to_parquet(climate / "forcing_masked.parquet")
    (climate / "members.yaml").write_text(
        yaml.safe_dump({"members": [{"member": m} for m in MEMBERS]}), encoding="utf-8"
    )
    return land, climate


@pytest.fixture(scope="module")
def registry():
    base = load_technologies(TECHNOLOGIES)
    wind = base.technologies["wind"].model_copy(
        update={
            "power_curves": {"synthetic": "synthetic_curve"},
            "iec_class_rule": [
                IecClassBound(iec_class="synthetic", mean_speed_upper_ms=None, source=None)
            ],
        }
    )
    return base.model_copy(update={"technologies": {**base.technologies, "wind": wind}})


@pytest.fixture(scope="module")
def synthetic_params() -> CountryParams:
    return load_parameters(PARAMETERS).countries["ZZZ"]


def _with(params: CountryParams, tech: str, key: str, value) -> CountryParams:
    data = params.model_dump(mode="json")
    data["technologies"][tech][key]["value"] = value
    return CountryParams.model_validate(data)


def _run(tmp_path, registry, params, drop=(), techs=("solar", "wind"), production=False):
    land, climate = _write_inputs(tmp_path / "in", drop)
    out = tmp_path / "out"
    summary = build_potential(
        "ZZZ",
        registry,
        params,
        list(techs),
        EXPERIMENTS,
        FIXTURE_CURVES,
        production=production,
        **RANGE_ARGS,
        candidates_dir=land,
        climate_dir=climate,
        out_dir=out,
    )
    return summary, out


@pytest.fixture(scope="module")
def run_ok(tmp_path_factory, registry, synthetic_params):
    return _run(tmp_path_factory.mktemp("f5"), registry, synthetic_params)


# -- outputs and values --------------------------------------------------------------------------


@pytest.mark.unit
def test_zzz_produces_the_potential_files_for_three_scenarios_and_the_aggregates(run_ok):
    summary, out = run_ok
    for tech in ("solar", "wind"):
        for scenario in ("central", "restrictive", "permissive"):
            path = out / f"potential_{tech}__{scenario}.parquet"
            assert path.is_file() and read_schema_version(path) == POTENTIAL_TABLE_SCHEMA_VERSION
            table = pd.read_parquet(path)
            assert list(table.columns) == ["cell_id", "member", "P_MW", "CF", "E_MWh"]
            assert table["P_MW"].dtype == "float64" and table["CF"].dtype == "float64"
        agg = pd.read_parquet(out / f"potential_aggregates_{tech}.parquet")
        assert len(agg) == 3 * len(MEMBERS)
        assert {"P_GW", "E_TWh", "P_GW_like_for_like", "E_TWh_like_for_like"} <= set(agg.columns)
    assert set(summary.technologies) == {"solar", "wind"}


@pytest.mark.unit
def test_solar_values_follow_the_method(run_ok, synthetic_params):
    _, out = run_ok
    table = pd.read_parquet(out / "potential_solar__central.parquet")
    gamma = synthetic_params.technologies.solar.gamma.value
    luf = synthetic_params.technologies.solar.luf.value
    density = synthetic_params.technologies.solar.power_density_mw_per_km2.value
    assert (gamma, luf, density) == (-0.005, 0.5, 10.0)
    for member, (rsds, d_t, _wind) in FACTORS.items():
        part = table[table["member"].astype(str) == member].sort_values("cell_id")
        keep = [i for i in range(N_CELLS) if not (member == MEMBERS[2] and i == MASKED_CELL_INDEX)]
        expected_cf = PVOUT[keep] / 24.0 * rsds * (1 + gamma * d_t)
        expected_p = np.array(SCENARIO_AREAS["central"])[keep] * luf * density
        np.testing.assert_allclose(part["CF"], expected_cf, rtol=1e-14)
        np.testing.assert_allclose(part["P_MW"], expected_p, rtol=1e-14)
        np.testing.assert_allclose(
            part["E_MWh"], expected_p * expected_cf * HOURS_PER_YEAR, rtol=1e-14
        )


@pytest.mark.unit
def test_wind_values_follow_the_method(run_ok, synthetic_params):
    _, out = run_ok
    table = pd.read_parquet(out / "potential_wind__central.parquet")
    eta = synthetic_params.technologies.wind.eta_loss.value
    hub = synthetic_params.technologies.wind.hub_height_m.value
    curve = load_power_curve(FIXTURE_CURVES / "synthetic_curve.yaml")
    a_h, k_h, rho_h = resource_at_hub_height(
        {100: A100, 150: A150, 200: A200},
        {100: K100, 150: K150, 200: K200},
        {100: RHO100, 150: RHO150, 200: RHO200},
        hub,
    )
    a_eq = equivalent_scale(a_h, rho_h, RHO0_KG_M3)
    for member, (_r, _t, wind) in FACTORS.items():
        part = table[table["member"].astype(str) == member].sort_values("cell_id")
        keep = [i for i in range(N_CELLS) if not (member == MEMBERS[2] and i == MASKED_CELL_INDEX)]
        expected = wind_cf_member(a_eq[keep], k_h[keep], np.full(len(keep), wind), curve, eta)
        np.testing.assert_allclose(part["CF"], expected, rtol=1e-13)
    assert hub == 125.0


@pytest.mark.unit
def test_reference_member_is_the_unperturbed_cf(run_ok):
    _, out = run_ok
    table = pd.read_parquet(out / "potential_solar__central.parquet")
    m0 = table[table["member"].astype(str) == "m0"].sort_values("cell_id")
    np.testing.assert_allclose(m0["CF"], PVOUT / 24.0, rtol=1e-14)


# -- masked cell-members (M-F4-07, D-F5-006) ------------------------------------------------------


@pytest.mark.unit
def test_declared_masked_cell_member_has_no_row_and_is_counted(run_ok):
    _, out = run_ok
    for tech in ("solar", "wind"):
        table = pd.read_parquet(out / f"potential_{tech}__central.parquet")
        masked_cell = int(CELL_IDS[MASKED_CELL_INDEX])
        member_rows = table[table["member"].astype(str) == MEMBERS[2]]
        assert masked_cell not in set(member_rows["cell_id"])
        assert masked_cell in set(table[table["member"].astype(str) == "m0"]["cell_id"])
        assert len(table) == len(MEMBERS) * N_CELLS - 1
        agg = pd.read_parquet(out / f"potential_aggregates_{tech}.parquet")
        row = agg[(agg["scenario"] == "central") & (agg["member"] == MEMBERS[2])].iloc[0]
        assert (row["n_cells"], row["n_cells_absent"], row["n_cells_like_for_like"]) == (7, 1, 7)
        meta = json.loads(
            pq.read_schema(out / f"potential_{tech}__central.parquet").metadata[
                PROVENANCE_KEY.encode()
            ]
        )
        assert meta["absent_cell_members"] == {MEMBERS[2]: 1}


@pytest.mark.unit
def test_like_for_like_series_excludes_the_masked_cell_and_the_climate_effect_uses_it(run_ok):
    _, out = run_ok
    table = pd.read_parquet(out / "potential_solar__central.parquet")
    agg = pd.read_parquet(out / "potential_aggregates_solar.parquet")
    agg = agg[agg["scenario"] == "central"].set_index("member")
    masked_cell = int(CELL_IDS[MASKED_CELL_INDEX])
    kept = table[table["cell_id"] != masked_cell]
    for member in MEMBERS:
        e_lfl = kept[kept["member"].astype(str) == member]["E_MWh"].sum() / 1e6
        assert agg.loc[member, "E_TWh_like_for_like"] == pytest.approx(e_lfl, rel=1e-13)
        all_present = table[table["member"].astype(str) == member]["E_MWh"].sum() / 1e6
        assert agg.loc[member, "E_TWh"] == pytest.approx(all_present, rel=1e-13)
    assert (
        agg.loc["m0", "E_TWh"] > agg.loc["m0", "E_TWh_like_for_like"]
    )  # m0 keeps the masked cell in the all-present series
    expected = 100 * (
        agg.loc[MEMBERS[2], "E_TWh_like_for_like"] / agg.loc["m0", "E_TWh_like_for_like"] - 1
    )
    assert agg.loc[MEMBERS[2], "delta_E_pct_vs_m0_like_for_like"] == pytest.approx(
        expected, rel=1e-13
    )
    assert agg.loc["m0", "delta_E_pct_vs_m0_like_for_like"] == pytest.approx(0.0, abs=1e-12)


@pytest.mark.unit
def test_aggregate_scenario_hand_example():
    p = np.array([10.0, 20.0, 30.0])
    area = np.array([1.0, 2.0, 3.0])
    energy = {
        "m0": np.array([100.0, 200.0, 300.0]) * 1e6,
        "m1": np.array([110.0, np.nan, 330.0]) * 1e6,
    }
    agg = aggregate_scenario("s", ["m0", "m1"], p, area, energy, "m0", 8760.0).set_index("member")
    assert agg.loc["m1", "n_cells"] == 2 and agg.loc["m1", "n_cells_absent"] == 1
    assert agg.loc["m1", "P_GW"] == pytest.approx(0.040) and agg.loc[
        "m1", "E_TWh"
    ] == pytest.approx(440.0)
    assert agg.loc["m0", "P_GW_like_for_like"] == pytest.approx(0.040)
    assert agg.loc["m1", "delta_E_pct_vs_m0_like_for_like"] == pytest.approx(10.0)
    assert agg.loc["m1", "eligible_area_km2"] == pytest.approx(4.0)
    assert agg.loc["m0", "cf_energy_weighted"] == pytest.approx(600e6 / (60.0 * 8760.0))


@pytest.mark.unit
def test_an_undeclared_absence_raises_before_anything_is_written(
    tmp_path, registry, synthetic_params
):
    with pytest.raises(ForcingContractError, match="neither in forcing.parquet nor declared"):
        _run(tmp_path, registry, synthetic_params, drop=[(1, MEMBERS[1])])
    assert not list((tmp_path / "out").glob("*")) if (tmp_path / "out").exists() else True


@pytest.mark.unit
def test_wind_factor_out_of_range_in_a_candidate_cell_raises(tmp_path, registry, synthetic_params):
    land, climate = _write_inputs(tmp_path / "in", wind_override=1.8)
    with pytest.raises(ForcingContractError, match="outside"):
        build_potential(
            "ZZZ", registry, synthetic_params, ["solar"], EXPERIMENTS, FIXTURE_CURVES,
            candidates_dir=land, climate_dir=climate, out_dir=tmp_path / "out", **RANGE_ARGS,
        )  # fmt: skip
    assert not (tmp_path / "out").exists() or not list((tmp_path / "out").iterdir())


# -- V-03 invariants ------------------------------------------------------------------------------


@pytest.mark.unit
def test_invariants_cf_range_capacity_constant_across_members_and_sum_equals_aggregate(run_ok):
    _, out = run_ok
    for tech in ("solar", "wind"):
        agg = pd.read_parquet(out / f"potential_aggregates_{tech}.parquet")
        for scenario, area in SCENARIO_AREAS.items():
            table = pd.read_parquet(out / f"potential_{tech}__{scenario}.parquet")
            assert ((table["CF"] >= 0) & (table["CF"] <= 1)).all()
            per_cell = table.groupby("cell_id")["P_MW"].nunique()
            assert (per_cell == 1).all()  # P_MW is the same in every member of a cell
            assert (np.array(area) <= 25.0).all()  # eligible_area <= cell_area of the candidates
            m0 = table[table["member"].astype(str) == "m0"]
            row = agg[(agg["scenario"] == scenario) & (agg["member"] == "m0")].iloc[0]
            assert row["P_GW"] * 1e3 == pytest.approx(
                m0["P_MW"].sum(), rel=1e-13
            )  # country = sum of cells
            assert row["E_TWh"] * 1e6 == pytest.approx(m0["E_MWh"].sum(), rel=1e-13)


@pytest.mark.unit
def test_land_range_is_ordered_across_scenarios(run_ok):
    _, out = run_ok
    agg = pd.read_parquet(out / "potential_aggregates_solar.parquet")
    p = agg[agg["member"] == "m0"].set_index("scenario")["P_GW"]
    assert p["restrictive"] < p["central"] < p["permissive"]


@pytest.mark.unit
def test_a_capacity_factor_above_one_raises(tmp_path, registry, synthetic_params):
    land, climate = _write_inputs(tmp_path / "in")
    path = land / "candidates_solar__central.parquet"
    frame = pd.read_parquet(path)
    frame.loc[0, "pvout_kwh_kwp_day"] = 30.0  # CF0 = 1.25
    frame.to_parquet(path)
    # the range check of V-04 stops 30 first; widen the PVOUT range here to reach the capacity-factor guard behind it
    wide = AUDIT.model_copy(
        update={
            "layers": {
                **AUDIT.layers,
                "solar": AUDIT.layers["solar"].model_copy(update={"sanity_range": (0.0, 40.0)}),
            }
        }
    )
    with pytest.raises(CfModelError, match="outside \\[0, 1\\]"):
        build_potential(
            "ZZZ", registry, synthetic_params, ["solar"], EXPERIMENTS, FIXTURE_CURVES,
            candidates_dir=land, climate_dir=climate, out_dir=tmp_path / "out",
            audit_config=wide, geometry=GEOMETRY,
        )  # fmt: skip


@pytest.mark.unit
def test_a_hub_height_outside_the_data_heights_raises(tmp_path, registry, synthetic_params):
    params = _with(synthetic_params, "wind", "hub_height_m", 250.0)
    with pytest.raises(HubHeightError, match="does not extrapolate"):
        _run(tmp_path, registry, params, techs=("wind",))


# -- provenance metadata (A-02, D-F5-009, D-F5-010) ------------------------------------------------


@pytest.mark.unit
def test_table_metadata_records_the_parameters_curve_hash_and_that_c2_is_not_applied(run_ok):
    _, out = run_ok
    meta = json.loads(
        pq.read_schema(out / "potential_wind__central.parquet").metadata[PROVENANCE_KEY.encode()]
    )
    assert meta["c2_applied"] is False and meta["scenario"] == "central"
    assert meta["parameters"]["hub_height_m"] == 125.0
    assert meta["rho0_kg_m3"] == RHO0_KG_M3 and meta["hours_per_year"] == HOURS_PER_YEAR
    assert meta["integration"].startswith("exact_piecewise_linear")
    assert len(meta["curve_sha256"]["synthetic_curve"]) == 64


# -- fail loud (A-09) -----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("iso", ["BRA", "PRT", "IND"])
def test_real_countries_fail_loud_listing_the_missing_parameters_and_write_nothing(iso, tmp_path):
    technologies = load_technologies(TECHNOLOGIES)
    params = load_parameters(PARAMETERS).countries[iso]
    with pytest.raises(MissingParameterError) as caught:
        build_potential(
            iso,
            technologies,
            params,
            ["solar", "wind"],
            EXPERIMENTS,
            REAL_CURVES_DIR,
            out_dir=tmp_path / "out",
            **RANGE_ARGS,
        )
    message = str(caught.value)
    for item in (
        "luf",
        "power_density_mw_per_km2",
        "gamma",
        "eta_loss",
        "hub_height_m",
        "power curve",
        "iec_class_rule",
    ):
        assert item in message, item
    assert "pending_research" in message
    assert not (tmp_path / "out").exists()


@pytest.mark.unit
def test_missing_parameter_error_is_raised_before_inputs_are_read(tmp_path):
    """No candidate, forcing or members file exists here, and the error is still the parameter one."""
    technologies = load_technologies(TECHNOLOGIES)
    params = load_parameters(PARAMETERS).countries["PRT"]
    with pytest.raises(MissingParameterError):
        build_potential(
            "PRT", technologies, params, ["wind"], EXPERIMENTS, REAL_CURVES_DIR,
            candidates_dir=tmp_path / "none", climate_dir=tmp_path / "none", out_dir=tmp_path / "out",
            **RANGE_ARGS,
        )  # fmt: skip


@pytest.mark.unit
def test_a_synthetic_curve_is_refused_in_a_production_run(tmp_path, registry, synthetic_params):
    with pytest.raises(SyntheticCurveError, match="production"):
        _run(tmp_path, registry, synthetic_params, techs=("wind",), production=True)


@pytest.mark.unit
def test_a_missing_curve_file_is_reported_as_missing(tmp_path, registry, synthetic_params):
    wind = registry.technologies["wind"].model_copy(
        update={"power_curves": {"synthetic": "absent_curve"}}
    )
    reg = registry.model_copy(update={"technologies": {**registry.technologies, "wind": wind}})
    land, climate = _write_inputs(tmp_path / "in")
    with pytest.raises(MissingParameterError, match="absent_curve.yaml"):
        build_potential(
            "ZZZ", reg, synthetic_params, ["wind"], EXPERIMENTS, FIXTURE_CURVES,
            candidates_dir=land, climate_dir=climate, out_dir=tmp_path / "out", **RANGE_ARGS,
        )  # fmt: skip


@pytest.mark.unit
def test_unknown_cf_model_and_undeclared_required_parameter_raise(
    tmp_path, registry, synthetic_params
):
    with pytest.raises(CfModelError, match="unknown cf_model"):
        get_cf_model("no_such_model")
    solar = registry.technologies["solar"].model_copy(update={"required_parameters": ["luf"]})
    reg = registry.model_copy(update={"technologies": {**registry.technologies, "solar": solar}})
    with pytest.raises(CfModelError, match="not in required_parameters"):
        _run(tmp_path, reg, synthetic_params, techs=("solar",))


@pytest.mark.unit
def test_registry_resource_layers_are_the_columns_f3_writes():
    """A-04: the registry names the same resource columns as the F3 candidate tables (it had swapped comments and no suffix)."""
    technologies = load_technologies(TECHNOLOGIES).technologies
    assert technologies["solar"].resource_layers == ["pvout_kwh_kwp_day"]
    expected = {
        f"{p}_{h}m" for p in ("weibull_a", "weibull_k", "air_density") for h in WIND_HEIGHTS_M
    }
    assert set(technologies["wind"].resource_layers) == expected
    assert set(CF_MODELS) == {technologies[t].cf_model for t in technologies}


# -- IEC class rule (D-F5-004) -----------------------------------------------------------------------


def _rule(*bounds: float | None) -> list[IecClassBound]:
    return [
        IecClassBound(iec_class=f"c{i}", mean_speed_upper_ms=b, source=None)
        for i, b in enumerate(bounds)
    ]


@pytest.mark.unit
def test_class_follows_the_mean_speed_with_the_last_class_unbounded():
    rule = _rule(6.0, 8.0, None)  # c0 up to 6 m/s, c1 up to 8 m/s, c2 above
    speeds = np.array([5.0, 6.0, 6.1, 8.0, 8.1, 12.0])
    assert assign_by_mean_speed(speeds, rule).tolist() == [0, 0, 1, 1, 2, 2]
    assert (
        assign_by_mean_speed(speeds, _rule(None)).tolist() == [0] * 6
    )  # one class takes every cell


@pytest.mark.unit
def test_class_rule_rejects_malformed_rules():
    with pytest.raises(IecClassError, match="empty"):
        assign_by_mean_speed(np.array([5.0]), [])
    with pytest.raises(IecClassError, match="only the last class"):
        assign_by_mean_speed(np.array([5.0]), _rule(6.0, 8.0))  # no unbounded class
    with pytest.raises(IecClassError, match="only the last class"):
        assign_by_mean_speed(np.array([5.0]), _rule(None, 8.0, None))
    with pytest.raises(IecClassError, match="strictly increasing"):
        assign_by_mean_speed(np.array([5.0]), _rule(8.0, 6.0, None))
    with pytest.raises(IecClassError, match="not finite"):
        assign_by_mean_speed(np.array([np.nan]), _rule(None))


@pytest.mark.unit
def test_registry_rule_and_curves_must_name_the_same_classes():
    base = {
        "resource_layers": [],
        "cf_model": "m",
        "exclusions": [],
        "cost_drivers": [],
        "uncertain_parameters": [],
    }
    ok = TechnologyConfig.model_validate(
        {
            **base,
            "power_curves": {"c0": "x"},
            "iec_class_rule": [{"iec_class": "c0", "mean_speed_upper_ms": None, "source": None}],
        }
    )
    assert ok.iec_class_rule[0].iec_class == "c0"
    with pytest.raises(ValueError, match="same distinct classes"):
        TechnologyConfig.model_validate(
            {
                **base,
                "power_curves": {"c9": "x"},
                "iec_class_rule": [
                    {"iec_class": "c0", "mean_speed_upper_ms": None, "source": None}
                ],
            }
        )


@pytest.mark.unit
def test_the_real_registry_holds_no_threshold_until_oq_005_closes():
    """D-F5-017: the thresholds are the author's to source; no number is in `technologies.yaml` and none in a curve file."""
    wind = load_technologies(TECHNOLOGIES).technologies["wind"]
    assert wind.iec_class_rule is None and wind.power_curves is None
    assert "mean_speed_upper_ms" not in FIXTURE_CURVES.joinpath("synthetic_curve.yaml").read_text(
        encoding="utf-8"
    )


# -- A-04: no technology name in the package -------------------------------------------------------


@pytest.mark.unit
def test_no_technology_name_appears_in_technical_potential():
    """A-04: F5 code contains no technology names; a string literal equal to a registry technology key fails the test."""
    names = set(load_technologies(TECHNOLOGIES).technologies)
    offenders = []
    for path in sorted((REPO / "src" / "geofrea" / "technical_potential").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value.strip().lower() in names
            ):
                offenders.append((path.name, node.lineno, node.value))
            if isinstance(node, ast.Name | ast.Attribute):
                ident = node.id if isinstance(node, ast.Name) else node.attr
                if ident.lower() in names:
                    offenders.append((path.name, node.lineno, ident))
    assert not offenders, offenders


@pytest.mark.unit
def test_a_technology_without_candidate_cells_gives_empty_tables_and_zero_totals(
    tmp_path, registry, synthetic_params
):
    """A scenario with no candidate cells is a valid zero potential, written as an empty table and zero aggregates."""
    land, climate = _write_inputs(tmp_path / "in")
    for scenario in SCENARIO_AREAS:
        path = land / f"candidates_solar__{scenario}.parquet"
        pd.read_parquet(path).iloc[0:0].to_parquet(path)
    out = tmp_path / "out"
    summary = build_potential(
        "ZZZ", registry, synthetic_params, ["solar"], EXPERIMENTS, FIXTURE_CURVES,
        candidates_dir=land, climate_dir=climate, out_dir=out, **RANGE_ARGS,
    )  # fmt: skip
    assert summary.technologies["solar"].scenarios["central"].n_rows == 0
    assert len(pd.read_parquet(out / "potential_solar__central.parquet")) == 0
    agg = pd.read_parquet(out / "potential_aggregates_solar.parquet")
    assert (agg["P_GW"] == 0).all() and (agg["E_TWh"] == 0).all() and (agg["n_cells"] == 0).all()
    assert (
        agg["cf_energy_weighted"].isna().all()
        and agg["delta_E_pct_vs_m0_like_for_like"].isna().all()
    )


# -- V-04: F5 validates its inputs against audit.yaml --------------------------------------------


def _corrupt(land: Path, tech: str, column: str, value, rows=(0,)) -> None:
    for scenario in SCENARIO_AREAS:
        path = land / f"candidates_{tech}__{scenario}.parquet"
        frame = pd.read_parquet(path)
        frame.loc[list(rows), column] = value
        frame.to_parquet(path)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("tech", "column", "value", "range_text"),
    [
        (
            "solar",
            "pvout_kwh_kwp_day",
            450.0,
            "layers.solar.sanity_range",
        ),  # W/m2 read as kWh/kWp/day
        ("wind", "air_density_100m", 12.25, "derived_ranges.air_density"),  # a factor of 10
        ("wind", "air_density_200m", 0.2, "derived_ranges.air_density"),
        ("solar", "dist_grid_km", 99999.0, "derived_ranges.dist_grid_km"),
        ("wind", "dist_road_km", -3.0, "derived_ranges.dist_road_km"),
        ("wind", "air_density_150m", np.nan, "derived_ranges.air_density"),
    ],
)
def test_an_input_outside_its_sanity_range_raises_a_named_error_and_writes_nothing(
    tmp_path, registry, synthetic_params, tech, column, value, range_text
):
    land, climate = _write_inputs(tmp_path / "in")
    _corrupt(land, tech, column, value, rows=(0, 2))
    with pytest.raises(InputRangeError) as caught:
        build_potential(
            "ZZZ", registry, synthetic_params, [tech], EXPERIMENTS, FIXTURE_CURVES,
            candidates_dir=land, climate_dir=climate, out_dir=tmp_path / "out", **RANGE_ARGS,
        )  # fmt: skip
    message = str(caught.value)
    assert column in message and "2 of 8 candidate cells" in message
    assert f"ZZZ {tech} [" in message and "nothing was computed" in message
    assert (
        range_text.replace("derived_ranges.", "derived_ranges.") in message
        or "audit.yaml" in message
    )
    assert not (tmp_path / "out").exists() or not list((tmp_path / "out").iterdir())


@pytest.mark.unit
def test_every_layer_outside_its_range_is_listed_in_one_error(tmp_path, registry, synthetic_params):
    land, climate = _write_inputs(tmp_path / "in")
    _corrupt(land, "wind", "air_density_100m", 9.0)
    _corrupt(land, "wind", "dist_grid_km", 1e6)
    with pytest.raises(InputRangeError) as caught:
        build_potential(
            "ZZZ", registry, synthetic_params, ["wind"], EXPERIMENTS, FIXTURE_CURVES,
            candidates_dir=land, climate_dir=climate, out_dir=tmp_path / "out", **RANGE_ARGS,
        )  # fmt: skip
    assert "air_density_100m" in str(caught.value) and "dist_grid_km" in str(caught.value)


@pytest.mark.unit
def test_weibull_layers_without_a_range_warn_and_do_not_raise(
    tmp_path, registry, synthetic_params, caplog
):
    """Weibull A and k have no range yet (OQ-053): F5 does not range-check them and warns, naming the open question."""
    land, climate = _write_inputs(tmp_path / "in")
    _corrupt(
        land, "wind", "weibull_a_100m", 5000.0
    )  # a wild value: no range, so no error from the range check
    with caplog.at_level("WARNING", logger="geofrea.technical_potential.input_ranges"):
        build_potential(
            "ZZZ", registry, synthetic_params, ["wind"], EXPERIMENTS, FIXTURE_CURVES,
            candidates_dir=land, climate_dir=climate, out_dir=tmp_path / "out", **RANGE_ARGS,
        )  # fmt: skip
    text = caplog.text
    for column in ("weibull_a_100m", "weibull_k_150m", "weibull_a_200m"):
        assert column in text
    assert (
        text.count("weibull_a_100m has no sanity range") == 1
    )  # once per technology, not once per scenario
    assert "OQ-053" in text and "air_density_100m has no" not in text


@pytest.mark.unit
def test_a_registry_layer_with_no_declared_range_is_an_error():
    with pytest.raises(InputRangeError, match="not a layer with a sanity range"):
        resolve_input_ranges("ZZZ", AUDIT, GEOMETRY, ["wind_speed_100m"])


@pytest.mark.unit
def test_the_range_check_uses_the_zzz_pvout_override_for_zzz_and_the_product_range_otherwise():
    real = load_audit_config(REPO / "config" / "audit.yaml")
    zzz = resolve_input_ranges("ZZZ", real, GEOMETRY, ["pvout_kwh_kwp_day"])["pvout_kwh_kwp_day"]
    prt = resolve_input_ranges("PRT", real, GEOMETRY, ["pvout_kwh_kwp_day"])["pvout_kwh_kwp_day"]
    assert (zzz.low, zzz.high) == (4.5, 4.5) and (prt.low, prt.high) == (0.7, 6.8)


@pytest.mark.unit
def test_a_mean_equal_to_a_bound_up_to_floating_point_rounding_passes_and_a_real_excess_does_not():
    """The synthetic PVOUT range is one value, [4.5, 4.5]; an area-weighted mean of it differs from 4.5 by rounding only."""
    zzz = load_audit_config(REPO / "config" / "audit.yaml")
    ranges = resolve_input_ranges("ZZZ", zzz, GEOMETRY, ["pvout_kwh_kwp_day"])
    frame = pd.DataFrame({"cell_id": [1, 2], "pvout_kwh_kwp_day": [4.5 + 4e-16 * 4.5, 4.5 - 1e-13]})
    validate_candidates("ZZZ", "solar", "central", frame, ranges)
    frame["pvout_kwh_kwp_day"] = [4.5, 4.5001]
    with pytest.raises(InputRangeError, match="1 of 2 candidate cells"):
        validate_candidates("ZZZ", "solar", "central", frame, ranges)
