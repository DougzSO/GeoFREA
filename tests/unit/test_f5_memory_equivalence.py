"""The memory reduction of F5 changes no value (COMMAND 126, items a, b and d of step 6 of COMMAND 124).

The old code is kept here as the oracle: `_old_read_cell_pixels` is the function that read each raster whole, and the old table writing is
`pd.concat(pieces)` followed by `write_table`. The new code must give the same arrays bit for bit and the same files byte for byte.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
import rasterio

from geofrea.core.constants import CELL_DEG, CELL_NESTING_PIXELS, CELL_ORIGIN_LAT, CELL_ORIGIN_LON
from geofrea.core.scale import SCALES, use_scale
from geofrea.core.tables import write_table
from geofrea.land_eligibility.cells import (
    cell_id,
    lattice_window,
    pad_to_window,
    pixel_row_area_km2,
)
from geofrea.technical_potential import pipeline as P
from geofrea.technical_potential import pixel_inputs as PI
from geofrea.technical_potential.pixel_inputs import (
    AREA_AGREEMENT_RTOL,
    CellPixels,
    PixelInputError,
    read_cell_pixels,
)
from geofrea.technical_potential.table_schemas import POTENTIAL_TABLE_SCHEMA_VERSION, PotentialRow
from tests.unit.test_technical_potential_pipeline import (  # noqa: F401  (fixtures)
    _run,
    registry,
    synthetic_params,
)

pytestmark = pytest.mark.unit

K = CELL_NESTING_PIXELS
PIXEL_DEG = CELL_DEG / K


# --- the old read_cell_pixels, verbatim, as the oracle ----------------------------------------------------------------------------


def _old_read(path: Path, dtype: str):
    with rasterio.open(path) as src:
        return src.read(1, masked=True).astype(dtype).filled(np.nan), src.transform


def _old_read_cell_pixels(cells, fraction_path, resource_paths) -> CellPixels:
    fraction, transform = _old_read(fraction_path, "float32")
    height, width = fraction.shape
    window = lattice_window(transform, height, width)
    k = window.k
    rows = cells["row"].to_numpy(dtype="int64") - window.row0
    cols = cells["col"].to_numpy(dtype="int64") - window.col0
    if len(cells) and (rows.min() < 0 or cols.min() < 0 or rows.max() >= window.n_rows or cols.max() >= window.n_cols):
        raise PixelInputError(f"{fraction_path.name}: a candidate cell lies outside the raster")
    area_row = pixel_row_area_km2(transform, height)
    weight = np.where(np.isfinite(fraction), fraction, 0.0).astype("float64") * area_row[:, None]
    del fraction
    padded = pad_to_window(weight, window)
    del weight

    def gather(grid):
        blocks = grid.reshape(window.n_rows, k, window.n_cols, k)
        i = np.arange(k)
        picked = blocks[rows[:, None, None], i[None, :, None], cols[:, None, None], i[None, None, :]]
        return picked.reshape(len(rows), k * k)

    w = gather(padded)
    del padded
    values = {}
    usable = w > 0
    for name, path in resource_paths.items():
        grid, other = _old_read(path, "float32")
        if grid.shape != (height, width) or other != transform:
            raise PixelInputError(f"{path.name} is not on the grid of {fraction_path.name}")
        values[name] = gather(pad_to_window(grid, window, np.nan)).astype("float64")
        del grid
        usable &= np.isfinite(values[name])
    w = np.where(usable, w, 0.0)
    counts = usable.sum(axis=1)
    if (counts == 0).any():
        raise PixelInputError(
            f"{fraction_path.name}: {int((counts == 0).sum())} candidate cells have no eligible pixel with a finite resource"
        )
    table_area = cells["eligible_area_km2"].to_numpy(dtype="float64")
    gap = np.abs(w.sum(axis=1) - table_area) / table_area
    if (gap > AREA_AGREEMENT_RTOL).any():
        worst = int(np.argmax(gap))
        raise PixelInputError(
            f"{fraction_path.name}: the pixel weights of {int((gap > AREA_AGREEMENT_RTOL).sum())} cells differ from the eligible area of the "
            f"F3 table by more than {AREA_AGREEMENT_RTOL:g} (largest {gap[worst]:.3g}, cell {int(cells['cell_id'].iloc[worst])})"
        )
    offsets = np.concatenate([[0], np.cumsum(counts)]).astype("int64")
    return CellPixels(offsets=offsets, weight_km2=w[usable], resources={n: v[usable] for n, v in values.items()})


# --- a world on a lattice, with holes, NaN, nodata and zero fractions -----------------------------------------------------------------


def _write(path: Path, grid: np.ndarray, transform, *, nodata=-9999.0) -> Path:
    h, w = grid.shape
    with rasterio.open(
        path, "w", driver="GTiff", dtype="float32", count=1, nodata=nodata, crs="EPSG:4326", transform=transform, height=h, width=w
    ) as dst:  # fmt: skip
        dst.write(np.where(np.isfinite(grid), grid, nodata).astype("float32"), 1)
    return path


def _world(tmp_path: Path, *, row0=1000, col0=2000, n_rows=9, n_cols=7, seed=5, pad=(0, 0), n_layers=4):
    """`n_rows` x `n_cols` cells; `pad` pixels of the first cell lie outside the raster (the 0.1 degree scale pads, the 0.05 one does not)."""
    rng = np.random.default_rng(seed)
    pad_top, pad_left = pad
    height, width = n_rows * K - pad_top, n_cols * K - pad_left
    transform = rasterio.Affine(
        PIXEL_DEG,
        0.0,
        CELL_ORIGIN_LON + col0 * CELL_DEG + pad_left * PIXEL_DEG,
        0.0,
        -PIXEL_DEG,
        CELL_ORIGIN_LAT - row0 * CELL_DEG - pad_top * PIXEL_DEG,
    )
    fraction = rng.uniform(0.0, 1.0, (height, width))
    fraction[rng.random((height, width)) < 0.25] = 0.0
    fraction[rng.random((height, width)) < 0.02] = np.nan  # a masked pixel
    fraction[:K, :K] = 0.0  # a cell without any eligible pixel
    layers = {}
    for n in range(n_layers):
        grid = rng.uniform(1.0, 12.0, (height, width))
        grid[rng.random((height, width)) < 0.03] = np.nan  # a resource that is missing on a pixel
        layers[f"layer_{n}"] = grid
    paths = {"fraction": _write(tmp_path / "fraction.tif", fraction, transform)}
    for name, grid in layers.items():
        paths[name] = _write(tmp_path / f"{name}.tif", grid, transform)
    return paths, transform, (height, width)


def _candidate_cells(paths, transform, shape, *, shuffle_seed=None, drop=0.0):
    """The cells the old code accepts: the F3 table is made from the same arrays, so the weights agree."""
    height, width = shape
    window = lattice_window(transform, height, width)
    k = window.k
    fraction, _ = _old_read(paths["fraction"], "float32")
    layer_names = [n for n in paths if n != "fraction"]
    weight = np.where(np.isfinite(fraction), fraction, 0.0).astype("float64") * pixel_row_area_km2(transform, height)[:, None]
    usable = pad_to_window(weight, window) > 0
    for name in layer_names:
        grid, _ = _old_read(paths[name], "float32")
        usable &= np.isfinite(pad_to_window(grid, window, np.nan).astype("float64"))
    area = np.where(usable, pad_to_window(weight, window), 0.0).reshape(window.n_rows, k, window.n_cols, k).sum(axis=(1, 3))
    r, c = np.nonzero(area > 0)
    cells = pd.DataFrame(
        {"row": r + window.row0, "col": c + window.col0, "eligible_area_km2": area[r, c]}
    )
    cells["cell_id"] = cell_id(cells["row"].to_numpy(), cells["col"].to_numpy())
    if drop:
        keep = np.random.default_rng(1).random(len(cells)) >= drop
        cells = cells[keep]
        # the weight sum of the cell no longer matches the table only if a cell is changed: dropping whole cells keeps every other one valid
    if shuffle_seed is not None:
        cells = cells.sample(frac=1.0, random_state=shuffle_seed)
    return cells.reset_index(drop=True)


def _same(a: CellPixels, b: CellPixels) -> None:
    assert a.offsets.dtype == b.offsets.dtype and np.array_equal(a.offsets, b.offsets)
    assert a.weight_km2.dtype == b.weight_km2.dtype
    assert a.weight_km2.tobytes() == b.weight_km2.tobytes()
    assert list(a.resources) == list(b.resources)
    for name in a.resources:
        assert a.resources[name].dtype == b.resources[name].dtype
        assert a.resources[name].tobytes() == b.resources[name].tobytes(), name


@pytest.mark.parametrize("band_pixels", [1, 400, 3_000, 10**9])
@pytest.mark.parametrize("shuffled", [False, True])
def test_read_cell_pixels_by_bands_is_bit_identical_to_the_whole_read(tmp_path, monkeypatch, band_pixels, shuffled):
    paths, transform, shape = _world(tmp_path)
    cells = _candidate_cells(paths, transform, shape, shuffle_seed=3 if shuffled else None)
    assert len(cells) > 30
    resources = {n: p for n, p in paths.items() if n != "fraction"}
    old = _old_read_cell_pixels(cells, paths["fraction"], resources)
    monkeypatch.setattr(PI, "BAND_PIXELS", band_pixels)
    _same(read_cell_pixels(cells, paths["fraction"], resources), old)


def test_a_grid_that_starts_inside_a_cell_is_padded_like_before(tmp_path, monkeypatch):
    """The 0.1 degree scale: a grid on the 0.05 lattice may start and end inside a 0.1 degree cell, so the first and last bands hold padding."""
    with use_scale(SCALES["0p1deg"]):
        height, width = 7 * K, 5 * K  # 7 x 5 cells of 0.05 degrees
        rng = np.random.default_rng(9)
        shifted = rasterio.Affine(
            PIXEL_DEG, 0.0, CELL_ORIGIN_LON + 401 * CELL_DEG, 0.0, -PIXEL_DEG, CELL_ORIGIN_LAT - 201 * CELL_DEG
        )
        window = lattice_window(shifted, height, width)
        assert (window.pad_top, window.pad_left) == (5, 5) and window.k == 10
        fraction = rng.uniform(0.1, 1.0, (height, width))
        fraction[rng.random((height, width)) < 0.2] = 0.0
        grids = {f"layer_{n}": rng.uniform(1.0, 9.0, (height, width)) for n in range(3)}
        paths = {"fraction": _write(tmp_path / "f2.tif", fraction, shifted)}
        paths.update({n: _write(tmp_path / f"{n}.tif", g, shifted) for n, g in grids.items()})
        cells = _candidate_cells(paths, shifted, (height, width), shuffle_seed=2)
        assert len(cells) >= 10
        resources = {n: p for n, p in paths.items() if n != "fraction"}
        old = _old_read_cell_pixels(cells, paths["fraction"], resources)
        for band_pixels in (1, 700, 10**9):
            monkeypatch.setattr(PI, "BAND_PIXELS", band_pixels)
            _same(read_cell_pixels(cells, paths["fraction"], resources), old)


def test_the_errors_are_the_same_as_before(tmp_path, monkeypatch):
    paths, transform, shape = _world(tmp_path)
    cells = _candidate_cells(paths, transform, shape)
    resources = {n: p for n, p in paths.items() if n != "fraction"}
    monkeypatch.setattr(PI, "BAND_PIXELS", 500)

    def both(c, fraction, res):
        outcomes = []
        for fn in (_old_read_cell_pixels, read_cell_pixels):
            with pytest.raises(PixelInputError) as exc:
                fn(c, fraction, res)
            outcomes.append(str(exc.value))
        assert outcomes[0] == outcomes[1]
        return outcomes[0]

    outside = cells.copy()
    outside.loc[0, "row"] = 10**5
    assert "outside the raster" in both(outside, paths["fraction"], resources)

    wrong_area = cells.copy()
    wrong_area["eligible_area_km2"] = wrong_area["eligible_area_km2"] * 1.5
    assert "differ from the eligible area" in both(wrong_area, paths["fraction"], resources)

    # a cell that has no eligible pixel: the first cell (all zero) added to the table
    empty_cell = pd.concat([cells, pd.DataFrame({"row": [1000], "col": [2000], "eligible_area_km2": [1.0], "cell_id": [cell_id(1000, 2000)]})], ignore_index=True)
    assert "no eligible pixel" in both(empty_cell, paths["fraction"], resources)

    other = _write(tmp_path / "other.tif", np.ones((5, 5)), rasterio.Affine(PIXEL_DEG, 0.0, 0.0, 0.0, -PIXEL_DEG, 0.0))
    assert "is not on the grid" in both(cells, paths["fraction"], {**resources, "other": other})


def test_no_cell_gives_empty_arrays_like_before(tmp_path):
    paths, transform, shape = _world(tmp_path)
    cells = _candidate_cells(paths, transform, shape).iloc[0:0]
    resources = {n: p for n, p in paths.items() if n != "fraction"}
    _same(read_cell_pixels(cells, paths["fraction"], resources), _old_read_cell_pixels(cells, paths["fraction"], resources))


# --- the table of potential written in blocks -------------------------------------------------------------------------------------------


MEMBERS = [f"m{i:02d}" for i in range(37)]


def _pieces(sizes, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for i, n in enumerate(sizes):
        member = MEMBERS[i % len(MEMBERS)]
        out.append(
            pd.DataFrame(
                {
                    "cell_id": rng.integers(0, 10**7, n).astype("int64"),
                    "member": pd.Categorical([member] * n, categories=MEMBERS),
                    "P_MW": rng.uniform(0, 100, n),
                    "CF": rng.uniform(0, 1, n),
                    "E_MWh": rng.uniform(0, 1e5, n),
                }
            )
        )
    return out


def _old_write(pieces, path, extra):
    table = pd.concat(pieces, ignore_index=True) if pieces else P._empty_potential_table(MEMBERS)
    write_table(
        table, path, schema_version=POTENTIAL_TABLE_SCHEMA_VERSION, row_model=PotentialRow, compression="zstd", extra_metadata=extra
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


M = 1024 * 1024


@pytest.mark.parametrize(
    "sizes",
    [
        [],
        [10],
        [M - 1],
        [M],
        [M + 1],
        [M, M],
        [M // 2, M // 2, M // 2, M // 2],
        [300_000] * 10,  # 3.0 M rows: three full row groups and a rest, pieces that straddle the boundaries
        [3 * M + 5, 7, 2 * M],  # one piece longer than three row groups
        [0, 5, 0, 7],
    ],
)
def test_the_table_in_blocks_is_the_same_file_as_the_concatenated_one(tmp_path, sizes):
    extra = {P.PROVENANCE_KEY: '{"k": 1}'}
    old_path, new_path = tmp_path / "old.parquet", tmp_path / "new.parquet"
    _old_write(_pieces(sizes), old_path, extra)
    pieces = _pieces(sizes)
    n = P._write_potential_in_blocks(pieces, new_path, MEMBERS, extra_metadata=extra)
    assert n == sum(sizes) and pieces == []  # the pieces were released as they were written
    assert _sha(old_path) == _sha(new_path)
    assert pq.ParquetFile(old_path).metadata.num_row_groups == pq.ParquetFile(new_path).metadata.num_row_groups
    assert pq.read_table(old_path).equals(pq.read_table(new_path))


# --- the whole of F5: new code against the old paths --------------------------------------------------------------------------------------


def _old_write_potential(pieces, path, members, *, extra_metadata):
    table = pd.concat(pieces, ignore_index=True) if pieces else P._empty_potential_table(members)
    write_table(
        table, path, schema_version=POTENTIAL_TABLE_SCHEMA_VERSION, row_model=PotentialRow, compression="zstd", extra_metadata=extra_metadata
    )
    n = len(table)
    pieces.clear()
    return n


def test_every_artifact_of_f5_is_byte_identical_to_the_old_code(tmp_path_factory, registry, synthetic_params, monkeypatch):  # noqa: F811
    new_summary, new_out = _run(tmp_path_factory.mktemp("new"), registry, synthetic_params)
    monkeypatch.setattr(P, "read_cell_pixels", _old_read_cell_pixels)
    monkeypatch.setattr(P, "_write_potential_in_blocks", _old_write_potential)
    old_summary, old_out = _run(tmp_path_factory.mktemp("old"), registry, synthetic_params)
    new_files = sorted(p.name for p in new_out.rglob("*") if p.is_file())
    assert new_files == sorted(p.name for p in old_out.rglob("*") if p.is_file())
    assert any(n.startswith("potential_wind__") for n in new_files)
    for name in new_files:
        assert _sha(new_out / name) == _sha(old_out / name), name
    for tech in new_summary.technologies:
        a, b = new_summary.technologies[tech], old_summary.technologies[tech]
        for scenario in a.scenarios:
            assert a.scenarios[scenario].model_dump(exclude={"path", "ensemble_path", "class_flag_path"}) == b.scenarios[scenario].model_dump(
                exclude={"path", "ensemble_path", "class_flag_path"}
            )
