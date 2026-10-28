"""F5 end to end on a synthetic country (A-06, D-F5-013), the masked-cell contract (M-F4-07), V-03 invariants, fail-loud inputs, A-04.

The candidate tables are built here in the shape of the F3 output; the forcing is built here with round, known factors and one
declared masked cell-member (D13, option a). The parameters are the synthetic country's test values of `config/parameters.json`.
"""

from __future__ import annotations

import ast
import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
import rasterio
import yaml

from geofrea.climate_forcing.forcing import ForcingContractError
from geofrea.core.config_loader import load_audit_config, load_parameters, load_technologies
from geofrea.core.config_schemas import ClassFlagRule, TechnologyConfig
from geofrea.core.constants import (
    CELL_DEG,
    CELL_NESTING_PIXELS,
    CELL_ORIGIN_LAT,
    CELL_ORIGIN_LON,
    HOURS_PER_YEAR,
    ISA_T0_K,
    RHO0_KG_M3,
)
from geofrea.core.schemas import CountryParams
from geofrea.core.tables import read_schema_version
from geofrea.land_eligibility.cells import cell_id, eligible_fraction_file, pixel_row_area_km2
from geofrea.land_eligibility.pipeline import WIND_HEIGHTS_M
from geofrea.siting_layers.sanity import CountryGeometry
from geofrea.technical_potential.aggregates import aggregate_scenario
from geofrea.technical_potential.cf_models import (
    CF_MODELS,
    CfModelError,
    MissingParameterError,
    get_cf_model,
)
from geofrea.technical_potential.iec_class import IecClassError, exceeds_class
from geofrea.technical_potential.input_ranges import (
    InputRangeError,
    resolve_input_ranges,
    validate_candidates,
)
from geofrea.technical_potential.pipeline import PROVENANCE_KEY, build_potential
from geofrea.technical_potential.pixel_inputs import PixelInputError
from geofrea.technical_potential.power_curve import SyntheticCurveError, load_power_curve
from geofrea.technical_potential.table_schemas import POTENTIAL_TABLE_SCHEMA_VERSION
from geofrea.technical_potential.weibull_cf import weibull_mean_speed, wind_cf_member
from geofrea.technical_potential.wind_profile import HubHeightError, resource_at_hub_height

REPO = Path(__file__).resolve().parents[2]
PARAMETERS = REPO / "config" / "parameters.json"
TECHNOLOGIES = REPO / "config" / "technologies.yaml"
_REAL_EXPERIMENTS = REPO / "config" / "experiments.yaml"
# The real configuration excludes the wind cells above 3,000 m in F3 (OQ-058), so F5 has no altitude-sensitivity rows. The machinery that writes
# those rows (`central__below_<m>m`) is still part of F5 and is exercised on a copy of the configuration that reports the sensitivity instead.
_SENSITIVITY_TEXT = (
    _REAL_EXPERIMENTS.read_text(encoding="utf-8")
    .replace("\r\n", "\n")
    .replace(
        "nominal: 3000.0\n        sensitivity: null", "nominal: null\n        sensitivity: 3000.0"
    )
)
assert "sensitivity: 3000.0" in _SENSITIVITY_TEXT
EXPERIMENTS = Path(tempfile.mkdtemp(prefix="geofrea_f5_exp_")) / "experiments.yaml"
EXPERIMENTS.write_text(_SENSITIVITY_TEXT, encoding="utf-8")
REAL_CURVES_DIR = REPO / "config" / "turbines"
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
FLAG_THRESHOLD_MS = 7.0  # class limit of the synthetic registry: the windiest cells of the test world exceed it
CELL_IDS = cell_id(np.full(N_CELLS, 1000), 2000 + np.arange(N_CELLS))
PVOUT = np.array([4.0, 4.5, 5.0, 5.5, 6.0, 5.2, 4.8, 5.8])  # kWh/kWp/day, test values
A100 = np.array([6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5])
A150, A200 = A100 * 1.08, A100 * 1.12
K100 = np.array([2.0, 2.1, 2.2, 2.3, 2.4, 2.0, 2.2, 2.4])
K150, K200 = K100 + 0.1, K100 + 0.2
RHO100 = np.linspace(1.10, 1.22, N_CELLS)
RHO150, RHO200 = RHO100 - 0.01, RHO100 - 0.02
ELEVATION = np.linspace(
    100.0, 3500.0, N_CELLS
)  # the last two cells are above the 3000 m of the wind sensitivity (OQ-058)

