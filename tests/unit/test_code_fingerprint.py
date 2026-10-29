"""The code fingerprint of a phase (COMMAND 58, A-02, manifest 2.6): a change of a calculation invalidates the phase and what imports it, a
comment or a docstring does not, and the manifest runs the phase again when the recorded fingerprint differs."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

import geofrea
from geofrea.core.code_fingerprint import (
    INFRASTRUCTURE_MODULES,
    PHASE_CODE_ROOTS,
    code_fingerprint,
    normalised_source,
    phase_modules,
)
from geofrea.core.config_fingerprint import PHASE_CONFIG_SCOPE
from geofrea.core.orchestrator import Orchestrator, PhaseSpec

pytestmark = pytest.mark.unit

SRC = Path(geofrea.__file__).resolve().parent
CHAIN = [
    "land_eligibility",
    "technical_potential",
    "lcoe_modeling",
    "robustness_analysis",
    "external_validation",
    "results_synthesis",
]
FRACTIONS_LINE = "    top = transform.f + row0 * transform.e\n"


@pytest.fixture
def source_copy(tmp_path) -> Path:
    target = tmp_path / "geofrea"
    shutil.copytree(SRC, target, ignore=shutil.ignore_patterns("__pycache__"))
    return target


def _all(root: Path) -> dict[str, str]:
    return {phase: code_fingerprint(phase, root) for phase in PHASE_CODE_ROOTS}


def _changed(before: dict[str, str], after: dict[str, str]) -> set[str]:
    return {p for p in before if before[p] != after[p]}


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (path.name, old, text.count(old))
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_every_phase_with_a_config_scope_has_code_roots_and_the_roots_exist():
    assert set(PHASE_CODE_ROOTS) == set(PHASE_CONFIG_SCOPE)
    for phase in PHASE_CODE_ROOTS:
        modules = phase_modules(phase)
        assert modules, phase
        for root in PHASE_CODE_ROOTS[phase]:
            assert any(m == root or m.startswith(root + ".") for m in modules), (phase, root)


def test_the_closure_of_a_phase_holds_its_package_and_the_core_modules_it_imports():
    modules = set(phase_modules("land_eligibility"))
    assert {
        "land_eligibility.fractions",
        "land_eligibility.pipeline",
        "core.geo_utils",
        "core.paths",
    } <= modules
    assert not modules & INFRASTRUCTURE_MODULES
    assert "climate_forcing.forcing" not in modules and "lcoe_modeling.kernel" not in modules


def test_a_calculation_line_of_f3_changes_the_phases_that_run_that_module_and_not_the_phases_before_it(
    source_copy,
):
    before = _all(source_copy)
    _edit(
        source_copy / "land_eligibility" / "fractions.py",
        FRACTIONS_LINE,
        "    top = transform.f + row1 * transform.e\n",
    )
    changed = _changed(before, _all(source_copy))
    assert changed == {
        p for p in PHASE_CODE_ROOTS if "land_eligibility.fractions" in phase_modules(p, source_copy)
    }
    assert "land_eligibility" in changed
    assert not changed & {
        "data_acquisition",
        "data_quality_audit",
        "grid_alignment",
        "climate_forcing",
    }


def test_with_the_real_fingerprints_an_f3_calculation_change_reruns_f3_and_its_changed_output_reaches_f8(
    tmp_path, source_copy
):
    """The code fingerprint reruns F3; F5 to F8 do not import `fractions`, they follow the content F3 writes (A-02)."""
    outputs = tmp_path / "out"
    outputs.mkdir()
    calls: list[str] = []
    code = {n: code_fingerprint(n, source_copy) for n in CHAIN}
    _orchestrator(outputs, "run-1").run(_specs(outputs, calls, code, value=1))
    calls.clear()
    _edit(
        source_copy / "land_eligibility" / "fractions.py",
        FRACTIONS_LINE,
        "    top = transform.f + row1 * transform.e\n",
    )
    code = {n: code_fingerprint(n, source_copy) for n in CHAIN}
    _orchestrator(outputs, "run-2").run(
        _specs(outputs, calls, code, value=2)
    )  # the edited calculation gives another artifact
    assert calls == CHAIN
    calls.clear()
    _edit(
        source_copy / "land_eligibility" / "fractions.py",
        "    top = transform.f + row1 * transform.e\n",
        "    # same result, another comment\n    top = transform.f + row1 * transform.e\n",
    )
    code = {n: code_fingerprint(n, source_copy) for n in CHAIN}
    _orchestrator(outputs, "run-3").run(_specs(outputs, calls, code, value=2))
    assert calls == []  # only a comment: nothing runs


def test_a_comment_a_docstring_a_blank_line_or_a_reformat_does_not_change_any_fingerprint(
    source_copy,
):
    before = _all(source_copy)
    path = source_copy / "land_eligibility" / "fractions.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        FRACTIONS_LINE,
        "    # the top edge of the window\n" + FRACTIONS_LINE.replace(" = ", "  =  ") + "\n\n",
    )
    text = (
        '"""Another module docstring."""\n' + text.split('"""', 2)[2].lstrip("\n")
        if text.startswith('"""')
        else text
    )
    path.write_text(text, encoding="utf-8")
    other = source_copy / "core" / "geo_utils.py"
    other.write_text(
        other.read_text(encoding="utf-8") + "\n\n# a trailing comment\n", encoding="utf-8"
    )
    assert _changed(before, _all(source_copy)) == set()


