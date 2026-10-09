"""The LCOE and robustness maps: rasters on the lattice of the active scale, nodata, the `figures` setting (T-R4, T-R11; D-F6-015, D-F7-024, A-08)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import rasterio
import yaml
from test_robustness_pipeline import _run

from geofrea.core.constants import CELL_ORIGIN_LAT, CELL_ORIGIN_LON, NODATA_FLOAT
from geofrea.core.scale import use_scale
from geofrea.land_eligibility.cells import cell_id, row_col_from_id
from geofrea.land_eligibility.map_raster import MapError
from geofrea.lcoe_modeling.maps import build_lcoe_maps, slug
from geofrea.robustness_analysis.maps import CLASS_CODES, MAPS, build_robustness_maps

CORE = "2041-2070"


def _stage_lcoe(tmp_path, scale_step=1):
    """Cells on a 2 x 3 block with the reference member and two core members of two SSPs; one infinite nominal LCOE at m0."""
    rows, cols = np.meshgrid(
        [1000, 1000 + scale_step], [2000, 2000 + scale_step, 2000 + 2 * scale_step], indexing="ij"
    )
    ids = cell_id(rows.ravel(), cols.ravel())
    n = ids.size
    base = 40.0 + np.arange(n)
    pieces = []
    for member, offset in (("m0", 0.0), ("m_a", 10.0), ("m_b", 30.0), ("m_c", 50.0)):
        nominal = base + offset
        if member == "m0":
            nominal = nominal.copy()
            nominal[2] = np.inf
        pieces.append(
            pd.DataFrame(
                {
                    "cell_id": ids,
                    "member": member,
                    "lcoe_nominal": nominal,
                    "lcoe_p10": nominal - 1.0,
                    "lcoe_p50": nominal + 0.5,
                    "lcoe_p90": nominal + 2.0,
                }
            )
        )
    root = tmp_path / "f6"
    root.mkdir()
    pd.concat(pieces, ignore_index=True).to_parquet(root / "lcoe_summary_wind.parquet")
    curve = pd.DataFrame(
        {
            "member": "m0",
            "rank": np.arange(1, n + 1),
            "cell_id": ids,
            "lcoe_nominal": base,
            "cum_P_GW": np.arange(1, n + 1) * 0.1,
            "cum_E_TWh": np.arange(1, n + 1) * 0.2,
        }
    )
    curve.to_parquet(root / "supply_curve_wind.parquet")
    cells = tmp_path / "f3"
    cells.mkdir()
    pd.DataFrame({"cell_id": ids}).to_parquet(cells / "cells_wind__central.parquet")
    members = [
        {"member": "m0", "window": "1995-2014"},
        {"member": "m_a", "window": CORE, "ssp": "SSP1-2.6", "gcm": "g1"},
        {"member": "m_b", "window": CORE, "ssp": "SSP1-2.6", "gcm": "g2"},
        {"member": "m_c", "window": CORE, "ssp": "SSP3-7.0", "gcm": "g1"},
        {"member": "m_d", "window": "2071-2100", "ssp": "SSP3-7.0", "gcm": "g1"},
    ]
    climate = tmp_path / "f4"
    climate.mkdir()
    (climate / "members.yaml").write_text(yaml.safe_dump({"members": members}), encoding="utf-8")
    return (
        ids,
        base,
        {
            "lcoe_dir": root,
            "cells_dir": cells,
            "members_file": climate / "members.yaml",
            "figures_dir": tmp_path / "figs",
        },
    )


def _read(path):
    with rasterio.open(path) as src:
        return src.read(1), src.transform, src.nodata


@pytest.mark.unit
def test_the_lcoe_rasters_hold_the_reference_member_values_on_the_lattice_and_nodata_where_not_finite(
    tmp_path,
):
    _, base, dirs = _stage_lcoe(tmp_path)
    result = build_lcoe_maps("ZZZ", ["wind"], "none", CORE, **dirs)
    data, transform, nodata = _read(result.rasters["lcoe_nominal_wind"])
    assert nodata == NODATA_FLOAT and data.shape == (2, 3)
    assert transform.a == pytest.approx(0.05) and transform.c == pytest.approx(
        CELL_ORIGIN_LON + 2000 * 0.05
    )
    assert transform.f == pytest.approx(CELL_ORIGIN_LAT - 1000 * 0.05)
    expected = base.reshape(2, 3).copy()
    expected[0, 2] = NODATA_FLOAT  # the infinite nominal LCOE of m0
    np.testing.assert_allclose(data, expected, rtol=1e-6)
    p10, _, _ = _read(result.rasters["lcoe_p10_wind"])
    assert p10[0, 0] == pytest.approx(base[0] - 1.0, rel=1e-6)
    assert result.figures == []


@pytest.mark.unit
def test_the_nominal_lcoe_by_ssp_is_the_median_over_the_core_members_of_that_ssp(tmp_path):
    _, base, dirs = _stage_lcoe(tmp_path)
    result = build_lcoe_maps("ZZZ", ["wind"], "none", CORE, **dirs)
    assert {k for k in result.rasters if "__" in k} == {
        "lcoe_nominal_wind__ssp126",
        "lcoe_nominal_wind__ssp370",
    }
    ssp126, _, _ = _read(result.rasters["lcoe_nominal_wind__ssp126"])
    ssp370, _, _ = _read(result.rasters["lcoe_nominal_wind__ssp370"])
    # m_a (+10) and m_b (+30) give a median of +20; m_c (+50) alone for SSP3-7.0; m_d is in the other window
    np.testing.assert_allclose(ssp126, (base + 20.0).reshape(2, 3), rtol=1e-6)
    np.testing.assert_allclose(ssp370, (base + 50.0).reshape(2, 3), rtol=1e-6)
    assert slug("SSP1-2.6") == "ssp126"


@pytest.mark.unit
@pytest.mark.parametrize("mode", ["none", "summary", "all"])
def test_the_lcoe_figures_follow_the_figures_setting(tmp_path, mode):
    _, _, dirs = _stage_lcoe(tmp_path)
    result = build_lcoe_maps("ZZZ", ["wind"], mode, CORE, **dirs)
    # all: 4 statistics, 2 SSPs and the supply curve = 7 figures (the nominal map at m0 among them)
    assert len(result.figures) == {"none": 0, "summary": 1, "all": 7}[mode]
    assert all(p.is_file() for p in result.figures)
    if mode == "summary":
        assert result.figures[0].name == "lcoe_nominal_wind__ref__na__na.png"


@pytest.mark.unit
def test_the_lcoe_maps_run_at_the_coarse_scale_with_the_same_code(tmp_path):
    _, _, dirs = _stage_lcoe(tmp_path)
    with use_scale("0p1deg"):
        result = build_lcoe_maps("ZZZ", ["wind"], "none", CORE, **dirs)
    _, transform, _ = _read(result.rasters["lcoe_nominal_wind"])
    assert transform.a == pytest.approx(0.1)


@pytest.mark.unit
def test_the_lcoe_maps_refuse_an_unknown_mode_a_missing_table_and_a_window_without_members(
    tmp_path,
):
    _, _, dirs = _stage_lcoe(tmp_path)
    with pytest.raises(MapError, match="figures must be one of"):
        build_lcoe_maps("ZZZ", ["wind"], "some", CORE, **dirs)
    with pytest.raises(MapError, match="no member of the core window"):
        build_lcoe_maps("ZZZ", ["wind"], "none", "2099-2100", **dirs)
    (dirs["lcoe_dir"] / "supply_curve_wind.parquet").unlink()
    with pytest.raises(MapError, match="missing input"):
        build_lcoe_maps("ZZZ", ["wind"], "none", CORE, **dirs)


# -- robustness maps --------------------------------------------------------------------------------------


@pytest.mark.unit
def test_the_robustness_rasters_hold_the_f7_columns_and_the_class_codes(tmp_path):
    entry, out, _ = _run(tmp_path)
    windows = {"core": CORE, "sensitivity": "2071-2100"}
    result = build_robustness_maps(
        "ZZZ", ["wind"], "none", windows, robustness_dir=out, figures_dir=tmp_path / "figs"
    )
    assert set(result.rasters) == {f"{m}_wind__{r}" for m in MAPS for r in windows}
    table = pd.read_parquet(entry.windows["core"].tables["robustness"])
    data, transform, nodata = _read(result.rasters["max_regret_wind__core"])
    row = table.iloc[3]
    cell_row, cell_col = row_col_from_id(int(row["cell_id"]))
    top = round((CELL_ORIGIN_LAT - transform.f) / 0.05)
    left = round((transform.c - CELL_ORIGIN_LON) / 0.05)
    assert data[int(cell_row) - top, int(cell_col) - left] == pytest.approx(row["mr"], rel=1e-5)
    classes, _, _ = _read(result.rasters["cell_class_wind__core"])
    assert set(np.unique(classes[classes != nodata])) <= set(map(float, CLASS_CODES.values()))
    flags, _, _ = _read(result.rasters["topk_robust_wind__core"])
    assert set(np.unique(flags[flags != nodata])) <= {0.0, 1.0}


@pytest.mark.unit
@pytest.mark.parametrize("mode", ["none", "summary", "all"])
def test_the_robustness_figures_follow_the_figures_setting_and_skip_maps_without_values(
    tmp_path, mode
):
    _, out, _ = _run(tmp_path)
    result = build_robustness_maps(
        "ZZZ", ["wind"], mode, {"core": CORE}, robustness_dir=out, figures_dir=tmp_path / "figs"
    )
    names = {p.name for p in result.figures}
    summary = {f"{m}_wind__{CORE}__na__na.png" for m, v in MAPS.items() if v[3]}
    if mode == "none":
        assert names == set()
    elif mode == "summary":
        assert names == summary
    else:
        assert summary <= names and len(names) == len(MAPS)
    assert all(p.is_file() for p in result.figures)


@pytest.mark.unit
def test_the_robustness_maps_refuse_an_unknown_mode_and_a_missing_table(tmp_path):
    with pytest.raises(MapError, match="figures must be one of"):
        build_robustness_maps("ZZZ", ["wind"], "some", {"core": CORE}, robustness_dir=tmp_path)
    with pytest.raises(MapError, match="missing input"):
        build_robustness_maps("ZZZ", ["wind"], "none", {"core": CORE}, robustness_dir=tmp_path)