# The pixels of the 8 cells (D-F5-038): 5 x 5 pixels per cell on the lattice, the same eligible fraction in every pixel of a cell (so that the
# pixel weights add up to the eligible area of the table), and a spread of the resources across the five columns of a cell that averages to the
# cell value in every row (the weight is the same along a row): the cell means of the tables are the true means of the pixels, and the capacity
# factor of a cell is not the capacity factor of its means.
K_PIX = CELL_NESTING_PIXELS
PIXEL_DEG = CELL_DEG / K_PIX
SPREAD = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
SPREAD_BY_PRODUCT = {"weibull_a": 0.06, "weibull_k": 0.04, "air_density": 0.01}
PIXEL_TRANSFORM = rasterio.Affine(
    PIXEL_DEG,
    0.0,
    CELL_ORIGIN_LON + 2000 * CELL_DEG,
    0.0,
    -PIXEL_DEG,
    CELL_ORIGIN_LAT - 1000 * CELL_DEG,
)
CELL_VALUES = {
    "weibull_a": {100: A100, 150: A150, 200: A200},
    "weibull_k": {100: K100, 150: K150, 200: K200},
    "air_density": {100: RHO100, 150: RHO150, 200: RHO200},
}


def _pixel_resource(product: str, height_m: int) -> np.ndarray:
    """(5, 40) pixels of one wind layer: the value of the cell times `1 + spread * [-2, -1, 0, 1, 2]` along the columns of each cell."""
    factor = 1.0 + SPREAD_BY_PRODUCT[product] * np.tile(SPREAD, N_CELLS)
    return np.tile(np.repeat(CELL_VALUES[product][height_m], K_PIX) * factor, (K_PIX, 1))


def _pixel_fraction(scenario: str) -> np.ndarray:
    area = pixel_row_area_km2(PIXEL_TRANSFORM, K_PIX)
    per_cell = np.array(SCENARIO_AREAS[scenario]) / area.sum() / K_PIX
    return np.tile(np.repeat(per_cell, K_PIX), (K_PIX, 1))


def _write_pixels(land: Path) -> None:
    def write(path: Path, grid: np.ndarray) -> None:
        with rasterio.open(
            path, "w", driver="GTiff", dtype="float32", count=1, nodata=-9999.0, crs="EPSG:4326",
            transform=PIXEL_TRANSFORM, height=grid.shape[0], width=grid.shape[1],
        ) as dst:  # fmt: skip
            dst.write(grid.astype("float32"), 1)

    for scenario in SCENARIO_AREAS:
        write(land / eligible_fraction_file("wind", scenario), _pixel_fraction(scenario))
    for product, by_height in CELL_VALUES.items():
        for height in by_height:
            write(land / f"{product}_{height}m.tif", _pixel_resource(product, height))


def _expected_wind_cf(
    scenario: str, d_t: float, delta_wind: float, params: CountryParams
) -> np.ndarray:
    """Capacity factor of the 8 cells computed here, outside the pipeline: the model on each pixel, then the eligible-area-weighted mean."""
    eta = params.technologies.wind.eta_loss.value
    hub = params.technologies.wind.hub_height_m.value
    curve = load_power_curve(FIXTURE_CURVES / "synthetic_curve.yaml")
    layers = {
        product: {
            h: _pixel_resource(product, h).astype("float32").astype("float64").ravel()
            for h in (100, 150, 200)
        }
        for product in CELL_VALUES
    }
    a_h, k_h, rho_h = resource_at_hub_height(
        layers["weibull_a"], layers["weibull_k"], layers["air_density"], hub
    )
    n = a_h.size
    cf = wind_cf_member(
        a_h, k_h, rho_h, np.full(n, d_t), np.full(n, delta_wind), curve, eta, RHO0_KG_M3, ISA_T0_K
    )
    weight = (
        _pixel_fraction(scenario).astype("float32").astype("float64")
        * pixel_row_area_km2(PIXEL_TRANSFORM, K_PIX)[:, None]
    ).ravel()
    cell_of = np.tile(np.repeat(np.arange(N_CELLS), K_PIX), K_PIX)
    return np.bincount(cell_of, weights=weight * cf, minlength=N_CELLS) / np.bincount(
        cell_of, weights=weight, minlength=N_CELLS
    )


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
            "elevation_m": ELEVATION,
        }
    )
    for name, values in technology_columns.items():
        frame[name] = values
    return frame