def test_a_core_module_changes_only_the_phases_that_import_it(source_copy):
    before = _all(source_copy)
    _edit(
        source_copy / "core" / "geodesy.py",
        "    return lat_km_per_deg, lon_km_per_deg\n",
        "    return lat_km_per_deg * 1.0001, lon_km_per_deg\n",
    )
    expected = {p for p in PHASE_CODE_ROOTS if "core.geodesy" in phase_modules(p, source_copy)}
    assert expected  # at least one phase uses it
    assert _changed(before, _all(source_copy)) == expected
    assert "data_acquisition" not in expected or "core.geodesy" in phase_modules("data_acquisition")


def test_the_manifest_infrastructure_does_not_change_a_fingerprint(source_copy):
    before = _all(source_copy)
    path = source_copy / "core" / "orchestrator.py"
    path.write_text(path.read_text(encoding="utf-8") + "\nSOMETHING = 1\n", encoding="utf-8")
    assert _changed(before, _all(source_copy)) == set()


def test_normalised_source_drops_docstrings_and_comments_but_not_expressions():
    a = 'def f(x):\n    """Doc."""\n    # comment\n    return x+1\n'
    b = 'def f(x):\n    """Another doc, longer."""\n    return (x + 1)\n'
    c = 'def f(x):\n    """Doc."""\n    return x + 2\n'
    assert normalised_source(a) == normalised_source(b) != normalised_source(c)
    assert normalised_source("def f(:") == "def f(:"  # an unparsable file counts by its text


# ─── the resume ──────────────────────────────────────────────────────────


