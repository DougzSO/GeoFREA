"""COMMAND 88, item 3: the cache key of a layer holds the code of its builder and what it calls, not the code of the whole package."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from geofrea.core import function_fingerprint as ff
from geofrea.core.cache_code import CACHE_FUNCTION_ENTRIES, aligned_layers_code, cache_code
from geofrea.core.code_fingerprint import SRC_ROOT

pytestmark = pytest.mark.unit


def _copy_src(tmp_path: Path) -> Path:
    root = tmp_path / "geofrea"
    shutil.copytree(SRC_ROOT, root, ignore=shutil.ignore_patterns("__pycache__"))
    return root


def _edit(root: Path, relative: str, old: str, new: str) -> None:
    path = root / relative
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not in {relative}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _fingerprints(root: Path) -> dict[str, str]:
    return {name: ff.function_fingerprint(entries, root) for name, entries in CACHE_FUNCTION_ENTRIES.items()}


def test_an_edit_of_the_population_step_does_not_change_the_key_of_the_elevation(tmp_path):
    root = _copy_src(tmp_path)
    before = _fingerprints(root)
    _edit(root, "grid_alignment/layers.py", "ctx.path(\"population\"), ctx.grid)", "ctx.path(\"population\"), ctx.grid, nodata_out=-1.0)")
    after = _fingerprints(root)
    assert after["aligned_layer.population"] != before["aligned_layer.population"]
    assert {k: v for k, v in after.items() if k != "aligned_layer.population"} == {
        k: v for k, v in before.items() if k != "aligned_layer.population"
    }


def test_an_edit_of_the_shared_warp_changes_the_layers_that_call_it_and_not_the_others(tmp_path):
    root = _copy_src(tmp_path)
    before = _fingerprints(root)
    _edit(root, "grid_alignment/raster_alignment.py", "pad_px = int(np.ceil(abs(grid.transform.a) / src_res)) + 4", "pad_px = int(np.ceil(abs(grid.transform.a) / src_res)) + 5")
    after = _fingerprints(root)
    changed = {k for k in before if before[k] != after[k]}
    assert changed == {"aligned_layer.solar", "aligned_layer.wind", "aligned_layer.population", "aligned_layer.settlements"}


def test_an_edit_of_the_elevation_pass_leaves_the_reprojected_layers_current(tmp_path):
    root = _copy_src(tmp_path)
    before = _fingerprints(root)
    _edit(root, "grid_alignment/raster_alignment.py", "_SLOPE_STRIP_GRID_ROWS", "_SLOPE_STRIP_GRID_ROWS_")  # renames the constant everywhere it is used
    after = _fingerprints(root)
    assert {k for k in before if before[k] != after[k]} == {"aligned_layer.glo30", "aligned_layer.fabdem_slope"}  # the slope from FABDEM runs the same strips (D-F2a-028)


def test_a_comment_a_docstring_or_a_reformat_does_not_change_a_fingerprint(tmp_path):
    root = _copy_src(tmp_path)
    before = _fingerprints(root)
    _edit(root, "grid_alignment/layers.py", "def build_solar(ctx: LayerContext) -> Path:", "def build_solar(ctx: LayerContext) -> Path:\n    '''A new docstring.'''\n    # a new comment")
    assert _fingerprints(root) == before


def test_the_grid_enters_every_layer(tmp_path):
    root = _copy_src(tmp_path)
    before = _fingerprints(root)
    _edit(root, "grid_alignment/reference_grid.py", "nesting_pixels", "nesting_pixels_")
    after = _fingerprints(root)
    assert all(after[k] != before[k] for k in before)


def test_the_entries_reach_the_functions_they_call():
    reached = ff.reachable_definitions(("grid_alignment.layers:build_population",))
    assert "grid_alignment.raster_alignment:reproject_to_grid" in reached
    assert "core.clipped_cache:clipped_source" in reached
    assert "grid_alignment.raster_alignment:glo30_aligned_outputs" not in reached


def test_an_unknown_entry_is_an_error():
    with pytest.raises(ff.UnknownEntryError):
        ff.function_fingerprint(("grid_alignment.layers:build_nothing",))


def test_every_layer_cache_has_a_fingerprint_and_the_whole_has_one():
    assert all(len(cache_code(name)) == 64 for name in CACHE_FUNCTION_ENTRIES)
    assert len(aligned_layers_code()) == 64
