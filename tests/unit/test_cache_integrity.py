"""COMMAND 98: the integrity check finds files that are cut or changed, invalidates their cache key and never touches the file."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin

from geofrea.core.cache_integrity import (
    UnreadableError,
    check_country,
    invalidate_cache_key,
    read_fully,
    sidecar_for,
    summarize,
)
from geofrea.core.cache_key import KEY_SUFFIX, file_sha256
from geofrea.core.content_hash import content_hash

ISO = "XXX"


def _write_tif(path: Path) -> None:
    data = np.arange(512 * 512, dtype="float32").reshape(512, 512)
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "width": 512,
        "height": 512,
        "count": 1,
        "crs": "EPSG:4326",
        "transform": from_origin(0, 1, 0.001, 0.001),
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "compress": "deflate",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data + np.random.default_rng(1).normal(size=data.shape).astype("float32"), 1)


def _entry(data_root: Path, path: Path, phase: str) -> dict:
    return {
        "path": {"root": "data", "rel": path.relative_to(data_root).as_posix()},
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
        "content_sha256": content_hash(path),
        "phase": phase,
    }


@pytest.fixture
def world(tmp_path: Path) -> dict:
    root = tmp_path / "data"
    art = root / "outputs" / ISO / "artifacts"
    tif, table, doc = art / "layer_aligned.tif", art / "table.parquet", art / "doc.json"
    _write_tif(tif)
    pd.DataFrame({"a": np.arange(50_000), "b": np.arange(50_000) * 0.5}).to_parquet(table)
    doc.write_text(json.dumps({"k": 1}), encoding="utf-8")
    for output in (tif, table):
        (output.with_name(output.name + KEY_SUFFIX)).write_text("key", encoding="utf-8")
    manifest = {
        "artifacts": {
            "tif": _entry(root, tif, "grid_alignment"),
            "table": _entry(root, table, "land_eligibility"),
            "doc": _entry(root, doc, "data_acquisition"),
        }
    }
    (root / "outputs" / ISO / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return {"root": root, "tif": tif, "table": table, "doc": doc}


def _status(findings: list, path: Path, root: Path) -> str:
    rel = path.relative_to(root).as_posix()
    return next(f.status for f in findings if f.path == rel)


def test_a_whole_cache_has_no_problem(world: dict) -> None:
    findings = check_country(ISO, world["root"])
    assert summarize(findings)["problems"] == 0
    assert _status(findings, world["tif"], world["root"]) == "ok"


def test_a_cut_raster_is_found_and_its_key_removed_but_not_the_file(world: dict) -> None:
    tif: Path = world["tif"]
    tif.write_bytes(tif.read_bytes()[: tif.stat().st_size // 2])
    findings = check_country(ISO, world["root"])
    assert _status(findings, tif, world["root"]) in {"unreadable", "size_mismatch"}
    assert tif.exists()
    assert not (tif.with_name(tif.name + KEY_SUFFIX)).exists()
    assert summarize(findings)["phases_to_rerun"] == ["grid_alignment"]


def test_a_cut_table_is_unreadable(world: dict) -> None:
    table: Path = world["table"]
    table.write_bytes(table.read_bytes()[:-200])
    findings = check_country(ISO, world["root"])
    assert _status(findings, table, world["root"]) in {"unreadable", "size_mismatch"}
    assert sidecar_for(table) is None


def test_a_changed_but_readable_file_fails_the_hash(world: dict) -> None:
    doc: Path = world["doc"]
    doc.write_text(json.dumps({"k": 2}), encoding="utf-8")
    findings = check_country(ISO, world["root"])
    assert _status(findings, doc, world["root"]) in {
        "size_mismatch",
        "hash_mismatch",
        "content_mismatch",
    }


def test_dry_run_reports_and_keeps_the_key(world: dict) -> None:
    tif: Path = world["tif"]
    tif.write_bytes(b"")
    findings = check_country(ISO, world["root"], invalidate=False)
    assert _status(findings, tif, world["root"]) == "empty"
    assert (tif.with_name(tif.name + KEY_SUFFIX)).exists()
    assert not any(f.invalidated for f in findings)


def test_a_missing_artifact_is_a_problem(world: dict) -> None:
    world["doc"].unlink()
    assert _status(check_country(ISO, world["root"]), world["doc"], world["root"]) == "missing"


def test_residue_and_orphan_sidecar_are_information_not_problems(world: dict) -> None:
    art = world["tif"].parent
    (art / "elevation_aligned.writing.tif").write_bytes(b"")
    (art / "gone.tif.cachekey").write_text("key", encoding="utf-8")
    findings = check_country(ISO, world["root"])
    assert {
        f.status for f in findings if "elevation_aligned.writing" in f.path or "gone.tif" in f.path
    } == {"residue", "orphan_sidecar"}
    assert summarize(findings)["problems"] == 0
    assert (art / "elevation_aligned.writing.tif").exists()  # nothing is deleted


def test_a_truncated_manifest_is_a_bad_state_file(world: dict) -> None:
    manifest = world["root"] / "outputs" / ISO / "manifest.json"
    manifest.write_text(manifest.read_text(encoding="utf-8")[:40], encoding="utf-8")
    findings = check_country(ISO, world["root"])
    assert next(f.status for f in findings if f.scope == "state") == "bad_state_file"


def test_the_clip_cache_key_sidecar_is_matched_by_stem(tmp_path: Path) -> None:
    clip = tmp_path / "rivers_clipped.gpkg"
    clip.write_bytes(b"x")
    (tmp_path / "rivers_clipped.key").write_text("k", encoding="utf-8")
    assert sidecar_for(clip) == tmp_path / "rivers_clipped.key"
    assert invalidate_cache_key(clip) is True
    assert invalidate_cache_key(clip) is False
    assert clip.exists()


def test_read_fully_rejects_an_empty_file(tmp_path: Path) -> None:
    empty = tmp_path / "x.tif"
    empty.write_bytes(b"")
    with pytest.raises(UnreadableError):
        read_fully(empty)


def test_a_cached_ledger_row_is_normal_and_a_failed_one_is_reported(world: dict) -> None:
    ledger = world["root"] / "interim" / ISO / "grid_alignment" / "layers.json"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(
        json.dumps(
            [{"layer": "elevation", "status": "ok"}, {"layer": "slope", "status": "cached"}]
        ),
        encoding="utf-8",
    )
    assert "ledger_not_ok" not in {f.status for f in check_country(ISO, world["root"])}
    ledger.write_text(json.dumps([{"layer": "elevation", "status": "failed"}]), encoding="utf-8")
    assert "ledger_not_ok" in {f.status for f in check_country(ISO, world["root"])}
