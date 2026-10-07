"""Overview figures and tables (visual QC): built from small synthetic outputs, nothing recomputed."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin

from geofrea.overview.figures import ALIGNED_PANELS, build_overview

ISO = "ZZZ"


def _cell_ids(n_rows=4, n_cols=5):
    row0, col0 = 1000, 2000
    return np.array([(row0 + r) * 7200 + (col0 + c) for r in range(n_rows) for c in range(n_cols)], dtype=np.int64)


def _write_aligned(base, skip=None):
    art = base / "outputs" / ISO / "grid_alignment" / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    for stem, *_ in ALIGNED_PANELS:
        if stem == skip:
            continue
        data = rng.uniform(1, 10, (20, 30)).astype("float32")
        data[0, 0] = -9999.0
        with rasterio.open(
            art / f"{ISO}_{stem}_aligned.tif", "w", driver="GTiff", height=20, width=30, count=1, dtype="float32",
            crs="EPSG:4326", transform=from_origin(10.0, 5.0, 0.01, 0.01), nodata=-9999.0,
        ) as dst:
            dst.write(data, 1)


def _write_climate(base):
    art = base / "outputs" / ISO / "climate_forcing" / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    ids = _cell_ids()
    rng = np.random.default_rng(1)
    members = ["m0", "m_a_ssp126_2041_2070", "m_a_ssp370_2041_2070"]
    forcing = pd.concat(
        [
            pd.DataFrame(
                {"cell_id": ids, "member": m, "delta_rsds": 1.0 + 0.01 * rng.random(len(ids)),
                 "dT": 2.0 * rng.random(len(ids)), "delta_wind": 1.0 + 0.02 * rng.random(len(ids))}
            )
            for m in members
        ]
    )
    forcing.to_parquet(art / "forcing.parquet", index=False)
    pd.DataFrame({"cell_id": ids[:2], "member": "m_a_ssp370_2041_2070", "delta_wind": 3.0, "reason": "test"}).to_parquet(
        art / "forcing_masked.parquet", index=False
    )
    hazard = pd.concat(
        [
            pd.DataFrame(
                {"cell_id": ids, "member": m, "tx35_days": 10 + 5 * rng.random(len(ids)), "tx35_days_ref": 5.0,
                 "tx40_days": 1.0, "tx40_days_ref": 0.5, "rx5day_mm": 90 + rng.random(len(ids)), "rx5day_mm_ref": 85.0,
                 "wet_p95_exceed_freq": 0.05, "wet_days_per_year_ref": 100.0, "gust_mean_annual_max_ms": 25.0}
            )
            for m in members[1:]
        ]
    )
    hazard.to_parquet(art / "hazard_context.parquet", index=False)


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOFREA_DATA_DIR", str(tmp_path))
    return tmp_path


def test_overview_writes_two_figures_and_a_table(data_dir):
    _write_aligned(data_dir)
    _write_climate(data_dir)
    result = build_overview(ISO)
    assert [p.name for p in result.figures] == [f"{ISO}_aligned_layers.png", f"{ISO}_hazard_context.png"]
    assert all(p.exists() and p.stat().st_size > 5000 for p in result.figures)
    text = result.table.read_text(encoding="utf-8")
    assert "Masked cell-members in total: 2" in text
    assert "m_a_ssp370_2041_2070" in text and "m0" not in text.split("## Climate members")[1].split("Masked")[0]


def test_a_missing_layer_is_shown_as_missing_not_hidden(data_dir):
    _write_aligned(data_dir, skip="slope")
    _write_climate(data_dir)
    result = build_overview(ISO)
    text = result.table.read_text(encoding="utf-8")
    assert "| Slope (degrees) | missing |" in text


def test_eligibility_figure_is_added_when_f3_cell_tables_exist(data_dir):
    _write_aligned(data_dir)
    _write_climate(data_dir)
    art = data_dir / "outputs" / ISO / "land_eligibility" / "artifacts"
    art.mkdir(parents=True)
    ids = _cell_ids()
    for tech in ("solar", "wind"):
        rows, cols = ids // 7200, ids % 7200
        pd.DataFrame(
            {"cell_id": ids, "row": rows, "col": cols, "cell_area_km2": 30.0,
             "eligible_area_km2": np.linspace(0, 30, len(ids)), "dominant_exclusion": ["E5"] * 10 + [None] * 5 + ["E3"] * 5}
        ).to_parquet(art / f"cells_{tech}.parquet", index=False)
    pd.DataFrame({"cell_0p1deg_id": [0]}).to_parquet(art / "cells_0p1deg_solar.parquet", index=False)  # must be ignored
    result = build_overview(ISO)
    assert f"{ISO}_eligibility.png" in [p.name for p in result.figures]
