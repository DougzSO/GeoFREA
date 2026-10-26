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
def test_overview_none_writes_the_table_only_and_all_adds_the_diagnostic_maps(data_dir):
    _write_aligned(data_dir)
    _write_climate(data_dir)
    _write_cells(data_dir)
    _write_cost(data_dir)
    none = build_overview(ISO, "none")
    assert none.figures == [] and none.table.exists()
    everything = build_overview(ISO, "all")
    # the three aligned sheets and the land cover, the hazard context, the F3 sheets (2) and chart, the exclusion maps (12), the cost drivers (2)
    assert len(everything.figures) == 3 + 1 + 1 + 3 + 12 + 2
    summary = build_overview(ISO, "summary")
    assert len(summary.figures) == 3 + 1 + 1 + 3
    with pytest.raises(ValueError, match="figures must be"):
        build_overview(ISO, "some")


@pytest.mark.unit
def test_climate_maps_are_the_ensemble_sheets_and_the_members_only_with_all(data_dir):
    _write_climate(data_dir)
    # two members (m0 is identity and is not drawn): the ensemble sheet of each SSP, the three grids and the two supplementary member sheets
    assert build_maps(ISO, "all").n_figures == 2 + 3 + 2
    assert build_maps(ISO, "summary").n_figures == 2 + 3
    assert build_maps(ISO, "none").n_figures == 0
    with pytest.raises(ValueError, match="figures must be"):
        build_maps(ISO, "some")
