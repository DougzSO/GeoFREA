"""`scripts/restamp_parquet2.py` compares by value and fails closed (COMMAND 134, OQ-084)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "restamp_parquet2.py"


@pytest.fixture(scope="module")
def restamp():
    spec = importlib.util.spec_from_file_location("restamp_parquet2", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["restamp_parquet2"] = module
    spec.loader.exec_module(module)
    return module


def _write(path, names, values, large=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    typ = pa.large_string() if large else pa.string()
    pq.write_table(pa.table({"name": pa.array(names, type=typ), "v": pa.array(values, type=pa.float64())}), path)
    return path


@pytest.mark.unit
def test_the_arrow_type_is_ignored_and_the_value_is_not(restamp, tmp_path):
    a = _write(tmp_path / "a.parquet", ["x", "y"], [1.0, float("nan")], large=True)
    b = _write(tmp_path / "b.parquet", ["x", "y"], [1.0, float("nan")], large=False)
    c = _write(tmp_path / "c.parquet", ["x", "y"], [1.0, 2.0])
    assert restamp.values_equal(a, b)[0] is True  # large_string against string, NaN against NaN
    ok, why, rows, cols = restamp.values_equal(a, c)
    assert ok is False and "'v'" in why and rows == 2 and cols == 2


@pytest.mark.unit
def test_an_entry_without_a_reference_copy_or_with_other_bytes_is_a_problem(restamp, tmp_path):
    root, snapshot = tmp_path / "data", tmp_path / "snap"
    rel = "outputs/ZZZ/t.parquet"
    f = _write(root / rel, ["x"], [1.0])
    entry = {"path": {"rel": rel}, "sha256": restamp._sha256(f), "content_sha256": restamp.content_hash(f, "parquet")}
    assert "no reference copy" in restamp.check_entry("ZZZ", "t", entry, snapshot, root)["problem"]
    _write(snapshot / rel, ["x"], [9.0])
    assert "value differs" in restamp.check_entry("ZZZ", "t", entry, snapshot, root)["problem"]
    _write(snapshot / rel, ["x"], [1.0], large=True)
    found = restamp.check_entry("ZZZ", "t", entry, snapshot, root)
    assert found["ok"] and found["new"].startswith("parquet2:") and found["previous"].startswith("parquet:")
    assert "bytes of the file" in restamp.check_entry("ZZZ", "t", {**entry, "sha256": "0" * 64}, snapshot, root)["problem"]
    assert restamp.check_entry("ZZZ", "t", {**entry, "content_sha256": found["new"]}, snapshot, root)["skip"]


@pytest.mark.unit
def test_the_hash_of_the_manifest_saved_before_the_round_can_stand_for_the_reference_copy(restamp, tmp_path):
    """COMMAND 178: without a copy of the file, the same `parquet:` hash (Arrow type and value) in the earlier manifest is the proof; any difference is a problem."""
    root = tmp_path / "data"
    rel = "outputs/ZZZ/t.parquet"
    f = _write(root / rel, ["x", "y"], [1.0, 2.0])
    recorded = restamp.content_hash(f, "parquet")
    entry = {"path": {"rel": rel}, "sha256": restamp._sha256(f), "content_sha256": recorded}
    before_path = tmp_path / "before" / "manifest_ZZZ.json"
    before_path.parent.mkdir()
    before_path.write_text("{}", encoding="utf-8")

    found = restamp.check_entry_by_hash("ZZZ", "t", entry, {"artifacts": {"t": {"content_sha256": recorded}}}, before_path, root)
    assert found["ok"] and found["new"].startswith("parquet2:") and found["compared"] == "hash"
    assert found["n_rows"] == 2 and found["n_columns"] == 2 and found["reference_copy"] == "manifest:manifest_ZZZ.json"
    assert restamp.proof(found, "now")["compared"] == "hash"

    other = {"artifacts": {"t": {"content_sha256": "parquet:" + "0" * 64}}}
    assert "differs from the one in the manifest" in restamp.check_entry_by_hash("ZZZ", "t", entry, other, before_path, root)["problem"]
    assert "no entry" in restamp.check_entry_by_hash("ZZZ", "t", entry, {"artifacts": {}}, before_path, root)["problem"]
    assert "no entry" in restamp.check_entry_by_hash("ZZZ", "t", entry, None, before_path, root)["problem"]
    assert "bytes of the file" in restamp.check_entry_by_hash("ZZZ", "t", {**entry, "sha256": "0" * 64}, {"artifacts": {"t": {"content_sha256": recorded}}}, before_path, root)["problem"]
    assert restamp.check_entry_by_hash("ZZZ", "t", {**entry, "content_sha256": found["new"]}, None, before_path, root)["skip"]


@pytest.mark.unit
def test_a_restamp_never_lowers_the_schema_of_the_manifest(restamp):
    """COMMAND 178: the first run of the script wrote 2.12 over manifests of 2.13, which the model refuses."""
    assert restamp.schema_after_restamp("2.13") == "2.13"
    assert restamp.schema_after_restamp("2.12") == "2.12"
    assert restamp.schema_after_restamp("2.11") == "2.12"
    assert restamp.schema_after_restamp("2.9") == "2.12"
    assert restamp.schema_after_restamp(None) == "2.12"