def _write_inputs(
    root: Path,
    drop_forcing_rows: list[tuple[int, str]] = (),
    wind_override=None,
    no_wind: tuple[str, ...] = (),
):
    """Candidate tables of the three scenarios for both technologies, forcing, forcing_masked and members.yaml."""
    land, climate = root / "land", root / "climate"
    land.mkdir(parents=True), climate.mkdir(parents=True)
    _write_pixels(land)
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
            delta_wind = wind if wind_override is None else wind_override
            if (
                member == MEMBERS[2] and i == MASKED_CELL_INDEX
            ):  # masked (M-F4-07): the row stays, the wind ratio is NaN and declared
                masked.append(
                    {"cell_id": int(cid), "member": member, "delta_wind": 1.9, "reason": "test"}
                )
                delta_wind = np.nan
            if (
                member in no_wind
            ):  # no wind channel (M-F4-02 item 6): NaN everywhere, declared by `members.yaml`
                delta_wind = np.nan
            if (i, member) in drop_forcing_rows:
                continue
            rows.append(
                {
                    "cell_id": int(cid),
                    "member": member,
                    "delta_rsds": rsds,
                    "dT": d_t,
                    "delta_wind": delta_wind,
                }
            )
    pd.DataFrame(rows).to_parquet(climate / "forcing.parquet")
    pd.DataFrame(masked).to_parquet(climate / "forcing_masked.parquet")
    (climate / "members.yaml").write_text(
        yaml.safe_dump(
            {
                "members": [
                    {
                        "member": m,
                        "channels": {
                            "resource_rsds": True,
                            "resource_tas": True,
                            "resource_wind": m not in no_wind,
                            "hazard": False,
                        },
                    }
                    for m in MEMBERS
                ]
            }
        ),
        encoding="utf-8",
    )
    return land, climate


