"""The configuration fingerprint of a phase and the manifest resume that depends on it (manifest 2.5, A-02).

COMMAND 49 found that a change of `elevation_max_m` in experiments.yaml was not seen: the manifest resumed land_eligibility as
`success` with the old result. A phase is now resumed only while the configuration it reads is the recorded one.
"""

import shutil
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

import main as geofrea_main
from geofrea.config_models.land_availability import load_land_availability
from geofrea.core.config_fingerprint import (
    ABSENT,
    CONFIG_FILES,
    PHASE_CONFIG_SCOPE,
    TURBINES,
    DiskConfigSource,
    config_fingerprint,
    phase_config_payload,
)
from geofrea.core.config_loader import load_parameters
from geofrea.core.orchestrator import Orchestrator, PhaseSpec

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = REPO_ROOT / "config"
CHAIN = [
    "land_eligibility",
    "technical_potential",
    "lcoe_modeling",
    "robustness_analysis",
    "external_validation",
    "results_synthesis",
]


@pytest.fixture
def config_copy(tmp_path):
    target = tmp_path / "config"
    shutil.copytree(CONFIG, target)
    return target


def _source(config_dir: Path) -> DiskConfigSource:
    return DiskConfigSource(
        {k: config_dir / name for k, name in CONFIG_FILES.items()}, config_dir / TURBINES
    )


def _fingerprints(config_dir: Path, iso: str = "PRT") -> dict[str, str]:
    source = _source(config_dir)
    return {phase: config_fingerprint(phase, iso, source) for phase in PHASE_CONFIG_SCOPE}


def _edit(config_dir: Path, name: str, old: str, new: str) -> None:
    path = config_dir / name
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (name, old, text.count(old))
    path.write_text(text.replace(old, new), encoding="utf-8")


def _changed(before: dict[str, str], after: dict[str, str]) -> set[str]:
    return {phase for phase in before if before[phase] != after[phase]}


# ─── the scopes ──────────────────────────────────────────────────────────


@pytest.mark.unit
def test_every_registered_phase_has_a_scope_and_only_those():
    specs = geofrea_main._build_phase_specs(
        geofrea_main.ResolutionsConfig(suitability=0.01),
        100.0,
        geofrea_main.load_audit_config(geofrea_main.AUDIT_YAML),
        ("solar", "wind"),
    )
    assert {s.name for s in specs} == set(PHASE_CONFIG_SCOPE)


@pytest.mark.unit
@pytest.mark.parametrize("iso", ["PRT", "BRA", "IND"])
def test_every_section_a_scope_names_exists_in_the_config(iso):
    source = _source(CONFIG)
    for phase in PHASE_CONFIG_SCOPE:
        payload = phase_config_payload(phase, iso, source)
        for key, values in payload.items():
            if key == TURBINES:
                assert values, f"{phase}: no power-curve file"
                continue
            for selector, value in values.items():
                assert value != ABSENT, f"{phase}: {key} {selector} is not in the config"


@pytest.mark.unit
def test_main_specs_carry_the_fingerprint_only_with_a_country():
    args = (
        geofrea_main.ResolutionsConfig(suitability=0.01),
        100.0,
        geofrea_main.load_audit_config(geofrea_main.AUDIT_YAML),
        ("solar", "wind"),
    )
    assert all(s.config_fingerprint is None for s in geofrea_main._build_phase_specs(*args))
    with_country = geofrea_main._build_phase_specs(*args, country_code="PRT")
    assert all(len(s.config_fingerprint) == 64 for s in with_country)


# ─── what changes a fingerprint ──────────────────────────────────────────


@pytest.mark.unit
def test_a_key_read_by_f3_changes_f3_and_the_phases_downstream_that_read_it(config_copy):
    before = _fingerprints(config_copy)
    _edit(config_copy, "experiments.yaml", "nominal: 3000.0", "nominal: 2500.0")
    changed = _changed(before, _fingerprints(config_copy))
    assert set(CHAIN) <= changed  # F3, F5, F6, F7, F7b and F8 all read land_availability
    assert (
        "data_quality_audit" not in changed
    )  # F1b reads only the slope limits of land_availability
    assert not changed & {
        "data_acquisition",
        "grid_alignment",
        "siting_layers",
        "climate_forcing",
        "hazard_context",
        "climate_maps",
        "potential_maps",
        "overview",
        "external_inputs",
    }


@pytest.mark.unit
def test_a_key_f3_does_not_read_leaves_f3_unchanged(config_copy):
    before = _fingerprints(config_copy)
    _edit(config_copy, "experiments.yaml", "bootstrap_replicates: 200", "bootstrap_replicates: 400")
    changed = _changed(before, _fingerprints(config_copy))
    assert changed == {"robustness_analysis"}  # prim is read by F7 only
    assert "land_eligibility" not in changed


