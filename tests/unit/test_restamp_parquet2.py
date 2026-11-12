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