@pytest.fixture(scope="module")
def registry():
    base = load_technologies(TECHNOLOGIES)
    wind = base.technologies["wind"].model_copy(
        update={
            "power_curve": "synthetic_curve",
            "class_flag": ClassFlagRule(
                iec_class="synthetic",
                mean_speed_threshold_ms=FLAG_THRESHOLD_MS,
                layer_height_m=100.0,
                source=None,
            ),
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


def _run(
    tmp_path, registry, params, drop=(), techs=("solar", "wind"), production=False, no_wind=()
):
    land, climate = _write_inputs(tmp_path / "in", drop, no_wind=no_wind)
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
        siting_dir=land,
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
        # wind also has the rows without the cells above its altitude sensitivity (OQ-058), solar has none
        assert len(agg) == (4 if tech == "wind" else 3) * len(MEMBERS)
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
        keep = list(
            range(N_CELLS)
        )  # solar does not read the wind ratio: the wind-masked cell-member keeps its row
        expected_cf = PVOUT[keep] / 24.0 * rsds * (1 + gamma * d_t)
        expected_p = np.array(SCENARIO_AREAS["central"])[keep] * luf * density
        np.testing.assert_allclose(part["CF"], expected_cf, rtol=1e-14)
        np.testing.assert_allclose(part["P_MW"], expected_p, rtol=1e-14)
        np.testing.assert_allclose(
            part["E_MWh"], expected_p * expected_cf * HOURS_PER_YEAR, rtol=1e-14
        )


@pytest.mark.unit
def test_wind_values_follow_the_method(run_ok, synthetic_params):
    """M-F5-03, D-F5-038: the model on every pixel, the cell value the eligible-area-weighted mean of the pixel values."""
    _, out = run_ok
    table = pd.read_parquet(out / "potential_wind__central.parquet")
    hub = synthetic_params.technologies.wind.hub_height_m.value
    for member, (_r, d_t, wind) in FACTORS.items():
        part = table[table["member"].astype(str) == member].sort_values("cell_id")
        keep = [i for i in range(N_CELLS) if not (member == MEMBERS[2] and i == MASKED_CELL_INDEX)]
        # the density of the member follows the warming: rho = rho_ref T* / (T* + dT); the output is not rescaled again
        expected = _expected_wind_cf("central", d_t, wind, synthetic_params)[keep]
        np.testing.assert_allclose(part["CF"], expected, rtol=1e-12)
    assert hub == 125.0


@pytest.mark.unit
def test_the_wind_capacity_factor_of_a_cell_is_the_mean_of_its_pixels_and_not_the_factor_of_its_mean(
    run_ok, synthetic_params
):
    """The cell-mean resources (the old input) give another capacity factor: the power curve is not linear on the spread."""
    _, out = run_ok
    table = pd.read_parquet(out / "potential_wind__central.parquet")
    m0 = table[table["member"].astype(str) == "m0"].sort_values("cell_id")
    eta = synthetic_params.technologies.wind.eta_loss.value
    hub = synthetic_params.technologies.wind.hub_height_m.value
    curve = load_power_curve(FIXTURE_CURVES / "synthetic_curve.yaml")
    a_h, k_h, rho_h = resource_at_hub_height(
        {100: A100, 150: A150, 200: A200},
        {100: K100, 150: K150, 200: K200},
        {100: RHO100, 150: RHO150, 200: RHO200},
        hub,
    )
    of_means = wind_cf_member(
        a_h, k_h, rho_h, np.zeros(N_CELLS), np.ones(N_CELLS), curve, eta, RHO0_KG_M3, ISA_T0_K
    )
    relative = np.abs(m0["CF"].to_numpy() - of_means) / of_means
    assert relative.max() > 1e-3  # the spread moves the capacity factor of the cells
    assert relative.max() < 0.2  # and not into another regime


@pytest.mark.unit
def test_every_land_scenario_aggregates_with_its_own_pixel_weights(run_ok, synthetic_params):
    _, out = run_ok
    for scenario in SCENARIO_AREAS:
        table = pd.read_parquet(out / f"potential_wind__{scenario}.parquet")
        m0 = table[table["member"].astype(str) == "m0"].sort_values("cell_id")
        np.testing.assert_allclose(
            m0["CF"], _expected_wind_cf(scenario, 0.0, 1.0, synthetic_params), rtol=1e-12
        )


@pytest.mark.unit
def test_the_provenance_of_the_table_records_the_aggregation_of_each_technology(run_ok):
    _, out = run_ok
    for tech, aggregation in (("solar", "cell"), ("wind", "pixel")):
        meta = pq.read_metadata(out / f"potential_{tech}__central.parquet").metadata
        assert json.loads(meta[PROVENANCE_KEY.encode()])["cf_aggregation"] == aggregation


@pytest.mark.unit
def test_a_pixel_raster_of_another_scenario_is_refused(tmp_path, registry, synthetic_params):
    land, climate = _write_inputs(tmp_path / "in")
    other = land / eligible_fraction_file("wind", "permissive")
    (land / eligible_fraction_file("wind", "restrictive")).write_bytes(other.read_bytes())
    with pytest.raises(PixelInputError, match="differ from the eligible area"):
        build_potential(
            "ZZZ", registry, synthetic_params, ["wind"], EXPERIMENTS, FIXTURE_CURVES,
            candidates_dir=land, siting_dir=land, climate_dir=climate, out_dir=tmp_path / "out", **RANGE_ARGS,
        )  # fmt: skip


@pytest.mark.unit
def test_reference_member_is_the_unperturbed_cf(run_ok):
    _, out = run_ok
    table = pd.read_parquet(out / "potential_solar__central.parquet")
    m0 = table[table["member"].astype(str) == "m0"].sort_values("cell_id")
    np.testing.assert_allclose(m0["CF"], PVOUT / 24.0, rtol=1e-14)


# -- masked cell-members (M-F4-07, D-F5-006) ------------------------------------------------------


@pytest.mark.unit
def test_a_wind_ratio_masked_cell_member_is_absent_for_wind_only_and_solar_keeps_it(run_ok):
    """M-F4-07 (V-B1): the cell-member whose wind ratio is masked has no wind row and is counted; solar, which does not read it, keeps the row."""
    _, out = run_ok
    masked_cell = int(CELL_IDS[MASKED_CELL_INDEX])
    solar = pd.read_parquet(out / "potential_solar__central.parquet")
    assert masked_cell in set(solar[solar["member"].astype(str) == MEMBERS[2]]["cell_id"])
    assert len(solar) == len(MEMBERS) * N_CELLS
    table = pd.read_parquet(out / "potential_wind__central.parquet")
    member_rows = table[table["member"].astype(str) == MEMBERS[2]]
    assert masked_cell not in set(member_rows["cell_id"])
    assert masked_cell in set(table[table["member"].astype(str) == "m0"]["cell_id"])
    assert len(table) == len(MEMBERS) * N_CELLS - 1
    agg = pd.read_parquet(out / "potential_aggregates_wind.parquet")
    row = agg[(agg["scenario"] == "central") & (agg["member"] == MEMBERS[2])].iloc[0]
    assert (row["n_cells"], row["n_cells_absent"], row["n_cells_like_for_like"]) == (7, 1, 7)
    meta = json.loads(
        pq.read_schema(out / "potential_wind__central.parquet").metadata[PROVENANCE_KEY.encode()]
    )
    assert meta["absent_cell_members"] == {MEMBERS[2]: 1}
    solar_meta = json.loads(
        pq.read_schema(out / "potential_solar__central.parquet").metadata[PROVENANCE_KEY.encode()]
    )
    assert solar_meta["absent_cell_members"] == {}


@pytest.mark.unit
def test_a_member_without_a_wind_channel_is_absent_for_wind_by_declaration_and_present_for_solar(
    tmp_path, registry, synthetic_params
):
    """M-F4-02 item 6 (V-B1): a MIROC6-like member has no wind rows and is not counted as masked; its solar rows are all there."""
    _, out = _run(tmp_path, registry, synthetic_params, no_wind=(MEMBERS[1],))
    solar = pd.read_parquet(out / "potential_solar__central.parquet")
    wind = pd.read_parquet(out / "potential_wind__central.parquet")
    assert len(solar[solar["member"].astype(str) == MEMBERS[1]]) == N_CELLS
    assert MEMBERS[1] not in set(wind["member"].astype(str))
    assert set(wind["member"].astype(str)) == {MEMBERS[0], MEMBERS[2]}
    wind_agg = pd.read_parquet(out / "potential_aggregates_wind.parquet")
    solar_agg = pd.read_parquet(out / "potential_aggregates_solar.parquet")
    assert MEMBERS[1] not in set(wind_agg["member"]) and MEMBERS[1] in set(solar_agg["member"])
    meta = json.loads(
        pq.read_schema(out / "potential_wind__central.parquet").metadata[PROVENANCE_KEY.encode()]
    )
    assert MEMBERS[1] not in meta["absent_cell_members"]  # absent by declaration, not by mask


@pytest.mark.unit
def test_the_aggregates_of_wind_repeat_the_central_totals_without_the_cells_above_the_altitude_sensitivity(
    run_ok,
):
    """OQ-058: rows `central__below_3000m` of the wind aggregates sum the cells not above 3000 m (cells 6 and 7 of the fixture are); solar has none."""
    _, out = run_ok
    agg = pd.read_parquet(out / "potential_aggregates_wind.parquet")
    assert "central__below_3000m" in set(agg["scenario"])
    assert "central__below_3000m" not in set(
        pd.read_parquet(out / "potential_aggregates_solar.parquet")["scenario"]
    )
    table = pd.read_parquet(out / "potential_wind__central.parquet")
    kept = CELL_IDS[ELEVATION <= 3000.0]
    assert 0 < len(kept) < N_CELLS
    below = agg[agg["scenario"] == "central__below_3000m"].set_index("member")
    central = agg[agg["scenario"] == "central"].set_index("member")
    for member in MEMBERS:
        rows = table[(table["member"].astype(str) == member) & table["cell_id"].isin(kept)]
        assert below.loc[member, "E_TWh"] == pytest.approx(rows["E_MWh"].sum() / 1e6, rel=1e-13)
        assert below.loc[member, "P_GW"] == pytest.approx(rows["P_MW"].sum() / 1e3, rel=1e-13)
        assert below.loc[member, "E_TWh"] < central.loc[member, "E_TWh"]


@pytest.mark.unit
def test_like_for_like_series_excludes_the_masked_cell_and_the_climate_effect_uses_it(run_ok):
    _, out = run_ok
    table = pd.read_parquet(out / "potential_wind__central.parquet")
    agg = pd.read_parquet(out / "potential_aggregates_wind.parquet")
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
    with pytest.raises(ForcingContractError, match="have no row in forcing.parquet"):
        _run(tmp_path, registry, synthetic_params, drop=[(1, MEMBERS[1])])
    assert not list((tmp_path / "out").glob("*")) if (tmp_path / "out").exists() else True


@pytest.mark.unit
def test_wind_factor_out_of_range_in_a_candidate_cell_raises_for_wind_and_not_for_solar(
    tmp_path, registry, synthetic_params
):
    land, climate = _write_inputs(tmp_path / "in", wind_override=1.8)
    with pytest.raises(ForcingContractError, match="outside"):
        build_potential(
            "ZZZ", registry, synthetic_params, ["wind"], EXPERIMENTS, FIXTURE_CURVES,
            candidates_dir=land, siting_dir=land, climate_dir=climate, out_dir=tmp_path / "out", **RANGE_ARGS,
        )  # fmt: skip
    assert not (tmp_path / "out").exists() or not list((tmp_path / "out").iterdir())
    # solar never reads the wind ratio: the same forcing is usable (V-B1)
    summary = build_potential(
        "ZZZ", registry, synthetic_params, ["solar"], EXPERIMENTS, FIXTURE_CURVES,
        candidates_dir=land, siting_dir=land, climate_dir=climate, out_dir=tmp_path / "out_solar", **RANGE_ARGS,
    )  # fmt: skip
    assert set(summary.technologies) == {"solar"}


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
            candidates_dir=land, siting_dir=land, climate_dir=climate, out_dir=tmp_path / "out",
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


def _without_f5_values(iso: str) -> CountryParams:
    """A real country's parameters with the F5 values removed, as before the Group 1 values were recorded."""
    data = load_parameters(PARAMETERS).countries[iso].model_dump(mode="json")
    for tech, keys in (
        ("solar", ("luf", "power_density_mw_per_km2", "gamma")),
        ("wind", ("luf", "power_density_mw_per_km2", "eta_loss", "hub_height_m")),
    ):
        for key in keys:
            data["technologies"][tech][key].update(
                value=None, range=None, scenario_values=None, status="pending_research"
            )
    return CountryParams.model_validate(data)


@pytest.mark.unit
@pytest.mark.parametrize("iso", ["BRA", "PRT", "IND"])
def test_missing_parameters_fail_loud_listing_every_item_and_write_nothing(iso, tmp_path):
    technologies = load_technologies(TECHNOLOGIES)
    wind = technologies.technologies["wind"].model_copy(update={"power_curve": None})
    technologies = technologies.model_copy(
        update={"technologies": {**technologies.technologies, "wind": wind}}
    )
    with pytest.raises(MissingParameterError) as caught:
        build_potential(
            iso,
            technologies,
            _without_f5_values(iso),
            ["solar", "wind"],
            EXPERIMENTS,
            tmp_path / "no_such_dir",
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
        "power_curve",
    ):
        assert item in message, item
    assert "pending_research" in message
    assert "turbine curve directory config/turbines/" in message  # B-2: the folder is named too
    assert not (tmp_path / "out").exists()


@pytest.mark.unit
def test_an_existing_power_curve_directory_is_not_reported_missing(tmp_path):
    technologies = load_technologies(TECHNOLOGIES)
    params = _without_f5_values("PRT")
    (tmp_path / "curves").mkdir()
    with pytest.raises(MissingParameterError) as caught:
        build_potential(
            "PRT", technologies, params, ["wind"], EXPERIMENTS, tmp_path / "curves",
            out_dir=tmp_path / "out", **RANGE_ARGS,
        )  # fmt: skip
    assert "turbine curve directory" not in str(caught.value)


@pytest.mark.unit
def test_missing_parameter_error_is_raised_before_inputs_are_read(tmp_path):
    """No candidate, forcing or members file exists here, and the error is still the parameter one."""
    technologies = load_technologies(TECHNOLOGIES)
    params = _without_f5_values("PRT")
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
        update={"power_curve": "absent_curve"}
    )
    reg = registry.model_copy(update={"technologies": {**registry.technologies, "wind": wind}})
    land, climate = _write_inputs(tmp_path / "in")
    with pytest.raises(MissingParameterError, match="absent_curve.csv"):
        build_potential(
            "ZZZ", reg, synthetic_params, ["wind"], EXPERIMENTS, FIXTURE_CURVES,
            candidates_dir=land, siting_dir=land, climate_dir=climate, out_dir=tmp_path / "out", **RANGE_ARGS,
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


# -- design-class flag (M-F5-03) ---------------------------------------------------------------------


@pytest.mark.unit
def test_the_flag_is_strictly_above_the_class_limit():
    speeds = np.array([5.0, 7.4, 7.5, 7.51, 12.0])
    assert exceeds_class(speeds, 7.5).tolist() == [False, False, False, True, True]


@pytest.mark.unit
def test_the_flag_rejects_a_mean_speed_that_is_not_finite():
    with pytest.raises(IecClassError, match="not finite"):
        exceeds_class(np.array([np.nan]), 7.5)


@pytest.mark.unit
def test_the_flag_is_written_per_cell_fixed_across_members_and_changes_no_capacity_factor(
    run_ok, tmp_path_factory, registry, synthetic_params
):
    """The flag reads the 100 m layer in the reference climate; the cells and the capacity factor are those of a run without it."""
    summary, out = run_ok
    flag = pd.read_parquet(out / "class_flag_wind__central.parquet").sort_values("cell_id")
    assert list(flag.columns) == [
        "cell_id",
        "v_ave_ms",
        "exceeds_class",
        "density_ratio_isa",
        "density_outside_isa_check",
    ]
    expected = weibull_mean_speed(A100, K100)
    np.testing.assert_allclose(flag["v_ave_ms"], expected, rtol=1e-14)
    assert flag["exceeds_class"].tolist() == (expected > FLAG_THRESHOLD_MS).tolist()
    assert 0 < flag["exceeds_class"].sum() < len(flag), "the synthetic world must have flagged and unflagged cells"
    entry = summary.technologies["wind"].scenarios["central"]
    table = pd.read_parquet(out / "potential_wind__central.parquet")
    p_by_cell = table[table["member"].astype(str) == "m0"].set_index("cell_id")["P_MW"]
    flagged = flag.loc[flag["exceeds_class"], "cell_id"]
    assert entry.p_gw_class_flag == pytest.approx(p_by_cell.loc[flagged].sum() / 1e3, rel=1e-13)
    # no flag in the registry: the same capacity factors (the flag has no effect on CF or eligibility)
    wind = registry.technologies["wind"].model_copy(update={"class_flag": None})
    reg = registry.model_copy(update={"technologies": {**registry.technologies, "wind": wind}})
    _, out2 = _run(tmp_path_factory.mktemp("noflag"), reg, synthetic_params, techs=("wind",))
    assert not (out2 / "class_flag_wind__central.parquet").exists()
    other = pd.read_parquet(out2 / "potential_wind__central.parquet")
    pd.testing.assert_frame_equal(table, other)


@pytest.mark.unit
def test_the_registry_names_one_turbine_and_one_flag_and_the_old_class_rule_is_gone():
    """M-F5-03: one reference turbine for every cell; the class rule is a flag. The real registry names both."""
    wind = load_technologies(TECHNOLOGIES).technologies["wind"]
    assert wind.power_curve == "iea_3.4_130"
    assert wind.class_flag is not None
    assert (wind.class_flag.iec_class, wind.class_flag.mean_speed_threshold_ms) == ("III", 7.5)
    assert wind.class_flag.layer_height_m == 100.0
    assert "power_curves" not in TechnologyConfig.model_fields
    assert "iec_class_rule" not in TechnologyConfig.model_fields


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
        candidates_dir=land, siting_dir=land, climate_dir=climate, out_dir=out, **RANGE_ARGS,
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
            candidates_dir=land, siting_dir=land, climate_dir=climate, out_dir=tmp_path / "out", **RANGE_ARGS,
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
            candidates_dir=land, siting_dir=land, climate_dir=climate, out_dir=tmp_path / "out", **RANGE_ARGS,
        )  # fmt: skip
    assert "air_density_100m" in str(caught.value) and "dist_grid_km" in str(caught.value)


def _run_wind_with(tmp_path, registry, synthetic_params, caplog, column, value, rows=(0,)):
    land, climate = _write_inputs(tmp_path / "in")
    _corrupt(land, "wind", column, value, rows=rows)
    with caplog.at_level("INFO", logger="geofrea.technical_potential"):
        return build_potential(
            "ZZZ", registry, synthetic_params, ["wind"], EXPERIMENTS, FIXTURE_CURVES,
            candidates_dir=land, siting_dir=land, climate_dir=climate, out_dir=tmp_path / "out", **RANGE_ARGS,
        )  # fmt: skip


@pytest.mark.unit
def test_a_cell_with_k_above_10_stops_the_phase_with_the_count_and_the_coordinates(
    tmp_path, registry, synthetic_params, caplog
):
    """OQ-053 closed: k is valid on (0, 10]; k = 10.5 is an error that names the layer, the count of cells and where they are."""
    with pytest.raises(InputRangeError) as caught:
        _run_wind_with(tmp_path, registry, synthetic_params, caplog, "weibull_k_100m", 10.5, rows=(0, 2))
    text = str(caught.value)
    assert "weibull_k_100m" in text and "2 of" in text and "(0, 10]" in text
    assert "(lat, lon)" in text and "(40.0000, 10.0000)" in text  # the fixture cells are at 40 N, 10 E
    assert "nothing was computed" in text
    assert not (tmp_path / "out").exists() or not list((tmp_path / "out").glob("potential_*"))


@pytest.mark.unit
@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("weibull_k_100m", 0.0),
        ("weibull_k_150m", -1.0),
        ("weibull_a_200m", 0.0),
        ("weibull_a_100m", 25.5),
        ("weibull_a_150m", float("nan")),
    ],
)
def test_the_weibull_limits_exclude_zero_and_negative_values_and_a_above_25_and_non_finite(
    tmp_path, registry, synthetic_params, caplog, column, value
):
    with pytest.raises(InputRangeError, match=column):
        _run_wind_with(tmp_path, registry, synthetic_params, caplog, column, value)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("weibull_k_100m", 4.5),
        ("weibull_k_100m", 0.8),
        ("weibull_k_150m", 10.0),
        ("weibull_a_100m", 25.0),
        ("weibull_a_200m", 0.5),
    ],
)
def test_values_inside_the_limits_stop_nothing_and_generate_no_warning_even_when_unusual(
    tmp_path, registry, synthetic_params, caplog, column, value
):
    """k = 4.5 and k = 0.8 are valid (they are only reported in the distribution); the limits include 10 and 25 themselves."""
    summary = _run_wind_with(tmp_path, registry, synthetic_params, caplog, column, value)
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert not warnings, [r.getMessage() for r in warnings]
    assert summary.technologies["wind"].scenarios["central"].n_candidate_cells > 0


