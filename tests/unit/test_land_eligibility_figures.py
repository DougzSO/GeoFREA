"""The figures of the land eligibility (`land_eligibility/figures.py`, COMMAND 68; spec v2 T-10): the dominant exclusion and its rule, the
denominator, the colours of the exclusions, the layout that follows the country, the chart of the contributions and the files."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin

from geofrea.land_eligibility import figures as F
from geofrea.land_eligibility.cells import cell_id, row_col_from_id
from geofrea.viz import display
from geofrea.viz import mapstyle as ms
from geofrea.viz.context import MapContext, country_geometry, lattice_of_extent
from geofrea.viz.panels import adaptive_grid

pytestmark = pytest.mark.unit

ISO = "ZZZ"


def _cells(n_rows=6, n_cols=8, seed=3):
    rows, cols = np.meshgrid(np.arange(n_rows) + 1000, np.arange(n_cols) + 2000, indexing="ij")
    ids = cell_id(rows.ravel(), cols.ravel())
    rng = np.random.default_rng(seed)
    k = len(ids)
    area = np.full(k, 30.0)
    excluded = {f"excluded_area_km2_E{i}": rng.uniform(0, 10, k) for i in range(1, 7)}
    return pd.DataFrame(
        {
            "cell_id": ids,
            "row": rows.ravel(),
            "col": cols.ravel(),
            "cell_area_km2": area,
            "eligible_area_km2": rng.uniform(0, 30, k),
            **excluded,
        }
    )


def _context(cells):
    polygon = country_geometry(None, cells["cell_id"].to_numpy())
    return MapContext(polygon, ms.country_extent(polygon, contiguous=False), None)


# --------------------------------------------------------------------------------------------------------------------------- dominant


def test_the_dominant_exclusion_is_the_largest_area_the_lower_number_wins_a_tie_and_none_is_zero():
    cells = _cells(1, 4)
    for code in F.EXCLUSION_NAMES:
        cells[f"excluded_area_km2_{code}"] = 0.0
    cells.loc[0, "excluded_area_km2_E3"] = 5.0  # E3 alone
    cells.loc[1, ["excluded_area_km2_E2", "excluded_area_km2_E5"]] = 4.0  # a tie: E2 wins
    cells.loc[2, "excluded_area_km2_E6"] = 1.0
    cells.loc[2, "excluded_area_km2_E1"] = 0.5
    # the cell 3 has no excluded area: None
    assert F.dominant_codes(cells).tolist() == [3, 2, 6, 0]
    assert F.CLASS_LABELS[0] == "None" and F.CLASS_LABELS[3] == "E3 riparian setback"
    assert len(F.class_colours()) == len(F.CLASS_LABELS) == 7


def test_a_cell_table_without_an_exclusion_column_is_refused_by_name():
    cells = _cells().drop(columns="excluded_area_km2_E4")
    with pytest.raises(ValueError, match="excluded_area_km2_E4"):
        F.dominant_codes(cells)


def test_the_eligible_share_has_the_land_area_of_the_cell_as_its_denominator():
    cells = _cells(1, 2)
    cells["cell_area_km2"] = [20.0, 40.0]
    cells["eligible_area_km2"] = [5.0, 40.0]
    assert F.eligible_share(cells).tolist() == [0.25, 1.0]


def test_the_exclusion_shares_add_up_to_one_hundred_for_each_technology():
    tables = {"solar": _cells(seed=1), "wind": _cells(seed=2)}
    shares = F.exclusion_shares(tables)
    assert set(shares) == set(F.EXCLUSION_NAMES)
    for k in range(2):
        assert sum(shares[c][k] for c in F.EXCLUSION_NAMES) == pytest.approx(100.0)
    assert all(v > 0 for values in shares.values() for v in values)


def test_the_layout_follows_the_shape_of_the_country():
    assert adaptive_grid(2, 2.2) == (1, 2)  # a tall country: side by side
    assert adaptive_grid(2, 0.4) == (2, 1)  # a wide one: one above the other


# ----------------------------------------------------------------------------------------------------------------------------- the files


@pytest.fixture(scope="module")
def drawn(tmp_path_factory):
    out = tmp_path_factory.mktemp("f3")
    tables = {"solar": _cells(seed=1), "wind": _cells(seed=2)}
    ctx = _context(tables["solar"])
    files = F.draw_country(ISO, tables, ctx, out)
    return out, files


def test_one_sheet_per_technology_a_chart_and_a_map_of_each_exclusion_are_written(drawn):
    out, files = drawn
    names = sorted(p.name for p in files)
    assert f"{ISO}_F3_land-eligibility_solar_central.png" in names
    assert f"{ISO}_F3_land-eligibility_wind_central.png" in names
    assert f"{ISO}_F3_exclusion-contribution_central.png" in names
    layers = sorted(p.name for p in (out / "layers").glob("*.png"))
    assert len(layers) == 12 and f"{ISO}_F3_excluded-share_E5-land-cover_wind_central.png" in layers
    assert all(ms.validate_filename(p.name) for p in files)
    assert (out / "figures_index.json").exists() and (
        out / "layers" / "figures_index.json"
    ).exists()


def test_the_sheet_declares_the_denominator_and_the_rule_of_the_dominant_exclusion(drawn):
    out, _ = drawn
    meta = ms.read_png_metadata(out / f"{ISO}_F3_land-eligibility_solar_central.png")
    assert meta["Title"].endswith("Solar · Land eligibility")
    assert meta["geofrea_denominator"] == "land area of the cell"
    assert "ties to the lower number" in meta["geofrea_dominant_rule"]
    assert meta["geofrea_scale_limits"] == "0,1" and meta["geofrea_scale_mode"] == "fixed"
    assert "OQ" not in meta["Title"] + meta["Description"]  # an open question is not in a title


def test_the_chart_and_the_diagnostic_maps_say_what_they_are(drawn):
    out, _ = drawn
    chart = ms.read_png_metadata(out / f"{ISO}_F3_exclusion-contribution_central.png")
    assert "Contribution of each exclusion" in chart["Title"]
    assert "overlap" in chart["Description"]
    assert chart["geofrea_denominator"] == "sum of the excluded areas of E1 to E6"
    layer = ms.read_png_metadata(
        out / "layers" / f"{ISO}_F3_excluded-share_E1-protected_solar_central.png"
    )
    assert layer["geofrea_status"] == "diagnostic" and "Diagnostic" in layer["Description"]


# ------------------------------------------------------------------------------------------------------------------------- the fine layer


def _fraction_tif(path, cells, k=5, deviation=0.0):
    ids = cells["cell_id"].to_numpy()
    rows, cols = row_col_from_id(ids)
    cell = 0.05
    r0, c0 = rows.min(), cols.min()
    n_r, n_c = rows.max() - r0 + 1, cols.max() - c0 + 1
    share = np.zeros((n_r, n_c))
    share[rows - r0, cols - c0] = (cells["eligible_area_km2"] / cells["cell_area_km2"]).to_numpy()
    fine = np.kron(share, np.ones((k, k))) + deviation
    west, north = -180.0 + c0 * cell, 90.0 - r0 * cell
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=fine.shape[0],
        width=fine.shape[1],
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(west, north, cell / k, cell / k),
        nodata=-9999.0,
    ) as dst:
        dst.write(fine.astype("float32"), 1)
    return path


def test_the_fine_layer_is_drawn_when_it_agrees_with_the_cells_and_left_out_when_it_does_not(
    tmp_path, caplog
):
    cells = _cells()
    ctx = _context(cells)
    good = _fraction_tif(tmp_path / "eligible_fraction_solar.tif", cells)
    layer = F.read_fraction_layer(good)
    assert layer.cell_deg == pytest.approx(0.01) and lattice_of_extent(layer.extent).shape == (6, 8)
    assert F.check_fraction_layer(layer, cells).ok
    out = tmp_path / "ok"
    F.draw_country(ISO, {"solar": cells}, ctx, out, tmp_path, with_layers=False)
    meta = ms.read_png_metadata(out / f"{ISO}_F3_land-eligibility_solar_central.png")
    assert meta["geofrea_display_source"] == "0.01° display layer"

    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    _fraction_tif(bad_dir / "eligible_fraction_solar.tif", cells, deviation=0.2)
    assert not F.check_fraction_layer(
        F.read_fraction_layer(bad_dir / "eligible_fraction_solar.tif"), cells
    ).ok
    out2 = tmp_path / "out2"
    F.draw_country(ISO, {"solar": cells}, ctx, out2, bad_dir, with_layers=False)
    meta2 = ms.read_png_metadata(out2 / f"{ISO}_F3_land-eligibility_solar_central.png")
    assert meta2["geofrea_display_source"] == "0.05° analysis grid"
    assert "differs from the cells" in caplog.text
    assert display.MAX_PX_PER_CELL == 4.0
