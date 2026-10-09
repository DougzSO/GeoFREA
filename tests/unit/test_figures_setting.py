# ruff: noqa: F401, F811  (the overview test module owns the fixtures and helpers; they are imported by name for pytest)
"""`settings.yaml` `figures` (A-08) in climate_maps, overview and the per-layer maps (H-5): all, summary and none."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin

from geofrea.climate_forcing.pipeline import build_maps
from geofrea.overview.figures import build_overview
from geofrea.overview.layer_maps import EXCLUSION_LABELS, build_layer_maps
from tests.unit.test_overview_figures import (
    ISO,
    _cell_ids,
    _write_aligned,
    _write_climate,
    data_dir,
)


def _write_cells(base, technologies=("solar", "wind")):
    art = base / "outputs" / ISO / "land_eligibility" / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    ids = _cell_ids()
    for tech in technologies:
        pd.DataFrame(
            {
                "cell_id": ids,
                "row": ids // 7200,
                "col": ids % 7200,
                "cell_area_km2": 30.0,
                "dominant_exclusion": ["E5"] * 10 + [None] * 5 + ["E3"] * 5,
                "eligible_area_km2": np.linspace(0, 30, len(ids)),
                **{f"excluded_area_km2_E{i}": 1.0 * i for i in range(1, 7)},
            }
        ).to_parquet(art / f"cells_{tech}__central.parquet", index=False)
    pd.DataFrame({"cell_0p1deg_id": [0]}).to_parquet(
        art / "cells_0p1deg_solar.parquet", index=False
    )  # not a cell table of the 0.05 degree lattice: ignored


def _write_cost(base):
    art = base / "outputs" / ISO / "siting_layers" / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    for name in ("dist_grid_km", "dist_road_km"):
        with rasterio.open(
            art / f"{name}.tif",
            "w",
            driver="GTiff",
            height=20,
            width=30,
            count=1,
            dtype="float32",
            crs="EPSG:4326",
            transform=from_origin(10.0, 5.0, 0.01, 0.01),
            nodata=-9999.0,
        ) as dst:
            dst.write(np.linspace(0, 50, 600, dtype="float32").reshape(20, 30), 1)


def _names(paths):
    return sorted(p.name for p in paths)


@pytest.mark.unit
def test_layer_maps_all_draws_one_file_per_layer(data_dir):
    _write_cells(data_dir)
    _write_cost(data_dir)
    paths = build_layer_maps(ISO, "all")
    expected = {"dist_grid_km__na__na__na.png", "dist_road_km__na__na__na.png"}
    for tech in ("solar", "wind"):
        expected.add(f"eligible_share_{tech}__na__na__na.png")
        expected |= {
            f"excluded_share_{code}_{label}_{tech}__na__na__na.png"
            for code, label in EXCLUSION_LABELS.items()
        }
    assert set(_names(paths)) == expected and len(paths) == len(expected) == 16
    assert all(p.stat().st_size > 2000 for p in paths)


@pytest.mark.unit
def test_layer_maps_summary_draws_only_the_eligible_share_and_none_draws_nothing(data_dir):
    _write_cells(data_dir)
    _write_cost(data_dir)
    assert _names(build_layer_maps(ISO, "summary")) == [
        "eligible_share_solar__na__na__na.png",
        "eligible_share_wind__na__na__na.png",
    ]
    assert build_layer_maps(ISO, "none") == []


@pytest.mark.unit
def test_layer_maps_skip_absent_inputs_and_reject_incomplete_cell_tables(data_dir):
    assert build_layer_maps(ISO, "all") == []  # nothing on disk: nothing drawn, nothing invented
    _write_cells(data_dir, technologies=("solar",))
    table = (
        data_dir
        / "outputs"
        / ISO
        / "land_eligibility"
        / "artifacts"
        / "cells_solar__central.parquet"
    )
    frame = pd.read_parquet(table).drop(columns="excluded_area_km2_E4")
    frame.to_parquet(table, index=False)
    with pytest.raises(ValueError, match="excluded_area_km2_E4"):
        build_layer_maps(ISO, "all")
    with pytest.raises(ValueError, match="figures must be"):
        build_layer_maps(ISO, "some")


@pytest.mark.unit
def test_overview_none_writes_the_table_only_and_all_adds_the_layer_maps(data_dir):
    _write_aligned(data_dir)
    _write_climate(data_dir)
    _write_cells(data_dir)
    _write_cost(data_dir)
    none = build_overview(ISO, "none")
    assert none.figures == [] and none.table.exists()
    everything = build_overview(ISO, "all")
    assert (
        len(everything.figures) == 3 + 16
    )  # aligned layers, hazard context, eligibility, and the layer maps
    summary = build_overview(ISO, "summary")
    assert len(summary.figures) == 3 + 2
    with pytest.raises(ValueError, match="figures must be"):
        build_overview(ISO, "some")


@pytest.mark.unit
def test_climate_maps_are_member_level_and_drawn_only_with_all(data_dir):
    _write_climate(data_dir)
    assert build_maps(ISO, "all").n_figures == 2  # m0 is identity and is not drawn
    for mode in ("summary", "none"):
        assert build_maps(ISO, mode).n_figures == 0
    with pytest.raises(ValueError, match="figures must be"):
        build_maps(ISO, "some")