class Out(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int


def _specs(
    outputs: Path, calls: list[str], code: dict[str, str | None], value: int = 1
) -> list[PhaseSpec]:
    specs, previous = [], None
    for name in CHAIN:

        def run(context, name=name):
            calls.append(name)
            path = outputs / f"{name}.txt"
            path.write_text(f"{name}-{value}" if name == CHAIN[0] else name, encoding="utf-8")
            context.register_artifact(name, path, "1.0")
            return Out(value=value)

        specs.append(
            PhaseSpec(
                name=name,
                output_model=Out,
                run=run,
                requires=frozenset({previous}) if previous else frozenset(),
                produces=frozenset({name}),
                code_fingerprint=code[name],
            )
        )
        previous = name
    return specs


def _orchestrator(outputs: Path, run_id: str) -> Orchestrator:
    from geofrea.core.config_loader import load_parameters

    repo = SRC.parents[1]
    return Orchestrator(
        outputs_dir=outputs,
        country_code="PRT",
        country_params=load_parameters(repo / "config" / "parameters.json").countries["PRT"],
        target_phases=[CHAIN[-1]],
        rerun_phases=[],
        run_id=run_id,
        methodology_version="test-1.0.0",
        dirty=False,
    )


def test_a_changed_code_fingerprint_reruns_the_phase_and_a_consumer_stays_when_the_content_is_identical(
    tmp_path,
):
    outputs = tmp_path / "out"
    outputs.mkdir()
    calls: list[str] = []
    code = {n: f"code-{n}" for n in CHAIN}
    _orchestrator(outputs, "run-1").run(_specs(outputs, calls, code))
    assert calls == CHAIN
    calls.clear()
    _orchestrator(outputs, "run-2").run(_specs(outputs, calls, code))
    assert calls == []  # same code: everything resumes
    # a change of the code of F5 only: F5 runs again, its artifact is identical, so F6 to F8 stay
    code["technical_potential"] = "code-technical_potential-v2"
    orch = _orchestrator(outputs, "run-3")
    orch.run(_specs(outputs, calls, code))
    assert calls == ["technical_potential"]
    assert (
        orch.manifest.phases["technical_potential"].code_fingerprint
        == "code-technical_potential-v2"
    )


def test_a_code_change_that_changes_the_artifact_marks_the_consumers_stale_and_they_run_again(
    tmp_path,
):
    outputs = tmp_path / "out"
    outputs.mkdir()
    calls: list[str] = []
    code = {n: f"code-{n}" for n in CHAIN}
    _orchestrator(outputs, "run-1").run(_specs(outputs, calls, code, value=1))
    calls.clear()
    code["land_eligibility"] = (
        "code-land_eligibility-v2"  # F3 changes and now writes another artifact
    )
    orch = _orchestrator(outputs, "run-2")
    orch.run(_specs(outputs, calls, code, value=2))
    assert calls == CHAIN  # F3 by its code, F4..F8 by the content of what they read


def test_an_entry_without_a_code_fingerprint_is_resumed_once_and_adopts_the_current_one(tmp_path):
    outputs = tmp_path / "out"
    outputs.mkdir()
    calls: list[str] = []
    _orchestrator(outputs, "run-1").run(_specs(outputs, calls, dict.fromkeys(CHAIN)))
    calls.clear()
    code = {n: f"code-{n}" for n in CHAIN}
    orch = _orchestrator(outputs, "run-2")
    orch.run(_specs(outputs, calls, code))
    assert calls == []
    assert all(orch.manifest.phases[n].code_fingerprint == code[n] for n in CHAIN)
    code["lcoe_modeling"] = "changed"
    _orchestrator(outputs, "run-3").run(_specs(outputs, calls, code))
    assert calls == ["lcoe_modeling"]


def test_a_phase_without_a_code_fingerprint_is_never_checked(tmp_path):
    outputs = tmp_path / "out"
    outputs.mkdir()
    calls: list[str] = []
    _orchestrator(outputs, "run-1").run(_specs(outputs, calls, {n: f"c-{n}" for n in CHAIN}))
    calls.clear()
    _orchestrator(outputs, "run-2").run(_specs(outputs, calls, dict.fromkeys(CHAIN)))
    assert calls == []


def test_revalidate_refuses_a_phase_whose_code_changed(tmp_path):
    outputs = tmp_path / "out"
    outputs.mkdir()
    calls: list[str] = []
    code = {n: f"code-{n}" for n in CHAIN}
    _orchestrator(outputs, "run-1").run(_specs(outputs, calls, code))
    orch = _orchestrator(outputs, "run-2")
    entry = orch.manifest.phases["technical_potential"]
    orch.manifest.phases["technical_potential"] = entry.model_copy(
        update={"status": "stale_upstream"}
    )
    changed = _specs(outputs, calls, {**code, "technical_potential": "other"})
    with pytest.raises(ValueError, match="code it runs changed"):
        orch._revalidate(next(s for s in changed if s.name == "technical_potential"))


# ─── the digests kept between runs (COMMAND 77, item 7) ──────────────────────────────────────────────────────────────────────────────


def _fresh_store(monkeypatch, tmp_path):
    from geofrea.core import code_fingerprint as cf

    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(cf, "_store", None)
    monkeypatch.setattr(cf, "_store_dirty", False)
    cf._file_digest_cached.cache_clear()
    return cf


def test_the_fingerprint_with_the_store_equals_the_fingerprint_without_it(tmp_path, monkeypatch):
    from geofrea.core import code_fingerprint as cf

    monkeypatch.delenv("GEOFREA_DATA_DIR", raising=False)
    monkeypatch.setattr(cf, "_store", None)
    cf._file_digest_cached.cache_clear()
    without = cf.closure_fingerprint(("core.geometry_memo",))

    cf = _fresh_store(monkeypatch, tmp_path)
    cold = cf.closure_fingerprint(("core.geometry_memo",))
    cf._save_store()
    assert (tmp_path / "interim" / "_code_digest_cache.json").exists()

    cf = _fresh_store(monkeypatch, tmp_path)  # a new process: empty lru, the file in place
    monkeypatch.setattr(cf, "normalised_source", lambda *a, **k: (_ for _ in ()).throw(AssertionError("normalised again")))
    warm = cf.closure_fingerprint(("core.geometry_memo",))
    assert without == cold == warm


def test_a_changed_file_or_a_changed_normalisation_is_not_read_from_the_store(tmp_path, monkeypatch):
    cf = _fresh_store(monkeypatch, tmp_path)
    source = tmp_path / "m.py"
    source.write_text("x = 1\n", encoding="utf-8")
    first = cf._file_digest_cached(str(source), source.stat().st_mtime_ns, source.stat().st_size, False)
    cf._save_store()
    source.write_text("x = 22\n", encoding="utf-8")  # same name, other size
    cf._file_digest_cached.cache_clear()
    again = cf._file_digest_cached(str(source), source.stat().st_mtime_ns, source.stat().st_size, False)
    assert again != first

    cf = _fresh_store(monkeypatch, tmp_path)
    monkeypatch.setattr(cf, "_store_identity", lambda: "another normalisation")
    assert cf._load_store()["digest"] == {}
