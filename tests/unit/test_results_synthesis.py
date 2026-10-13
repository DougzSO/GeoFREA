"""F8 results_synthesis: names, the artifact reader, the writers and the guard that F8 only reads (M-F8-01, M-F8-02)."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from geofrea.core.config_loader import load_experiments, load_parameters, load_technologies
from geofrea.core.tables import write_table
from geofrea.results_synthesis import names
from geofrea.results_synthesis.inputs import ArtifactReader, MissingArtifactError, ThesisInputError
from geofrea.results_synthesis.method_tables import ThesisValueError, check_values
from geofrea.results_synthesis.output import (
    BuildContext,
    NotBuilt,
    latex_escape,
    latex_table,
    methodology_version,
)
from geofrea.results_synthesis.output import (
    write_table as write_output_table,
)
from geofrea.technical_potential.table_schemas import PotentialAggregateRow

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src" / "geofrea" / "results_synthesis"

# What F8 may import from the rest of the package: configuration, paths and table contracts, and the shared map style. Anything else
# (a kernel, an evaluator, the eligibility engine, a pipeline) would be a way to recompute a scientific quantity (M-F8-01).
ALLOWED_IMPORTS = (
    "geofrea.core",
    "geofrea.results_synthesis",
    "geofrea.overview.style",
    "geofrea.land_eligibility.parameters",
    "geofrea.external_validation.table_schemas",
    "geofrea.lcoe_modeling.table_schemas",
    "geofrea.technical_potential.table_schemas",
    "geofrea.robustness_analysis.table_schemas",
)
FORBIDDEN_MODULES = (
    "geofrea.lcoe_modeling.kernel",
    "geofrea.lcoe_modeling.inputs",
    "geofrea.lcoe_modeling.pipeline",
    "geofrea.robustness_analysis.evaluator",
    "geofrea.robustness_analysis.futures",
    "geofrea.robustness_analysis.hypotheses",
    "geofrea.robustness_analysis.h1_rank_robustness",
    "geofrea.robustness_analysis.rankings",
    "geofrea.robustness_analysis.pipeline",
    "geofrea.robustness_analysis.prim",
    "geofrea.technical_potential.pipeline",
    "geofrea.land_eligibility.pipeline",
    "geofrea.climate_forcing.pipeline",
    "geofrea.external_validation.pipeline",
)


# -- names ---------------------------------------------------------------------------------------------------------


@pytest.mark.unit
def test_names_follow_the_thesis_convention():
    assert names.stem("T-R4", "max_regret", "BRA", "solar") == "T-R4_max_regret_BRA_solar"
    assert names.stem("T-R8", "synthesis") == "T-R8_synthesis"
    for bad in (("T-R99", "x"), ("T-R4", "Max regret"), ("T-R4", "_x"), ("R4", "x")):
        with pytest.raises(names.OutputNameError):
            names.stem(*bad)
    assert names.OPTIONAL == {"T-O1", "T-O2"} and len(names.THESIS_IDS) == 18


# -- the artifact reader -------------------------------------------------------------------------------------------


def _register(
    data: Path,
    iso: str,
    key: str,
    rel: str,
    schema_version: str | None,
    content: bytes | None = None,
):
    """A manifest with one artifact: a Parquet table with `schema_version` (or any bytes) at `rel`."""
    path = data / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if content is None:
        frame = pd.DataFrame(
            {
                "scenario": ["central"],
                "member": ["m0"],
                "n_cells": [1],
                "n_cells_absent": [0],
                "n_cells_like_for_like": [1],
                "eligible_area_km2": [1.0],
                "P_GW": [1.0],
                "E_TWh": [1.0],
                "cf_energy_weighted": [0.3],
                "P_GW_like_for_like": [1.0],
                "E_TWh_like_for_like": [1.0],
                "delta_E_pct_vs_m0_like_for_like": [None],
            }
        )
        write_table(frame, path, schema_version=schema_version, row_model=PotentialAggregateRow)
    else:
        path.write_bytes(content)
    manifest = data / "outputs" / iso / "manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "artifacts": {
                    key: {
                        "path": {"root": "data", "rel": rel},
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.unit
def test_the_reader_returns_a_registered_table_and_records_its_hash(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    _register(tmp_path, "ZZZ", "potential_aggregates_solar", "outputs/ZZZ/a.parquet", "1.0")
    reader = ArtifactReader("ZZZ")
    table = reader.table("potential_aggregates_solar", {"1.0"})
    assert table["P_GW"].iloc[0] == 1.0
    assert set(reader.used) == {"potential_aggregates_solar"} and reader.available


@pytest.mark.unit
def test_the_reader_refuses_an_unknown_schema_version_a_missing_key_and_a_changed_file(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    path = _register(tmp_path, "ZZZ", "k", "outputs/ZZZ/a.parquet", "9.9")
    reader = ArtifactReader("ZZZ")
    with pytest.raises(ThesisInputError, match="schema version"):
        reader.table("k", {"1.0"})
    with pytest.raises(MissingArtifactError):
        reader.path("other")
    path.write_bytes(path.read_bytes() + b"x")
    with pytest.raises(ThesisInputError, match="changed since it was registered"):
        ArtifactReader("ZZZ").path("k")
    assert not ArtifactReader(
        "QQQ"
    ).available  # no manifest: nothing is available, and nothing is invented


# -- writers -------------------------------------------------------------------------------------------------------


@pytest.mark.unit
def test_latex_is_escaped_and_missing_values_are_dashes():
    assert latex_escape("a_b & 5% #1") == r"a\_b \& 5\% \#1"
    frame = pd.DataFrame({"name": ["x_y"], "value": [float("nan")], "n": [3], "flag": [True]})
    text = latex_table(frame, "A caption_with underscore", "tab:x")
    assert (
        r"x\_y & -- & 3 & yes" in text
        and r"\toprule" in text
        and r"\caption{A caption\_with underscore}" in text
    )
    assert r"\begin{tabular}{lrrl}" in text


def _context(tmp_path: Path, test_values: bool) -> BuildContext:
    return BuildContext(
        iso="ZZZ",
        technologies=("solar",),
        reader=ArtifactReader("ZZZ"),
        other_scale=None,
        out_dir=tmp_path / "thesis",
        config_files={"parameters.json": REPO / "config" / "parameters.json"},
        methodology_version=methodology_version(REPO / "docs" / "METHODOLOGY.md"),
        registry=load_technologies(REPO / "config" / "technologies.yaml"),
        experiments=load_experiments(REPO / "config" / "experiments.yaml"),
        country_params=load_parameters(REPO / "config" / "parameters.json").countries["ZZZ"],
        test_values=test_values,
    )


@pytest.mark.unit
def test_a_table_is_written_with_a_provenance_file_that_holds_no_time_and_no_path(tmp_path):
    ctx = _context(tmp_path, test_values=True)
    files = write_output_table(
        ctx, "T-R2", "potential", pd.DataFrame({"a": [1.5]}), "Caption.", technology="solar"
    )
    assert [f.name for f in files] == [
        "T-R2_potential_ZZZ_solar.csv",
        "T-R2_potential_ZZZ_solar.tex",
        "T-R2_potential_ZZZ_solar.provenance.json",
    ]
    provenance = json.loads(files[-1].read_text(encoding="utf-8"))
    assert provenance["caption"] == "TEST VALUES (synthetic fixture, not a result). Caption."
    assert (
        provenance["test_values"] is True and "parameters.json" in provenance["config_files_read"]
    )
    text = files[-1].read_text(encoding="utf-8")
    assert str(tmp_path) not in text and "timestamp" not in text
    ctx.out_dir.joinpath("x").mkdir()
    assert (
        write_output_table(ctx, "T-R2", "units", pd.DataFrame({"a": [1]}), "c.", latex=False)[
            0
        ].suffix
        == ".csv"
    )
    assert not (ctx.out_dir / "T-R2_units_ZZZ.tex").exists()


@pytest.mark.unit
def test_a_thesis_build_refuses_test_values_and_a_test_build_accepts_them(tmp_path):
    with pytest.raises(ThesisValueError, match="test value in a thesis build"):
        check_values(_context(tmp_path, test_values=False), "solar")
    check_values(
        _context(tmp_path, test_values=True), "solar"
    )  # a fixture is built as a test build
    assert NotBuilt  # the exception a script raises to say why an output is not built


# -- F8 only reads --------------------------------------------------------------------------------------------------


def _imports(path: Path) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("geofrea"):
            found.append(node.module)
        elif isinstance(node, ast.Import):
            found += [a.name for a in node.names if a.name.startswith("geofrea")]
    return found


@pytest.mark.unit
def test_f8_imports_no_kernel_evaluator_or_pipeline():
    offenders = {
        f"{path.name}: {module}": None
        for path in sorted(SRC.glob("*.py"))
        for module in _imports(path)
        if not module.startswith(ALLOWED_IMPORTS)
    }
    assert not offenders, sorted(offenders)


@pytest.mark.unit
def test_loading_the_f8_runner_loads_no_module_that_recomputes_a_scientific_quantity():
    code = (
        "import sys, json; import geofrea.results_synthesis.runner; "
        f"bad = [m for m in {list(FORBIDDEN_MODULES)!r} if m in sys.modules]; print(json.dumps(bad))"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", code],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO,
        env={
            "PYTHONPATH": str(REPO / "src"),
            "PATH": "",
            "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""),
        },
    )
    assert json.loads(result.stdout.strip().splitlines()[-1]) == []


@pytest.mark.unit
def test_f8_source_carries_no_country_or_technology_literal():
    banned = {"BRA", "PRT", "IND", "ZZZ", "solar", "wind"}
    offenders = []
    for path in sorted(SRC.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value.strip() in banned
            ):
                offenders.append((path.name, node.lineno, node.value))
    assert not offenders, offenders


@pytest.mark.unit
def test_the_t_r6_verdict_row_takes_the_primary_statistic_reference_threshold_and_verdict():
    from geofrea.results_synthesis.robustness_tables import VERDICT_COLUMNS, _verdict_row

    base = {"scale": "0p05deg", "role": "core", "window": "2041-2070"}
    h1 = pd.Series(
        base
        | {
            "c_k": 0.7,
            "v_k": 0.1,
            "reference": 0.01,
            "alpha": 0.6,
            "beta": 0.2,
            "verdict": "partially_supported",
        }
    )
    h2 = pd.Series(
        base | {"overlap": 0.2, "overlap_ref": 0.1, "gamma": 0.3, "verdict": "supported"}
    )
    h3 = pd.Series(base | {"d": 0.3, "d_ref": 0.9, "delta": 0.2, "verdict": "supported"})
    rows = [_verdict_row(name, row) for name, row in (("H1", h1), ("H2", h2), ("H3", h3))]
    assert all(set(row) == set(VERDICT_COLUMNS) for row in rows)
    first, second, third = rows
    assert (first["statistic"], first["value"], first["reference"], first["threshold"]) == (
        "h1a_core_share",
        0.7,
        0.01,
        0.6,
    )
    assert (first["statistic_2"], first["value_2"], first["threshold_2"]) == (
        "h1b_vulnerable_share",
        0.1,
        0.2,
    )
    assert first["verdict"] == "partially_supported"
    assert (second["statistic"], second["value"], second["reference"], second["threshold"]) == (
        "h2_overlap_index",
        0.2,
        0.1,
        0.3,
    )
    assert (third["statistic"], third["value"], third["reference"], third["threshold"]) == (
        "h3_beyond_reach_share",
        0.3,
        0.9,
        0.2,
    )
    assert third["verdict"] == "supported" and second["statistic_2"] is None
