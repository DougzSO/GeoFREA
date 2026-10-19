"""The second synthetic world, ZZZ2, through F1 to F8 with no network (audit 2026-10, M-1; COMMAND 39).

ZZZ keeps the order of its cells in every future, so its end-to-end values of `V_k`, `D`, `D_clim`, `D_tec` and the PRIM outcome are zero and the checks on them would
also pass for a function that returns zero. ZZZ2 (`scripts/zzz2_world.py`) is built so that they are not: the wind of the atlas and the change factors of each GCM vary in space,
the line is on the west edge and the road on the east edge, and the test parameters make the distance as expensive as the climate is strong. The values below were not read from
the pipeline: they come from the hand validation (`docs/_audit/2026-10_pre_research_audit_scripts/validate_zzz_by_hand.py`, which imports nothing from `geofrea`) run on this
world, and the same script is run here on the same run, so a pipeline that disagrees with the plain-numpy computation fails twice. The outcome of PRIM is the real one (no rule replaces
it, unlike in `test_zzz_end_to_end.py`).

What is known beforehand about the world, from its construction:

- the change factors of a cell centre are the closed forms of `zzz2_world` (linear fields, so the 3 x 3 mean and the bilinear interpolation are exact);
- GFDL-ESM4 and IPSL-CM6A-LR take wind from the east (the cells the nominal ranking favours) and CNRM-CM6-1 takes it from the north, so the nominal shortlist is displaced in their futures;
- wind is Climate-Dominated (`D_clim` > 0, `D_tec` = 0, `rho` = 1): the draws of the costs do not take a cell of the techno-only shortlist beyond k + m, the climate does, and the box of PRIM
  restricts the climate model;
- solar is Techno-Economic-Dominated (`D_clim` = 0, `D_tec` > 0, `rho` = 0): the distance costs reorder the cells between draws, the climate does not displace the shortlist, and the box of PRIM
  restricts cost parameters, not the climate model;
- H4 compares countries (strict rule per technology), so one run cannot have a verdict; beside its mirror (a country whose two profiles are the other technology's) ZZZ2 is `supported` in both.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))

import zzz2_world as world
import zzz_run

VALIDATOR = (
    REPO / "docs" / "_audit" / "2026-10_pre_research_audit_scripts" / "validate_zzz_by_hand.py"
)
INITIAL_SIZE, CEILING = 16, 64
TECHS = ("wind", "solar")

# Expected statistics of the core window at the primary setting, from the hand validation of this world (see the module docstring).
EXPECTED = {
    "wind": {
        "c_k": 1.0,
        "v_k": 0.8,
        "overlap": 0.6134364728419008,
        "overlap_ref": 0.361205191909124,
        "d": 0.396691483432451,
        "d_clim": 0.396691483432451,
        "d_tec": 0.0,
        "rho": 1.0,
        "profile": "climate_dominated",
        "r_loss": 0.055151402881962984,  # METHODOLOGY 14.2.0: the member density follows dT; confirmed by the hand validation (was 0.0521657052686253)
        "cases": 134,
        "futures": 240,
        "box_density": 1.0,
        "box_coverage": 0.7164179104477612,
    },
    "solar": {
        "c_k": 1.0,
        "v_k": 0.4,
        "overlap": 0.7604003039769672,
        "overlap_ref": 0.35522992510054363,
        "d": 0.1932716627892325,
        "d_clim": 0.0,
        "d_tec": 0.1932716627892325,
        "rho": 0.0,
        "profile": "techno_economic_dominated",
        "r_loss": 0.07072541219935047,
        "cases": 220,
        "futures": 288,
        "box_density": 0.9444444444444444,
        "box_coverage": 0.7727272727272727,
    },
}


@pytest.fixture(scope="module")
def zzz2(tmp_path_factory):
    import main  # repo-root script
    from geofrea.core.config_loader import load_audit_config, load_settings

    data = tmp_path_factory.mktemp("zzz2_data")
    paths = zzz_run.prepare_configuration(
        data, INITIAL_SIZE, CEILING, parameter_changes=world.PARAMETER_OVERRIDES
    )
    patch = pytest.MonkeyPatch()
    patch.setenv("GEOFREA_DATA_DIR", str(data))
    patch.setattr(main, "TECHNOLOGIES_YAML", paths["technologies"])
    patch.setattr(main, "EXPERIMENTS_YAML", paths["experiments"])
    patch.setattr(main, "PARAMETERS_JSON", paths["parameters"])
    patch.setattr(main, "POWER_CURVES_DIR", zzz_run.CURVES)
    try:
        subprocess.run(
            [sys.executable, str(REPO / "scripts" / "generate_zzz2_fixture.py")],
            check=True,
            env={**os.environ, "GEOFREA_DATA_DIR": str(data)},
            capture_output=True,
        )
        settings = load_settings(main.SETTINGS_YAML)
        zzz_run.refuse_network(patch)
        ok, _orchestrator, results = main.run_geofrea(
            "ZZZ",
            zzz_run.PHASES,
            [],
            settings.geospatial.resolutions,
            settings.geospatial.distance_cap_km,
            load_audit_config(main.AUDIT_YAML),
            "zzz2-end-to-end",
            False,
            None,
            tuple(settings.run.technologies),
            False,
            settings.figures,
            settings.memory.max_batch_gb,
        )
        assert ok, {k: v.status for k, v in results.items()}
        yield data, results
    finally:
        patch.undo()


def _art(zzz2, phase):
    return zzz2[0] / "outputs" / "ZZZ" / phase / "artifacts"


def _primary(zzz2, name, tech):
    table = pd.read_parquet(_art(zzz2, "robustness_analysis") / f"{name}_{tech}__core.parquet")
    return table[table["primary"]].iloc[0]


@pytest.mark.synthetic
def test_every_phase_from_f1_to_f8_runs_and_succeeds(zzz2):
    _data, results = zzz2
    failed = {k: v.status for k, v in results.items() if v.status != "success"}
    assert not failed, failed
    assert {
        "technical_potential",
        "lcoe_modeling",
        "robustness_analysis",
        "results_synthesis",
    } <= set(results)


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", ["solar", "wind"])
def test_potential_maps_of_the_second_synthetic_world_add_up_to_the_f5_totals(zzz2, tech):
    """D-F5-029: the cells whose potential changes order between members still give 8 maps and states that add up to the national total."""
    from absolute_maps_checks import check_absolute_maps

    check_absolute_maps(zzz2[0], "ZZZ", tech)


@pytest.mark.synthetic
def test_the_change_factors_of_every_cell_centre_are_the_closed_forms_of_the_world(zzz2):
    """F4 interpolates linear native fields: each delta_wind, delta_rsds and dT must equal its closed form to single precision."""
    forcing = pd.read_parquet(_art(zzz2, "climate_forcing") / "forcing.parquet").astype(
        {"member": str}
    )
    cells = pd.read_parquet(
        _art(zzz2, "land_eligibility") / "cells_wind__central.parquet"
    ).set_index("cell_id")
    members = yaml.safe_load((_art(zzz2, "climate_forcing") / "members.yaml").read_text())[
        "members"
    ]
    ssp = {"SSP1-2.6": 0, "SSP3-7.0": 1, "SSP5-8.5": 2}
    window = {"2041-2070": 0, "2071-2100": 1}
    checked = 0
    for entry in members:
        if entry.get("gcm") is None:
            continue
        gcm = entry["gcm"].lower().replace("-", "_")
        s, w = ssp[entry["ssp"]], window[entry["window"]]
        rows = forcing[forcing["member"] == entry["member"]].join(
            cells[["lat_c", "lon_c"]], on="cell_id"
        )
        lon, lat = rows["lon_c"].to_numpy(), rows["lat_c"].to_numpy()
        np.testing.assert_allclose(
            rows["delta_rsds"], world.delta_rsds(gcm, s, w, lon, lat), atol=2e-7
        )
        np.testing.assert_allclose(rows["dT"], world.delta_t(gcm, s, w, lon, lat), atol=2e-5)
        if entry["channels"]["resource_wind"]:
            np.testing.assert_allclose(
                rows["delta_wind"], world.delta_wind(gcm, s, w, lon, lat), atol=2e-7
            )
        checked += len(rows)
    assert checked >= 36 * 24


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", TECHS)
def test_the_cells_change_order_between_members_and_between_draws(zzz2, tech):
    """What ZZZ cannot show: the ranking is not the same in every future (the premise of M-1)."""
    robust = pd.read_parquet(
        _art(zzz2, "robustness_analysis") / f"robustness_{tech}__core.parquet"
    ).set_index("cell_id")
    nominal, climate, techno = (
        robust["nominal_rank"],
        robust["climate_only_rank"],
        robust["techno_only_rank"],
    )
    assert not nominal.equals(climate), "the climate-only ranking equals the nominal one"
    assert not nominal.equals(techno), "the techno-only ranking equals the nominal one"
    futures = pd.read_parquet(_art(zzz2, "robustness_analysis") / f"futures_{tech}__core.parquet")
    futures = futures[futures["sample"] >= 1]
    share = futures["displaced_capacity_share"]
    assert share.nunique() > 3
    assert 0.0 < float((share >= 0.2).mean()) < 1.0
    # the nominal shortlist is displaced in some climate models and in none of some others (wind: ACCESS-CM2 and MRI-ESM2-0 barely move it)
    by_gcm = futures.groupby("gcm")["displaced_capacity_share"].max()
    assert by_gcm.max() >= 0.2


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", TECHS)
def test_the_non_trivial_statistics_have_the_values_known_beforehand(zzz2, tech):
    expected = EXPECTED[tech]
    h1, h2, h3 = (_primary(zzz2, f"h{i}_summary", tech) for i in (1, 2, 3))
    h4, h5 = _primary(zzz2, "h4_country", tech), _primary(zzz2, "h5_summary", tech)
    assert h1["c_k"] == pytest.approx(expected["c_k"], abs=1e-12)
    assert h1["v_k"] == pytest.approx(expected["v_k"], abs=1e-12)
    assert h2["overlap"] == pytest.approx(expected["overlap"], abs=1e-9)
    assert h2["overlap_ref"] == pytest.approx(expected["overlap_ref"], abs=1e-9)
    assert h3["d"] == pytest.approx(expected["d"], abs=1e-9)
    assert h4["d_clim"] == pytest.approx(expected["d_clim"], abs=1e-9)
    assert h4["d_tec"] == pytest.approx(expected["d_tec"], abs=1e-9)
    assert h4["rho"] == pytest.approx(expected["rho"], abs=1e-9)
    assert h4["profile"] == expected["profile"]
    assert h5["r_loss"] == pytest.approx(expected["r_loss"], abs=1e-9)
    # none of them is the trivial value of ZZZ: V_k and D are strictly between 0 and 1, and the profile is decided by one displacement being positive (the other one is zero by construction)
    for value in (h1["v_k"], h3["d"]):
        assert 0.0 < value < 1.0
    assert h4["d_clim"] + h4["d_tec"] > 0.0
    assert (h4["d_tec"] == 0.0) == (tech == "wind") and (h4["d_clim"] == 0.0) == (tech == "solar")


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", TECHS)
def test_prim_finds_a_box_on_the_real_outcome_that_restricts_what_decides_it(zzz2, tech):
    expected = EXPECTED[tech]
    box = _primary(zzz2, "prim_box", tech)
    assert box["status"] == "box_found"
    restricted = str(box["restricted"]).split("|")
    if tech == "wind":  # climate-dominated: the climate model decides the outcome
        assert "gcm" in restricted
    else:  # techno-economic-dominated: cost parameters decide it, not the climate model
        assert "gcm" not in restricted
        assert set(restricted) <= set(world.PARAMETER_OVERRIDES[tech]) | {
            "capex_usd_per_kw",
            "opex_fixed_frac",
            "discount_rate",
            "lifetime_years",
            "degradation_rate",
            "substation_cost_usd_per_mw",
            "gamma",
        }
    assert box["n_cases"] == expected["cases"]
    assert box["n_futures"] == expected["futures"]
    assert box["density"] == pytest.approx(expected["box_density"], abs=1e-9)
    assert box["coverage"] == pytest.approx(expected["box_coverage"], abs=1e-9)
    assert box["coverage"] >= 0.5  # the pre-registered requirement
    assert box["density"] > box["base_rate"]  # the box is better than the whole set of futures


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", TECHS)
def test_the_hand_validation_agrees_with_every_phase_of_the_run(zzz2, tech):
    """The script imports nothing from geofrea: it recomputes F3 to F7 (and the PRIM bookkeeping and the outcome of every future) with numpy and scipy."""
    done = subprocess.run(
        [sys.executable, str(VALIDATOR), str(zzz2[0]), tech, "zzz2"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-2000:]
    match = re.search(r"(\d+) of (\d+) checks pass\.", done.stdout)
    assert match, done.stdout[-1500:]
    passed, total = int(match.group(1)), int(match.group(2))
    assert passed == total >= 38


@pytest.mark.synthetic
def test_h4_is_supported_in_both_technologies_beside_the_mirror_of_zzz2(
    zzz2, tmp_path, monkeypatch
):
    """H4 compares countries, so one run has no verdict ('not testable'). The mirror country has the profile tables of the other technology
    (wind gets the solar table, solar the wind table): beside it ZZZ2 has a Climate-Dominated and a Techno-Economic-Dominated country in each
    technology, and the strict rule gives `supported`. Nothing is set by hand: both tables are the ones F7 wrote."""
    import hashlib
    import shutil

    from geofrea.core.tables import write_table
    from geofrea.robustness_analysis.cross_country import build_h4_verdict
    from geofrea.robustness_analysis.table_schemas import (
        ROBUSTNESS_TABLE_SCHEMA_VERSION,
        H4CountryRow,
    )

    data = tmp_path / "data"
    shutil.copytree(zzz2[0] / "outputs" / "ZZZ", data / "outputs" / "ZZZ")
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(data))
    alone = build_h4_verdict(["ZZZ"], ("solar", "wind"))
    assert {v.verdict for v in alone.verdicts} == {"not_testable"}

    manifest = {"artifacts": {}}
    other = {"wind": "solar", "solar": "wind"}
    for tech in ("solar", "wind"):
        for role in ("core", "sensitivity"):
            frame = pd.read_parquet(
                _art(zzz2, "robustness_analysis") / f"h4_country_{other[tech]}__{role}.parquet"
            )
            rel = f"outputs/ZZM/h4_country_{tech}__{role}.parquet"
            path = write_table(
                frame,
                data / rel,
                schema_version=ROBUSTNESS_TABLE_SCHEMA_VERSION,
                row_model=H4CountryRow,
            )
            manifest["artifacts"][f"h4_country_{tech}__{role}"] = {
                "path": {"root": "data", "rel": rel},
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
    (data / "outputs" / "ZZM" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    pair = build_h4_verdict(["ZZZ", "ZZM"], ("solar", "wind"))
    core = {v.technology: v for v in pair.verdicts if v.role == "core"}
    assert core["wind"].verdict == "supported" and core["solar"].verdict == "supported"
    for tech in ("wind", "solar"):
        assert core[tech].counts["climate_dominated"] == 1
        assert core[tech].counts["techno_economic_dominated"] == 1
        assert core[tech].n_available == 2