@pytest.mark.unit
def test_other_file_keys_reach_only_the_phases_that_read_them(config_copy):
    before = _fingerprints(config_copy)
    _edit(config_copy, "settings.yaml", "figures: summary", "figures: none")
    assert _changed(before, _fingerprints(config_copy)) >= {"potential_maps", "overview"}
    assert "land_eligibility" not in _changed(before, _fingerprints(config_copy))
    (config_copy / TURBINES / "iea_3.4_130.csv").write_text("0,0\n", encoding="utf-8")
    assert "technical_potential" in _changed(before, _fingerprints(config_copy))
    assert "land_eligibility" not in _changed(before, _fingerprints(config_copy))


@pytest.mark.unit
def test_parameters_of_another_country_do_not_change_the_fingerprint(config_copy):
    import json

    before = _fingerprints(config_copy, "PRT")
    path = config_copy / "parameters.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    cell = data["countries"]["BRA"]["technologies"]["solar"]["discount_rate"]
    cell["value"] = cell["value"] * 1.01
    path.write_text(json.dumps(data), encoding="utf-8")
    after = _fingerprints(config_copy, "PRT")
    assert "technical_potential" not in _changed(before, after)
    assert "technical_potential" in _changed(
        _fingerprints(CONFIG, "BRA"), _fingerprints(config_copy, "BRA")
    )


