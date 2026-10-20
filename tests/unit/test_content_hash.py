"""The canonical content hash of an artifact and the staleness by content (COMMAND 58, A-02, manifest 2.6): a rewrite of the same data with
other file metadata does not mark a consumer stale; another value does."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import rasterio
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from pydantic import BaseModel, ConfigDict
from rasterio.transform import from_origin

from geofrea.core.content_hash import content_hash
from geofrea.core.orchestrator import Orchestrator, PhaseSpec

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[2]


def _write_parquet(
    path: Path, frame: pd.DataFrame, provenance: str, compression: str = "snappy"
) -> None:
    table = pa.Table.from_pandas(frame, preserve_index=False)
    table = table.replace_schema_metadata({"provenance": provenance})
    pq.write_table(table, path, compression=compression, row_group_size=2)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {"cell_id": [1, 2, 3, 4, 5], "P_MW": [0.5, 1.5, np.nan, 2.0, 4.25], "name": list("abcde")}
    )


def test_a_parquet_rewritten_with_other_metadata_has_other_bytes_and_the_same_content_hash(
    tmp_path,
):
    a, b = tmp_path / "a.parquet", tmp_path / "b.parquet"
    _write_parquet(a, _frame(), "run-1")
    _write_parquet(b, _frame(), "run-2 at another time", compression="zstd")
    assert a.read_bytes() != b.read_bytes()
    assert content_hash(a) == content_hash(b)
    assert content_hash(a).startswith("parquet:")


def test_a_parquet_with_one_value_or_one_type_changed_has_another_content_hash(tmp_path):
    a, b, c = tmp_path / "a.parquet", tmp_path / "b.parquet", tmp_path / "c.parquet"
    _write_parquet(a, _frame(), "x")
    changed = _frame()
    changed.loc[3, "P_MW"] = 2.0000001
    _write_parquet(b, changed, "x")
    retyped = _frame().astype({"cell_id": "int32"})
    _write_parquet(c, retyped, "x")
    assert len({content_hash(a), content_hash(b), content_hash(c)}) == 3
    reordered = _frame().iloc[::-1].reset_index(drop=True)
    _write_parquet(tmp_path / "d.parquet", reordered, "x")
    assert content_hash(tmp_path / "d.parquet") != content_hash(a)  # row order is content


def _write_tif(path: Path, data: np.ndarray, tags: dict[str, str], nodata: float = -9999.0) -> None:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(10.0, 50.0, 0.01, 0.01),
        nodata=nodata,
    ) as dst:
        dst.write(data.astype("float32"), 1)
        dst.update_tags(**tags)


def test_a_geotiff_ignores_tags_but_not_data_nodata_or_the_transform(tmp_path):
    data = np.arange(12, dtype="float32").reshape(3, 4)
    a, b = tmp_path / "a.tif", tmp_path / "b.tif"
    _write_tif(a, data, {"created": "monday"})
    _write_tif(b, data, {"created": "tuesday", "software": "x"})
    assert a.read_bytes() != b.read_bytes()
    assert content_hash(a) == content_hash(b)
    other = data.copy()
    other[1, 1] += 1
    _write_tif(tmp_path / "c.tif", other, {})
    _write_tif(tmp_path / "d.tif", data, {}, nodata=-1.0)
    assert (
        len({content_hash(a), content_hash(tmp_path / "c.tif"), content_hash(tmp_path / "d.tif")})
        == 3
    )


def test_json_and_yaml_ignore_white_space_and_key_order_but_not_values(tmp_path):
    a, b, c = tmp_path / "a.json", tmp_path / "b.json", tmp_path / "c.json"
    a.write_text(json.dumps({"x": 1, "y": [1, 2]}), encoding="utf-8")
    b.write_text(json.dumps({"y": [1, 2], "x": 1}, indent=4), encoding="utf-8")
    c.write_text(json.dumps({"x": 1, "y": [2, 1]}), encoding="utf-8")
    assert content_hash(a) == content_hash(b) != content_hash(c)
    y1, y2 = tmp_path / "a.yaml", tmp_path / "b.yaml"
    y1.write_text("a: 1\nb: 2\n", encoding="utf-8")
    y2.write_text("# a comment\nb: 2\na: 1\n", encoding="utf-8")
    assert content_hash(y1) == content_hash(y2)


def test_a_png_ignores_text_chunks_but_not_pixels(tmp_path):
    image = Image.fromarray(np.arange(64, dtype="uint8").reshape(8, 8))
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    image.save(a)
    meta = PngInfo()
    meta.add_text("Software", "other")
    image.save(b, pnginfo=meta)
    assert a.read_bytes() != b.read_bytes() and content_hash(a) == content_hash(b)
    Image.fromarray(np.zeros((8, 8), dtype="uint8")).save(tmp_path / "c.png")
    assert content_hash(tmp_path / "c.png") != content_hash(a)


def test_other_files_and_unreadable_files_are_hashed_by_their_bytes(tmp_path):
    text = tmp_path / "a.txt"
    text.write_text("one", encoding="utf-8")
    broken = tmp_path / "broken.parquet"
    broken.write_bytes(b"not a parquet")
    assert content_hash(text).startswith("bytes:") and content_hash(broken).startswith("bytes:")
    before = content_hash(text)
    text.write_text("two", encoding="utf-8")
    assert content_hash(text) != before


# ─── the manifest ────────────────────────────────────────────────────────

CHAIN = ["land_eligibility", "technical_potential", "lcoe_modeling"]


class Out(BaseModel):
    model_config = ConfigDict(extra="forbid")

    n: int


def _specs(
    outputs: Path, calls: list[str], counter: dict[str, int], rows: list[int]
) -> list[PhaseSpec]:
    """The first phase writes a parquet whose bytes change at every run (the metadata holds the run counter) and whose rows are `rows`."""
    specs, previous = [], None
    for name in CHAIN:

        def run(context, name=name):
            calls.append(name)
            counter[name] = counter.get(name, 0) + 1
            path = outputs / f"{name}.parquet"
            frame = (
                pd.DataFrame({"cell_id": rows}) if name == CHAIN[0] else pd.DataFrame({"x": [1, 2]})
            )
            _write_parquet(path, frame, f"{name} run {counter[name]}")
            context.register_artifact(name, path, "1.0")
            return Out(n=len(frame))

        specs.append(
            PhaseSpec(
                name=name,
                output_model=Out,
                run=run,
                requires=frozenset({previous}) if previous else frozenset(),
                produces=frozenset({name}),
            )
        )
        previous = name
    return specs


def _orchestrator(outputs: Path, run_id: str, rerun: list[str]) -> Orchestrator:
    from geofrea.core.config_loader import load_parameters

    return Orchestrator(
        outputs_dir=outputs,
        country_code="PRT",
        country_params=load_parameters(REPO / "config" / "parameters.json").countries["PRT"],
        target_phases=[CHAIN[-1]],
        rerun_phases=rerun,
        run_id=run_id,
        methodology_version="test-1.0.0",
        dirty=False,
    )


def test_rewriting_an_artifact_with_identical_content_does_not_mark_the_consumers_stale(tmp_path):
    outputs = tmp_path / "out"
    outputs.mkdir()
    calls: list[str] = []
    counter: dict[str, int] = {}
    first = _orchestrator(outputs, "run-1", [])
    first.run(_specs(outputs, calls, counter, [1, 2, 3]))
    bytes_before = (outputs / "land_eligibility.parquet").read_bytes()
    entry_before = first.manifest.artifacts["land_eligibility"]

    calls.clear()
    second = _orchestrator(outputs, "run-2", ["land_eligibility"])
    second.run(_specs(outputs, calls, counter, [1, 2, 3]))
    assert calls == ["land_eligibility"]  # only the named phase ran again
    assert (
        outputs / "land_eligibility.parquet"
    ).read_bytes() != bytes_before  # the file was rewritten, bytes differ
    entry_after = second.manifest.artifacts["land_eligibility"]
    assert entry_after.sha256 != entry_before.sha256
    assert entry_after.content_sha256 == entry_before.content_sha256
    assert (
        entry_after.run_id == entry_before.run_id
    )  # the lineage that first produced the content is kept
    assert second.manifest.phases["technical_potential"].status == "success"
    assert second.manifest.phases["lcoe_modeling"].status == "success"


def test_another_content_marks_the_consumers_stale_and_they_run_again(tmp_path):
    outputs = tmp_path / "out"
    outputs.mkdir()
    calls: list[str] = []
    counter: dict[str, int] = {}
    _orchestrator(outputs, "run-1", []).run(_specs(outputs, calls, counter, [1, 2, 3]))
    calls.clear()
    _orchestrator(outputs, "run-2", ["land_eligibility"]).run(
        _specs(outputs, calls, counter, [1, 2, 4])
    )
    assert calls == CHAIN


def test_an_entry_of_an_older_manifest_without_a_content_hash_is_compared_by_bytes(tmp_path):
    outputs = tmp_path / "out"
    outputs.mkdir()
    calls: list[str] = []
    counter: dict[str, int] = {}
    first = _orchestrator(outputs, "run-1", [])
    first.run(_specs(outputs, calls, counter, [1, 2, 3]))
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["artifacts"].values():
        entry.pop("content_sha256")  # a manifest of schema 2.5
    manifest["schema_version"] = "2.5"
    first.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    calls.clear()
    _orchestrator(outputs, "run-2", ["land_eligibility"]).run(
        _specs(outputs, calls, counter, [1, 2, 3])
    )
    assert calls == CHAIN  # no content hash to compare with: the new bytes count, once
    calls.clear()
    _orchestrator(outputs, "run-3", ["land_eligibility"]).run(
        _specs(outputs, calls, counter, [1, 2, 3])
    )
    assert calls == ["land_eligibility"]  # now the content hash is recorded
