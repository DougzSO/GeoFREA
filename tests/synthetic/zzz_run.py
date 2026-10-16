"""Shared set-up of the synthetic runs on a scratch data directory (ZZZ2; also used to size F5 to F8 at the BRA scale, COMMAND 39).

`prepare_configuration` writes, into the scratch directory, the copies of the registries that a synthetic run needs: the technologies file with the synthetic IEC rule (the
real one is null until OQ-005 closes), the experiments file with the test values of the pre-registered settings (null in the real file), and the parameters file with the
test values of a synthetic world. `run_pipeline` runs the orchestrator on them with every socket connection refused, and returns the results.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
CURVES = REPO / "tests" / "fixtures" / "power_curves"
PHASES = [
    "hazard_context",
    "technical_potential",
    "potential_maps",
    "lcoe_modeling",
    "sample_size_convergence",
    "robustness_analysis",
    "external_validation",
    "lcoe_maps",
    "robustness_maps",
    "results_synthesis",
]
F5_TO_F8 = PHASES[1:]


class NetworkUsedError(AssertionError):
    pass


def _no_network(*_args, **_kwargs):
    raise NetworkUsedError("the synthetic pipeline tried to open a network connection")


def refuse_network(patch) -> None:
    """Make every socket connection raise for the life of the `pytest.MonkeyPatch` / `unittest` patch object."""
    patch.setattr(socket.socket, "connect", _no_network)
    patch.setattr(socket, "create_connection", _no_network)


def experiments_text(
    initial_size: int, ceiling: int, country: str = "ZZZ", target_gw: float = 0.0001
) -> str:
    """`config/experiments.yaml` with the test values of the settings that are null until the author decides them (OQ-050, OQ-051, OQ-056).

    The values are the ones of `tests/synthetic/test_zzz_end_to_end.py`; the targets are for `country`.
    """
    text = (REPO / "config" / "experiments.yaml").read_text(encoding="utf-8")
    for old, new in (
        ("initial_size: 500", f"initial_size: {initial_size}"),
        ("max_size_for_convergence: null", f"max_size_for_convergence: {ceiling}"),
        ("tx35_days: {threshold: null,", "tx35_days: {threshold: 1.0,"),
        ("tx40_days: {threshold: null,", "tx40_days: {threshold: 1.0,"),
        ("rx5day_mm: {threshold: null,", "rx5day_mm: {threshold: 1.0,"),
        ("wet_p95_exceed_freq: {threshold: null,", "wet_p95_exceed_freq: {threshold: 0.0,"),
        ("gust_mean_annual_max_ms: {threshold: null,", "gust_mean_annual_max_ms: {threshold: 1.0,"),
        (
            "national_targets:\n",
            (
                "national_targets:\n"
                f"  {country}:\n"
                f'    solar: {{value: {target_gw}, unit: GW, source: "synthetic test value", horizon: 2040, alternatives: []}}\n'
                f'    wind: {{value: {target_gw}, unit: GW, source: "synthetic test value", horizon: 2040, alternatives: []}}\n'
            ),
        ),
        ("bootstrap_replicates: 200", "bootstrap_replicates: 10"),
        (
            'source: "OQ-050 (H5), pre-registered 2026-10-14"\n',
            (
                'source: "OQ-050 (H5), pre-registered 2026-10-14"\n'
                "  RQ4: [{statistic: mr_sr_kendall_tau_b, comparison: ge, threshold: -2.0}]\n"
            ),
        ),
    ):
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    return text


def prepare_configuration(
    data: Path,
    initial_size: int,
    ceiling: int,
    parameter_country: str = "ZZZ",
    parameter_changes: dict[str, dict[str, dict]] | None = None,
    experiments_country: str = "ZZZ",
) -> dict[str, Path]:
    """Write the three registries into `data` and return their paths (`technologies`, `experiments`, `parameters`).

    `parameter_country`: the country whose block of `parameters.json` becomes the ZZZ test block (the BRA sizing run reads the ZZZ test values for BRA).
    `parameter_changes`: `{technology: {parameter: {"value": v, "min": a, "max": b}}}` applied to that block (min and max only when the parameter has a range).
    """
    registry = yaml.safe_load((REPO / "config" / "technologies.yaml").read_text(encoding="utf-8"))
    registry["wind"]["power_curve"] = "synthetic_curve"
    technologies = data / "technologies_with_synthetic_rule.yaml"
    technologies.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    experiments = data / "experiments_zzz.yaml"
    experiments.write_text(
        experiments_text(initial_size, ceiling, experiments_country), encoding="utf-8"
    )

    document = json.loads((REPO / "config" / "parameters.json").read_text(encoding="utf-8"))
    block = json.loads(json.dumps(document["countries"]["ZZZ"]))
    for tech, changes in (parameter_changes or {}).items():
        for name, change in changes.items():
            entry = block["technologies"][tech][name]
            entry["value"] = change["value"]
            if "min" in change:
                entry["range"]["min"], entry["range"]["max"] = change["min"], change["max"]
    document["countries"][parameter_country] = block
    parameters = data / "parameters_synthetic.json"
    parameters.write_text(json.dumps(document, indent=1), encoding="utf-8")
    return {"technologies": technologies, "experiments": experiments, "parameters": parameters}