@pytest.mark.unit
def test_the_distribution_report_is_written_with_the_percentiles_and_the_k_counts_without_a_warning(
    tmp_path, registry, synthetic_params, caplog
):
    summary = _run_wind_with(
        tmp_path, registry, synthetic_params, caplog, "weibull_k_100m", 4.5, rows=(0,)
    )
    path = summary.technologies["wind"].weibull_distribution
    assert path is not None and path.name == "weibull_distribution_wind.csv" and path.is_file()
    table = pd.read_csv(path)
    assert list(table.columns) == [
        "variable", "height_m", "n_cells", "p1", "p50", "p99", "min", "max", "n_k_below_1", "n_k_above_4",
    ]  # fmt: skip
    assert set(zip(table["variable"], table["height_m"], strict=True)) == {
        (v, h) for v in ("A", "k") for h in (100, 150, 200)
    }
    k100 = table[(table["variable"] == "k") & (table["height_m"] == 100)].iloc[0]
    assert k100["n_k_above_4"] == 1 and k100["max"] == pytest.approx(4.5)
    assert k100["p1"] <= k100["p50"] <= k100["p99"]
    a100 = table[(table["variable"] == "A") & (table["height_m"] == 100)].iloc[0]
    assert pd.isna(a100["n_k_below_1"]) and pd.isna(a100["n_k_above_4"])
    assert not [r for r in caplog.records if r.levelname == "WARNING"]
    assert any("Weibull distribution" in r.getMessage() for r in caplog.records)


