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
- ACCESS-CM2 and MRI-ESM2-0 leave the shortlist almost where it is, so the box of PRIM restricts the climate model;
- the distance costs reorder the cells between draws, so `D_tec` is positive in both technologies.
"""

from __future__ import annotations

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
        "v_k": 0.6,
        "overlap": 0.7604003039769672,
        "overlap_ref": 0.35522992510054363,
        "d": 0.386543325578465,
        "d_clim": 0.386543325578465,
        "d_tec": 0.386543325578465,
        "rho": 0.5,
        "profile": "mixed",
        "r_loss": 0.056642199984308333,
        "cases": 139,
        "futures": 240,
        "box_density": 0.9841269841269841,
        "box_coverage": 0.8920863309352518,
    },
    "solar": {
        "c_k": 1.0,
        "v_k": 0.6,
        "overlap": 0.6134364728419008,
        "overlap_ref": 0.35522992510054363,
        "d": 0.1932716627892325,
        "d_clim": 0.1932716627892325,
        "d_tec": 0.19007445029735284,
        "rho": 0.5041701381372263,
        "profile": "mixed",
        "r_loss": 0.07072541219935047,
        "cases": 134,
        "futures": 288,
        "box_density": 0.5857142857142857,
        "box_coverage": 0.917910447761194,
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
    assert by_gcm.max() >= 0.2 > by_gcm.min() or tech == "solar"


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
    # none of them is the trivial value of ZZZ
    for value in (h1["v_k"], h3["d"], h4["d_clim"], h4["d_tec"]):
        assert 0.0 < value < 1.0


@pytest.mark.synthetic
@pytest.mark.parametrize("tech", TECHS)
def test_prim_finds_a_box_that_restricts_the_climate_model_on_the_real_outcome(zzz2, tech):
    expected = EXPECTED[tech]
    box = _primary(zzz2, "prim_box", tech)
    assert box["status"] == "box_found"
    assert "gcm" in str(box["restricted"]).split("|")
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
