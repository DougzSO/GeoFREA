"""scripts/adopt_aligned_cache_keys.py: the aligned layers made under an earlier code are adopted under the current one, not computed again (COMMAND 75)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

import geofrea.grid_alignment.alignment as alignment_module
import geofrea.grid_alignment.raster_alignment as raster_alignment_module
from geofrea.grid_alignment.alignment import run_grid_alignment_phase
from tests.unit.test_grid_alignment_alignment import (
    _SP,
    _context,
    _country_gdf,
    _inputs,
    _write_dem_tile,
)

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "adopt_aligned_cache_keys.py"


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path / "data_dir"))


@pytest.fixture(autouse=True)
def _small_glo30_tiles(monkeypatch):
    monkeypatch.setattr(raster_alignment_module, "_GLO30_SAMPLES_PER_DEGREE", _SP)


def _script():
    spec = importlib.util.spec_from_file_location("adopt_aligned_cache_keys", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _phase(tmp_path):
    inputs = _inputs(slope_dem_tiles=_write_dem_tile(tmp_path, 55.0), country_gdf=_country_gdf())
    context = _context(tmp_path)
    return context, inputs, lambda: run_grid_alignment_phase(context, inputs)


def _artifacts(context) -> Path:
    return context.outputs_dir / context.country_code / "grid_alignment" / "artifacts"


def _calls(run) -> int:
    with patch.object(alignment_module, "glo30_aligned_outputs", wraps=alignment_module.glo30_aligned_outputs) as spy:
        run()
    return spy.call_count


def _layers_made_under(monkeypatch, tmp_path, code):
    monkeypatch.setattr(alignment_module, "cache_code", lambda name: code)
    context, inputs, run = _phase(tmp_path)
    assert _calls(run) == 1
    return context, run


def test_without_the_adoption_a_new_code_computes_every_layer_again(tmp_path, monkeypatch):
    context, run = _layers_made_under(monkeypatch, tmp_path, "code-before")
    monkeypatch.setattr(alignment_module, "cache_code", lambda name: "code-after")
    assert _calls(run) == 1


def test_the_layers_of_an_earlier_code_are_adopted_and_the_next_run_finds_them_current(tmp_path, monkeypatch):
    adopt = _script()
    context, run = _layers_made_under(monkeypatch, tmp_path, "code-before")
    keys_before = {p.name: p.read_text(encoding="utf-8") for p in _artifacts(context).glob("*_aligned.tif.cachekey")}
    assert keys_before
    monkeypatch.setattr(alignment_module, "cache_code", lambda name: "code-after")

    calls = []
    adopted = adopt.adopt(lambda: calls.append(_calls(run)), "code-before", _artifacts(context))
    assert calls == [0] and adopted  # the phase ran with every layer current under the old code: nothing was computed

    assert _calls(run) == 0  # the code of today finds them current
    assert sorted(p.name for p in _artifacts(context).glob("*.cachekey.before_adopt")) == sorted(f"{n}.before_adopt" for n in adopted)
    for sidecar in _artifacts(context).glob("*_aligned.tif.cachekey"):
        assert sidecar.read_text(encoding="utf-8") != keys_before[sidecar.name]  # the key of the current code


def test_a_layer_that_was_not_made_under_the_old_code_stops_the_adoption_before_anything_is_computed(tmp_path, monkeypatch):
    adopt = _script()
    context, run = _layers_made_under(monkeypatch, tmp_path, "some-other-code")
    monkeypatch.setattr(alignment_module, "cache_code", lambda name: "code-after")
    before = {p.name: p.read_text(encoding="utf-8") for p in _artifacts(context).glob("*.cachekey")}

    with patch.object(alignment_module, "glo30_aligned_outputs") as computed, pytest.raises(adopt.AdoptionError, match="not made under the code"):
        adopt.adopt(run, "code-before", _artifacts(context))

    computed.assert_not_called()
    assert {p.name: p.read_text(encoding="utf-8") for p in _artifacts(context).glob("*.cachekey")} == before
    assert not list(_artifacts(context).glob("*.before_adopt"))
    assert alignment_module.aligned_layer_key is not None and alignment_module.cache_is_current.__module__ == "geofrea.core.cache_key"  # restored


def test_the_cache_code_of_a_revision_is_that_of_its_tree():
    adopt = _script()
    from geofrea.core.cache_code import cache_code

    head = adopt.cache_code_at("HEAD")
    assert len(head) == 64 and head != adopt.cache_code_at("38e8da1")
    assert isinstance(cache_code("aligned_layers"), str)


def test_the_adoption_needs_a_proof_of_equality_for_exactly_these_two_codes():
    adopt = _script()
    good = {"equal": True, "n_equal": 28, "n_artifacts": 28, "sample": "PRT", "old_cache_code": "old", "new_cache_code": "new"}
    adopt.require_proof(good, "old", "new")
    with pytest.raises(adopt.AdoptionError, match="27 of 28"):
        adopt.require_proof({**good, "equal": False, "n_equal": 27}, "old", "new")
    with pytest.raises(adopt.AdoptionError, match="other code"):
        adopt.require_proof(good, "old", "newer")
    with pytest.raises(adopt.AdoptionError, match="other code"):
        adopt.require_proof(good, "older", "new")


def test_the_equivalence_check_compares_the_artifacts_of_the_phase_by_content_hash():
    check = importlib.util.module_from_spec(importlib.util.spec_from_file_location("check_aligned_equivalence", SCRIPT.parent / "proofs" / "check_aligned_equivalence.py"))
    check.__spec__.loader.exec_module(check)

    def manifest(**hashes):
        return {"artifacts": {k: {"phase": "grid_alignment" if not k.startswith("x_") else "other", "sha256": "bytes-" + v, "content_sha256": v or None} for k, v in hashes.items()}}

    same = check.compare_manifests(manifest(a="1", b="2", x_other="3"), manifest(a="1", b="2", x_other="9"))
    assert same["equal"] and same["n_artifacts"] == 2  # another phase's artifact is not compared
    differ = check.compare_manifests(manifest(a="1", b="2"), manifest(a="1", b="3"))
    assert not differ["equal"] and differ["n_equal"] == 1 and differ["artifacts"]["b"]["equal"] is False
    missing = check.compare_manifests(manifest(a="1", b="2"), manifest(a="1"))
    assert not missing["equal"] and missing["artifacts"]["b"]["new"] is None
    assert not check.compare_manifests({"artifacts": {}}, {"artifacts": {}})["equal"]  # nothing compared is not equal


@pytest.mark.unit
def test_restore_before_adopt_puts_back_the_key_of_the_revision(tmp_path):
    from scripts.adopt_aligned_cache_keys import restore_before_adopt

    (tmp_path / "A_aligned.tif.cachekey").write_text("adopted-key", encoding="utf-8")
    (tmp_path / "A_aligned.tif.cachekey.before_adopt").write_text("old-key", encoding="utf-8")
    (tmp_path / "B_aligned.tif.cachekey").write_text("never-adopted", encoding="utf-8")

    assert restore_before_adopt(tmp_path) == ["A_aligned.tif.cachekey"]
    assert (tmp_path / "A_aligned.tif.cachekey").read_text(encoding="utf-8") == "old-key"
    assert (tmp_path / "B_aligned.tif.cachekey").read_text(encoding="utf-8") == "never-adopted"


@pytest.mark.unit
def test_the_adopting_run_names_f2a_in_rerun_so_it_executes_when_its_manifest_entry_is_current():
    from scripts.adopt_aligned_cache_keys import phase_arguments

    args = phase_arguments("IND")
    assert args[0] == "IND" and args[args.index("--phases") + 1] == "grid_alignment" and args[args.index("--rerun") + 1] == "grid_alignment"


@pytest.mark.unit
def test_check_mode_resolves_the_revision_and_the_proof_without_adopting_or_running(monkeypatch, capsys, tmp_path):
    import json

    module = _script()
    from geofrea.core.cache_code import cache_code

    proof = tmp_path / "proof.json"
    proof.write_text(json.dumps({"equal": True, "old_cache_code": "old" * 4, "new_cache_code": cache_code("aligned_layers")}), encoding="utf-8")
    monkeypatch.setattr(module, "cache_code_at", lambda revision: "old" * 4)

    def must_not_run(*_args, **_kwargs):
        raise AssertionError("check mode ran something")

    monkeypatch.setattr(module, "adopt", must_not_run)
    assert module.main(["PRT", "--revision", "adopt-base-75", "--proof", str(proof), "--check"]) == 0
    assert "check only" in capsys.readouterr().out