@pytest.mark.unit
def test_the_weibull_limits_are_those_of_the_verdict_at_every_height_and_the_layers_are_no_longer_open():
    ranges = resolve_input_ranges(
        "ZZZ", AUDIT, GEOMETRY, [f"weibull_{v}_{h}m" for v in "ak" for h in (100, 150, 200)]
    )
    for h in (100, 150, 200):
        a, k = ranges[f"weibull_a_{h}m"], ranges[f"weibull_k_{h}m"]
        assert (a.low, a.high, a.low_exclusive, a.tier) == (0.0, 25.0, True, 3)
        assert (k.low, k.high, k.low_exclusive, k.tier) == (0.0, 10.0, True, 3)
        assert not a.is_open and not k.is_open


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


# -- scenario-coupled LUF and power density, eta_loss applied once (M-F5-01, M-F5-03) ----------------------------


def _with_scenarios(params: CountryParams, tech: str, key: str, triple) -> CountryParams:
    data = params.model_dump(mode="json")
    entry = data["technologies"][tech][key]
    entry["scenario_values"] = dict(
        zip(("restrictive", "central", "permissive"), triple, strict=True)
    )
    entry["value"] = triple[1]
    return CountryParams.model_validate(data)


@pytest.mark.unit
def test_luf_and_power_density_take_the_value_of_each_land_scenario(
    tmp_path, registry, synthetic_params
):
    params = _with_scenarios(synthetic_params, "solar", "luf", (0.2, 0.4, 0.6))
    params = _with_scenarios(params, "solar", "power_density_mw_per_km2", (45.0, 50.0, 75.0))
    summary, out = _run(tmp_path, registry, params, techs=("solar",))
    expected = {"restrictive": (0.2, 45.0), "central": (0.4, 50.0), "permissive": (0.6, 75.0)}
    for scenario, (luf, density) in expected.items():
        table = pd.read_parquet(out / f"potential_solar__{scenario}.parquet")
        m0 = table[table["member"].astype(str) == "m0"].sort_values("cell_id")
        np.testing.assert_allclose(
            m0["P_MW"], np.array(SCENARIO_AREAS[scenario]) * luf * density, rtol=1e-14
        )
        entry = summary.technologies["solar"].scenarios[scenario]
        assert (entry.luf, entry.power_density_mw_per_km2) == (luf, density)
        meta = json.loads(
            pq.read_schema(out / f"potential_solar__{scenario}.parquet").metadata[
                PROVENANCE_KEY.encode()
            ]
        )
        assert meta["scenario_parameters"] == {"luf": luf, "power_density_mw_per_km2": density}


@pytest.mark.unit
def test_scenario_values_must_have_the_value_as_their_central_one(synthetic_params):
    data = synthetic_params.model_dump(mode="json")
    data["technologies"]["solar"]["luf"]["scenario_values"] = {
        "restrictive": 0.1,
        "central": 0.3,  # the value is 0.5
        "permissive": 0.7,
    }
    with pytest.raises(ValueError, match="central"):
        CountryParams.model_validate(data)


@pytest.mark.unit
def test_eta_loss_multiplies_the_wind_capacity_factor_once(tmp_path, registry, synthetic_params):
    _, out_a = _run(tmp_path / "a", registry, synthetic_params, techs=("wind",))
    other = _with(synthetic_params, "wind", "eta_loss", 0.85)
    _, out_b = _run(tmp_path / "b", registry, other, techs=("wind",))
    a = pd.read_parquet(out_a / "potential_wind__central.parquet")
    b = pd.read_parquet(out_b / "potential_wind__central.parquet")
    eta_a = synthetic_params.technologies.wind.eta_loss.value
    np.testing.assert_allclose(b["CF"].to_numpy() / a["CF"].to_numpy(), 0.85 / eta_a, rtol=1e-13)