@pytest.mark.unit
def test_comments_and_key_order_do_not_change_a_fingerprint(config_copy):
    before = _fingerprints(config_copy)
    path = config_copy / "experiments.yaml"
    path.write_text(
        "# a comment that changes nothing\n" + path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    assert _fingerprints(config_copy) == before


# ─── the resume ──────────────────────────────────────────────────────────


class Out(BaseModel):
    model_config = ConfigDict(extra="forbid")

    elevation_max_m: float


def _chain_specs(config_dir: Path, outputs: Path, calls: list[str]) -> list[PhaseSpec]:
    """Dummy phases with the real names, whose artifact content is the elevation limit read from `config_dir`."""
    source = _source(config_dir)
    specs = []
    previous = None
    for name in CHAIN:

        def run(context, name=name):
            calls.append(name)
            value = (
                load_land_availability(config_dir / "experiments.yaml")
                .technologies["wind"]
                .elevation_max_m.nominal
            )
            path = outputs / f"{name}.txt"
            path.write_text(f"{name}-{value}", encoding="utf-8")
            context.register_artifact(name, path, "1.0")
            return Out(elevation_max_m=value)

        specs.append(
            PhaseSpec(
                name=name,
                output_model=Out,
                run=run,
                requires=frozenset({previous}) if previous else frozenset(),
                produces=frozenset({name}),
                config_fingerprint=config_fingerprint(name, "PRT", source),
            )
        )
        previous = name
    return specs


def _orchestrator(outputs: Path, run_id: str, target: str = CHAIN[-1]) -> Orchestrator:
    return Orchestrator(
        outputs_dir=outputs,
        country_code="PRT",
        country_params=load_parameters(CONFIG / "parameters.json").countries["PRT"],
        target_phases=[target],
        rerun_phases=[],
        run_id=run_id,
        methodology_version="test-1.0.0",
        dirty=False,
    )


@pytest.mark.unit
def test_changing_a_key_f3_reads_reruns_f3_to_f8_and_an_unrelated_key_reruns_none(
    tmp_path, config_copy
):
    outputs = tmp_path / "out"
    outputs.mkdir()
    calls: list[str] = []
    _orchestrator(outputs, "run-1").run(_chain_specs(config_copy, outputs, calls))
    assert calls == CHAIN

    calls.clear()
    _orchestrator(outputs, "run-2").run(_chain_specs(config_copy, outputs, calls))
    assert calls == []  # same configuration: everything resumes

    _edit(config_copy, "experiments.yaml", "bootstrap_replicates: 200", "bootstrap_replicates: 400")
    _orchestrator(outputs, "run-3").run(_chain_specs(config_copy, outputs, calls))
    assert calls == [
        "robustness_analysis"
    ]  # F3 resumed; F7 ran again and, its content unchanged, its consumer stays valid

    calls.clear()
    _edit(config_copy, "experiments.yaml", "nominal: 3000.0", "nominal: 2500.0")
    results = _orchestrator(outputs, "run-4").run(_chain_specs(config_copy, outputs, calls))
    assert (
        calls == CHAIN
    )  # the case of COMMAND 49: F3 and everything that reads the limit run again
    assert results["land_eligibility"].output.elevation_max_m == 2500.0
    assert (outputs / "land_eligibility.txt").read_text(
        encoding="utf-8"
    ) == "land_eligibility-2500.0"


@pytest.mark.unit
def test_a_changed_fingerprint_is_recorded_and_the_next_run_resumes(tmp_path, config_copy):
    outputs = tmp_path / "out"
    outputs.mkdir()
    calls: list[str] = []
    _orchestrator(outputs, "run-1").run(_chain_specs(config_copy, outputs, calls))
    _edit(config_copy, "experiments.yaml", "nominal: 3000.0", "nominal: 2500.0")
    orch = _orchestrator(outputs, "run-2")
    orch.run(_chain_specs(config_copy, outputs, calls))
    assert (
        orch.manifest.phases["land_eligibility"].config_fingerprint
        == _fingerprints(config_copy)["land_eligibility"]
    )
    calls.clear()
    _orchestrator(outputs, "run-3").run(_chain_specs(config_copy, outputs, calls))
    assert calls == []


@pytest.mark.unit
def test_an_upstream_rerun_with_changed_content_stales_a_consumer_whose_own_config_is_unchanged(
    tmp_path, config_copy
):
    outputs = tmp_path / "out"
    outputs.mkdir()
    calls: list[str] = []
    _orchestrator(outputs, "run-1").run(_chain_specs(config_copy, outputs, calls))
    specs = _chain_specs(config_copy, outputs, calls)
    # the consumers keep their recorded fingerprint, only F3 sees a new configuration: the consumers are invalidated by the new content
    specs[0] = PhaseSpec(**{**specs[0].__dict__, "config_fingerprint": "f" * 64})
    _edit(config_copy, "experiments.yaml", "nominal: 3000.0", "nominal: 2500.0")
    orch = _orchestrator(outputs, "run-2", target="land_eligibility")
    orch.run(specs)
    assert orch.manifest.phases["technical_potential"].status == "stale_upstream"
    assert orch.manifest.phases["land_eligibility"].status == "success"


@pytest.mark.unit
def test_an_entry_without_a_fingerprint_is_resumed_once_and_adopts_the_current_one(
    tmp_path, config_copy
):
    outputs = tmp_path / "out"
    outputs.mkdir()
    calls: list[str] = []
    old = [
        PhaseSpec(**{**s.__dict__, "config_fingerprint": None})
        for s in _chain_specs(config_copy, outputs, calls)
    ]
    _orchestrator(outputs, "run-1").run(old)
    calls.clear()
    orch = _orchestrator(outputs, "run-2")
    orch.run(_chain_specs(config_copy, outputs, calls))
    assert calls == []
    assert all(
        orch.manifest.phases[n].config_fingerprint == _fingerprints(config_copy)[n] for n in CHAIN
    )
    _edit(config_copy, "experiments.yaml", "nominal: 3000.0", "nominal: 2500.0")
    _orchestrator(outputs, "run-3").run(_chain_specs(config_copy, outputs, calls))
    assert calls == CHAIN


@pytest.mark.unit
def test_a_phase_without_a_fingerprint_is_never_checked(tmp_path, config_copy):
    outputs = tmp_path / "out"
    outputs.mkdir()
    calls: list[str] = []

    def bare():
        return [
            PhaseSpec(**{**s.__dict__, "config_fingerprint": None})
            for s in _chain_specs(config_copy, outputs, calls)
        ]

    _orchestrator(outputs, "run-1").run(bare())
    calls.clear()
    _edit(config_copy, "experiments.yaml", "nominal: 3000.0", "nominal: 2500.0")
    _orchestrator(outputs, "run-2").run(bare())
    assert calls == []


@pytest.mark.unit
def test_revalidate_refuses_a_phase_whose_configuration_changed(tmp_path, config_copy):
    outputs = tmp_path / "out"
    outputs.mkdir()
    calls: list[str] = []
    _orchestrator(outputs, "run-1").run(_chain_specs(config_copy, outputs, calls))
    orch = _orchestrator(outputs, "run-2")
    orch.manifest.phases["technical_potential"] = orch.manifest.phases[
        "technical_potential"
    ].model_copy(
        update={
            "status": "stale_upstream",
            "invalidated_by": "land_eligibility",
            "invalidated_in_run": "run-1",
        }
    )
    _edit(config_copy, "experiments.yaml", "nominal: 3000.0", "nominal: 2500.0")
    changed = _chain_specs(config_copy, outputs, calls)
    orch.revalidate_phases = ["technical_potential"]
    with pytest.raises(ValueError, match="configuration it reads changed"):
        orch.run(changed)


@pytest.mark.unit
def test_a_slope_limit_reaches_f1b_and_a_wildcard_step_selects_every_child(config_copy):
    before = _fingerprints(config_copy)
    text = (config_copy / "experiments.yaml").read_text(encoding="utf-8")
    start = text.index("slope_max_deg:")
    nominal = text.index("nominal:", start)
    end = text.index("\n", nominal)
    value = text[nominal + len("nominal:") : end].strip()
    (config_copy / "experiments.yaml").write_text(
        text[: nominal + len("nominal:")] + f" {float(value) + 1}" + text[end:], encoding="utf-8"
    )
    changed = _changed(before, _fingerprints(config_copy))
    assert {"data_quality_audit", "land_eligibility"} <= changed
    payload = phase_config_payload("data_quality_audit", "PRT", _source(config_copy))
    (selector,) = payload["experiments"]
    assert set(payload["experiments"][selector]) == {"solar", "wind"}
