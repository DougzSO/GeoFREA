"""COMMAND 98: durable atomic writes, the COG writer, and the write mechanics outside the code fingerprints."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import rasterio
import rasterio.shutil
from rasterio.transform import from_origin

from geofrea.core import atomic_io, code_fingerprint, cog_write
from geofrea.core.cache_code import CACHE_CODE_ROOTS, CACHE_FUNCTION_ENTRIES
from geofrea.core.code_fingerprint import (
    FINGERPRINT_EXEMPT_MODULES,
    PHASE_CODE_ROOTS,
    SRC_ROOT,
    closure_fingerprint,
    closure_modules,
)
from geofrea.core.content_hash import content_hash
from geofrea.core.function_fingerprint import function_fingerprint, reachable_definitions
from geofrea.core.raster_io import safe_raster_write


def _profile(**extra) -> dict:
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "width": 300,
        "height": 280,
        "count": 1,
        "crs": "EPSG:4326",
        "transform": from_origin(-9.0, 39.0, 0.01, 0.01),
        "nodata": -9999.0,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    profile.update(extra)
    return profile


def _data(profile: dict) -> np.ndarray:
    rng = np.random.default_rng(7)
    shape = (profile["count"], profile["height"], profile["width"])
    return rng.integers(0, 50, shape).astype(profile["dtype"])


def _write(path: Path, profile: dict) -> None:
    with safe_raster_write(path, **profile) as dst:
        dst.write(_data(profile))


def _legacy_cog(source: Path, final: Path, profile: dict) -> None:
    """What `_write_cog` did before COMMAND 98: the options of the profile, converted straight onto the destination."""
    options = {
        "COMPRESS": str(profile.get("compress", "lzw")).upper(),
        "BLOCKSIZE": str(profile.get("blockxsize", 256)),
        "OVERVIEW_RESAMPLING": "NEAREST",
    }
    if profile.get("predictor") is not None:
        options["PREDICTOR"] = str(profile["predictor"])
    rasterio.shutil.copy(str(source), str(final), driver="COG", **options)


PROFILES = [
    {},  # float32, lzw (the writer's default)
    {"compress": "deflate", "predictor": 2, "dtype": "uint16", "count": 4, "nodata": 65535},
    {"compress": "deflate", "predictor": 3},
]


@pytest.mark.parametrize("extra", PROFILES)
def test_the_cog_bytes_are_those_of_the_conversion_before_the_change(
    tmp_path: Path, extra: dict
) -> None:
    profile = _profile(**extra)
    source = tmp_path / "source.tif"
    with rasterio.open(
        source, "w", **{k: v for k, v in profile.items() if k != "tiled"}, tiled=True
    ) as dst:
        dst.write(_data(profile))
    legacy = tmp_path / "legacy.tif"
    _legacy_cog(source, legacy, profile)

    new = tmp_path / "new.tif"
    shutil.copyfile(source, tmp_path / "new.writing.tif")
    cog_write.write_cog(tmp_path / "new.writing.tif", new, profile)

    assert new.read_bytes() == legacy.read_bytes()
    assert content_hash(new) == content_hash(legacy)
    assert (
        not list(tmp_path.glob("*.converting.tif")) and not (tmp_path / "new.writing.tif").exists()
    )


def test_safe_raster_write_gives_the_same_content_as_before(tmp_path: Path) -> None:
    profile = _profile(compress="deflate", predictor=2, dtype="uint16", count=2, nodata=65535)
    out = tmp_path / "layer.tif"
    _write(out, profile)
    with rasterio.open(out) as src:
        assert (src.read() == _data(profile)).all()
        assert src.profile["compress"].lower() == "deflate"


def test_a_failed_conversion_leaves_the_previous_file_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = _profile()
    final = tmp_path / "layer.tif"
    _write(final, profile)
    before = final.read_bytes()

    real_copy = rasterio.shutil.copy

    def cut_in_the_middle(src, dst, **kwargs):
        real_copy(src, dst, **kwargs)
        Path(dst).write_bytes(
            Path(dst).read_bytes()[:1000]
        )  # what a power loss leaves: a cut file at the temporary name
        raise OSError("the computer went down")

    monkeypatch.setattr(rasterio.shutil, "copy", cut_in_the_middle)
    with pytest.raises(OSError, match="went down"), safe_raster_write(final, **profile) as dst:
        dst.write(_data(profile) + 1)

    assert final.read_bytes() == before  # the destination was never deleted nor written in place
    assert not list(tmp_path.glob("*.converting.tif"))


def test_the_destination_is_not_deleted_before_the_new_file_is_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = _profile()
    final = tmp_path / "layer.tif"
    _write(final, profile)
    seen = {}
    real_copy = rasterio.shutil.copy

    def spy(src, dst, **kwargs):
        seen["final_exists_during_conversion"] = final.exists()
        seen["converting_name"] = Path(dst).name
        return real_copy(src, dst, **kwargs)

    monkeypatch.setattr(rasterio.shutil, "copy", spy)
    _write(final, profile)
    assert seen == {
        "final_exists_during_conversion": True,
        "converting_name": "layer.converting.tif",
    }


def test_replace_durable_flushes_the_file_before_the_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    order = []
    real_fsync, real_replace = os.fsync, Path.replace
    monkeypatch.setattr(os, "fsync", lambda fd: (order.append("fsync"), real_fsync(fd))[1])
    monkeypatch.setattr(
        Path,
        "replace",
        lambda self, target: (order.append("replace"), real_replace(self, target))[1],
    )
    atomic_io.write_text_atomic(tmp_path / "state.json", '{"a": 1}')
    assert order.index("fsync") < order.index("replace")
    assert (tmp_path / "state.json").read_text(encoding="utf-8") == '{"a": 1}'
    assert not list(tmp_path.glob("*.tmp"))


def test_a_failed_atomic_write_keeps_the_old_file_and_no_residue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "state.json"
    target.write_text("old", encoding="utf-8")

    def boom(self, target):
        raise RuntimeError("killed")

    monkeypatch.setattr(Path, "replace", boom)
    with pytest.raises(RuntimeError):
        atomic_io.write_text_atomic(target, "new")
    assert target.read_text(encoding="utf-8") == "old"
    assert not list(tmp_path.glob("*.tmp"))


def test_a_lock_is_retried_and_another_error_is_not(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(atomic_io, "WRITE_RETRY_WAITS_S", (0.0, 0.0))
    calls = []

    def locked_twice():
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError("Permission denied")
        return "done"

    assert atomic_io.retry_while_locked(locked_twice, "x") == "done" and len(calls) == 3
    calls.clear()

    def missing():
        calls.append(1)
        raise FileNotFoundError("no such file")

    with pytest.raises(FileNotFoundError):
        atomic_io.retry_while_locked(missing, "x")
    assert len(calls) == 1


def test_write_table_appears_whole_or_not_at_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pyarrow.parquet as pq
    from pydantic import BaseModel

    from geofrea.core import tables

    class Row(BaseModel):
        a: int

    path = tmp_path / "t.parquet"
    tables.write_table(pd.DataFrame({"a": [1, 2]}), path, schema_version="1", row_model=Row)
    before = path.read_bytes()

    def cut(table, where, **kwargs):
        Path(where).write_bytes(b"PAR1 cut")
        raise OSError("power loss")

    monkeypatch.setattr(pq, "write_table", cut)
    with pytest.raises(OSError, match="power loss"):
        tables.write_table(pd.DataFrame({"a": [3]}), path, schema_version="1", row_model=Row)
    assert path.read_bytes() == before
    assert not list(tmp_path.glob("*.partial"))


# --- the write mechanics are outside the code fingerprints ---------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tree_copy(tmp_path_factory: pytest.TempPathFactory) -> Path:
    copy = tmp_path_factory.mktemp("srccopy") / "geofrea"
    shutil.copytree(SRC_ROOT, copy, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return copy


def _fingerprints(root: Path) -> dict[str, str]:
    result = {
        f"phase:{name}": closure_fingerprint(roots, root)
        for name, roots in PHASE_CODE_ROOTS.items()
    }
    result |= {
        f"cache:{name}": closure_fingerprint(roots, root)
        for name, roots in CACHE_CODE_ROOTS.items()
    }
    result |= {
        f"layer:{name}": function_fingerprint(entries, root)
        for name, entries in CACHE_FUNCTION_ENTRIES.items()
    }
    return result


def test_the_exempt_modules_are_in_no_closure_and_no_reachable_definition() -> None:
    for name, roots in PHASE_CODE_ROOTS.items():
        assert not set(closure_modules(roots)) & FINGERPRINT_EXEMPT_MODULES, name
    for name, entries in CACHE_FUNCTION_ENTRIES.items():
        reachable = reachable_definitions(entries)
        assert not [d for d in reachable if d.split(":")[0] in FINGERPRINT_EXEMPT_MODULES], name
    assert any(
        d.startswith("core.raster_io:")
        for d in reachable_definitions(CACHE_FUNCTION_ENTRIES["aligned_layer.glo30"])
    )


def test_changing_a_write_mechanic_changes_no_fingerprint(tree_copy: Path) -> None:
    before = _fingerprints(tree_copy)
    for module in ("atomic_io", "cog_write"):
        path = tree_copy / "core" / f"{module}.py"
        path.write_text(
            path.read_text(encoding="utf-8") + "\n\ndef _a_new_mechanic(x):\n    return x + 1\n",
            encoding="utf-8",
        )
    assert _fingerprints(tree_copy) == before


def test_control_changing_a_result_module_does_change_the_fingerprints(tree_copy: Path) -> None:
    before = _fingerprints(tree_copy)
    path = tree_copy / "core" / "raster_io.py"
    original = path.read_text(encoding="utf-8")
    try:
        path.write_text(
            original + "\n\ndef _changes_the_closure(x):\n    return x * 2\n", encoding="utf-8"
        )
        after = _fingerprints(tree_copy)
    finally:
        path.write_text(original, encoding="utf-8")
    assert (
        after["cache:clip"] != before["cache:clip"]
        or after["phase:grid_alignment"] != before["phase:grid_alignment"]
    )


def test_a_module_added_to_the_exempt_list_that_nothing_imports_changes_nothing(
    tree_copy: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _fingerprints(tree_copy)
    monkeypatch.setattr(
        code_fingerprint,
        "FINGERPRINT_EXEMPT_MODULES",
        FINGERPRINT_EXEMPT_MODULES | {"core.some_future_module"},
    )
    assert _fingerprints(tree_copy) == before


def test_a_scratch_file_cut_by_a_power_loss_does_not_stop_the_next_write(tmp_path: Path) -> None:
    """IND, 2026-11-05: `IND_elevation_aligned.writing.tif` was left with an unreadable header and every later write of that layer failed."""
    profile = _profile(compress="deflate", predictor=2, dtype="uint16", count=2, nodata=65535)
    out = tmp_path / "layer.tif"
    cut = tmp_path / "layer.writing.tif"
    cut.write_bytes(b"II*\x00\x08\x00\x00\x00" + b"\x00" * 64)  # a TIFF header whose directory is not there
    (tmp_path / "layer.converting.tif").write_bytes(b"II*\x00\x08\x00\x00\x00" + b"\x00" * 64)
    _write(out, profile)
    with rasterio.open(out) as src:
        assert (src.read() == _data(profile)).all()
    assert not cut.exists() and not list(tmp_path.glob("*.converting.tif"))
