"""Display resolution of the maps (COMMAND 67b): pixels per cell, the finer display layer, the masked smoothing, the aggregation checks of the
0.01 degree layers, and what never changes with the option (classes, categories, states). Nothing here is a result."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from matplotlib.colors import ListedColormap, Normalize
from pydantic import ValidationError

from geofrea.core.config_schemas import AbsoluteMapsConfig
from geofrea.technical_potential import display_layers as dl
from geofrea.technical_potential.cf_models import CfSettings, PvoutWithTemperature
from geofrea.viz import display
from geofrea.viz import mapstyle as ms
from geofrea.viz.examples import ARCHETYPES, archetype_country, archetype_figure, fine_layer

pytestmark = pytest.mark.unit

CONTINUOUS = ("density", "capacity_factor", "forcing")


@pytest.fixture(scope="module")
def countries():
    return {}


def _country(countries, iso):
    if iso not in countries:
        countries[iso] = archetype_country(iso)
    return countries[iso]


def _pixels(canvas) -> np.ndarray:
    canvas.fig.canvas.draw()
    return np.asarray(canvas.fig.canvas.buffer_rgba()).copy()


# ------------------------------------------------------------------------------------------------------------------- the smoothing


def test_smoothing_is_a_convex_combination_and_never_leaks_the_no_data_fill():
    rng = np.random.default_rng(1)
    grid = rng.uniform(5.0, 9.0, (12, 14))
    grid[4:8, 5:9] = np.nan  # a hole of no-data
    grid[:, 0] = np.nan
    out = display.smooth_masked(grid, 6)
    assert out.shape == (72, 84)
    values = out[np.isfinite(out)]
    assert values.min() >= 5.0 - 1e-9 and values.max() <= 9.0 + 1e-9, (
        "a value outside the data (0 leaked in)"
    )
    # the border between data and no-data stays at the edge of the cells: the middle of the hole and the empty column are still empty
    assert np.isnan(out[4 * 6 + 2 : 8 * 6 - 2, 5 * 6 + 2 : 9 * 6 - 2]).all()
    assert np.isnan(out[:, :3]).all()
    # and every data cell keeps its value at its own centre within the range of its neighbours
    assert np.isfinite(out[10 * 6 + 3, 10 * 6 + 3])


def test_smoothing_of_a_constant_field_is_that_constant_and_a_factor_of_one_is_the_identity():
    grid = np.full((5, 7), 3.5)
    grid[2, 3] = np.nan
    out = display.smooth_masked(grid, 4)
    assert np.allclose(out[np.isfinite(out)], 3.5)
    same = display.smooth_masked(grid, 1)
    assert np.array_equal(np.isnan(same), np.isnan(grid)) and np.allclose(
        same[~np.isnan(grid)], 3.5
    )
    with pytest.raises(ValueError):
        display.smooth_masked(grid, 0)


def test_the_rule_smooths_only_continuous_fields_above_four_pixels_a_gcm_field_or_never_when_off():
    assert display.needs_smoothing(4.1, continuous=True)
    assert not display.needs_smoothing(4.0, continuous=True)
    assert not display.needs_smoothing(30.0, continuous=False)  # classes, categories, states
    assert not display.needs_smoothing(30.0, continuous=True, mode="off")
    assert display.needs_smoothing(1.0, continuous=True, coarse_source=True)
    assert not display.needs_smoothing(1.0, continuous=True, mode="off", coarse_source=True)
    with pytest.raises(ValueError):
        display.needs_smoothing(1.0, True, mode="bilinear")


def test_an_image_of_classes_is_refused_by_the_smoothing(countries):
    c = _country(countries, "PRT")
    canvas = ms.new_map(c.geometry, iso="PRT", technology="Solar PV", variable="Classes")
    with pytest.raises(ValueError, match="never smoothed"):
        canvas.draw_raster(np.zeros((4, 4, 4)), c.grid_extent, smooth=4)


def test_the_smoothed_raster_has_no_colour_outside_the_country_or_inside_a_hole(countries):
    """One colour over a grid with a hole of no-data: with smoothing, no pixel of that colour outside the country or in the middle of the hole."""
    c = _country(countries, "PRT")
    canvas = ms.new_map(
        c.geometry,
        iso="PRT",
        technology="Solar PV",
        variable="Capacity density",
        graticule=False,
        no_data_label=ms.NO_DATA_LABEL,
    )
    canvas.fill_country()
    west, east, south, north = c.grid_extent
    grid = np.ones((round((north - south) / 0.05), round((east - west) / 0.05)))
    r0, r1 = grid.shape[0] // 2 - 4, grid.shape[0] // 2 + 4
    k0, k1 = grid.shape[1] // 2 - 3, grid.shape[1] // 2 + 3
    grid[r0:r1, k0:k1] = np.nan
    canvas.draw_raster(
        grid, c.grid_extent, cmap=ListedColormap([(1.0, 0.0, 1.0)]), norm=Normalize(0, 2), smooth=5
    )
    rgba = _pixels(canvas)
    bb = canvas.ax.get_window_extent()
    height = rgba.shape[0]
    cols = np.arange(int(bb.x0) + 1, int(bb.x1) - 1)
    rows = np.arange(int(height - bb.y1) + 1, int(height - bb.y0) - 1)
    px, py = np.meshgrid(cols + 0.5, height - (rows + 0.5))
    x, y = canvas.ax.transData.inverted().transform(np.column_stack([px.ravel(), py.ravel()])).T
    block = rgba[np.ix_(rows, cols)][..., :3] / 255.0
    painted = (np.abs(block - np.array([1.0, 0.0, 1.0])).max(axis=2) < 0.06).ravel()
    import shapely

    metres_per_px = canvas.frame.width_m / (bb.x1 - bb.x0)
    assert (
        painted & ~shapely.contains_xy(canvas.frame.polygon.buffer(1.5 * metres_per_px), x, y)
    ).sum() == 0
    # the middle of the hole (its rows and columns, one cell in from the edge) is not painted
    lon, lat = canvas.frame.inverse.transform(x, y)
    hole = (
        (lon > west + (k0 + 1) * 0.05)
        & (lon < west + (k1 - 1) * 0.05)
        & (lat < north - (r0 + 1) * 0.05)
        & (lat > north - (r1 - 1) * 0.05)
    )
    inside = shapely.contains_xy(canvas.frame.polygon.buffer(-2 * metres_per_px), x, y)
    assert (hole & inside).sum() > 500 and not painted[hole & inside].any()


# ---------------------------------------------------------------------------------------------------- pixels per cell and the figure


@pytest.mark.parametrize("iso", list(ARCHETYPES))
@pytest.mark.parametrize("kind", CONTINUOUS)
def test_a_cell_is_at_most_four_pixels_or_the_subtitle_declares_the_smoothing(iso, kind, countries):
    canvas = archetype_figure(_country(countries, iso), kind)
    subtitle = canvas.texts["subtitle"].get_text().replace("\n", " ")
    px = float(canvas.meta["display_px_per_cell"])
    smoothed = canvas.meta["display_smoothing"] == "applied"
    assert px <= display.MAX_PX_PER_CELL or smoothed, (
        f"{iso} {kind}: {px:.1f} px per cell, not smoothed"
    )
    assert smoothed == ("display smoothing" in subtitle)
    if smoothed:
        assert "source:" in subtitle and (
            "0.01° display layer" in subtitle or "0.05° analysis grid" in subtitle
        )
    assert canvas.meta["display_source"]
    # the limits are in the metadata, not in the subtitle; the subtitle says only the kind of scale, and only when it cuts
    assert "truncated" not in subtitle and "clipped to" not in subtitle
    canvas.fig.clf()


def test_a_small_country_draws_the_fine_layer_and_a_tiny_one_is_smoothed_too(countries):
    prt = archetype_figure(_country(countries, "PRT"), "density")
    assert (
        prt.meta["display_source"] == "0.01° display layer"
        and prt.meta["display_smoothing"] == "none"
    )
    assert float(prt.meta["display_px_per_cell"]) <= 4.0
    lux = archetype_figure(_country(countries, "LUX"), "density", "article_single")
    assert (
        lux.meta["display_smoothing"] == "applied"
        and "0.01° display layer" in lux.meta["resolution"]
    )
    assert (
        float(lux.meta["display_px_per_cell"]) > 4.0
    )  # still a block at 0.01 degree: interpolated
    che = archetype_figure(_country(countries, "CHE"), "forcing", "article_single")
    assert (
        che.meta["display_smoothing"] == "applied"
        and "0.05° analysis grid" in che.meta["resolution"]
    )
    bra = archetype_figure(_country(countries, "BRA"), "capacity_factor")
    assert bra.meta["display_smoothing"] == "none" and float(bra.meta["display_px_per_cell"]) < 4.0


def test_the_option_off_draws_the_cells_as_they_are(countries):
    c = _country(countries, "LUX")
    off = archetype_figure(c, "density", "article_single", display_smoothing="off")
    assert off.meta["display_smoothing"] == "off"
    assert "display smoothing" not in off.texts["subtitle"].get_text().replace("\n", " ")
    coarse = archetype_figure(c, "density", "article_single", fine=False, display_smoothing="off")
    assert coarse.meta["display_source"] == "0.05° analysis grid"


def test_classes_categories_and_states_are_identical_with_and_without_the_option(countries):
    for iso, kind in (
        ("PRT", "eligibility"),
        ("LUX", "eligibility"),
        ("IDN", "state"),
        ("CHE", "state"),
    ):
        c = _country(countries, iso)
        a = archetype_figure(c, kind, display_smoothing="auto")
        left = _pixels(a)
        a.fig.clf()
        b = archetype_figure(c, kind, display_smoothing="off")
        right = _pixels(b)
        b.fig.clf()
        assert np.array_equal(left, right), f"{iso} {kind} changes with the option"


def test_the_scale_is_in_the_metadata_and_the_subtitle_is_short(countries):
    canvas = archetype_figure(_country(countries, "BRA"), "capacity_factor")
    assert canvas.meta["scale_limits"].count(",") == 1 and canvas.meta["scale_mode"] == "fixed"
    info = ms.resolve_scale(np.array([1.0, 2.0, 30.0]), ms.ScaleSpec("fixed", (0.0, 10.0)))
    assert ms.clip_note(info) == "Scale: fixed"
    pct = ms.resolve_scale(np.linspace(0, 100, 1000), ms.ScaleSpec("percentile"))
    assert ms.clip_note(pct) == "Scale: 2nd–98th percentile"
    shared = ms.resolve_scale(np.array([0.0, 5.0, 40.0]), ms.ScaleSpec("shared", (0.0, 10.0)))
    assert ms.clip_note(shared) == "Scale: shared"
    assert (
        ms.clip_note(ms.resolve_scale(np.array([1.0, 2.0]), ms.ScaleSpec("fixed", (0.0, 10.0))))
        == ""
    )
    assert (
        ms.smoothing_note("0.05° analysis grid")
        == "display smoothing (source: 0.05° analysis grid)"
    )


# ----------------------------------------------------------------------------------------------------------------------- neighbours


def test_neighbours_are_cut_by_the_rectangle_of_the_map_not_by_a_buffer(countries):
    c = _country(countries, "CHE")
    canvas = ms.new_map(
        c.geometry,
        iso="CHE",
        technology="Solar PV",
        variable="Capacity density",
        neighbours=c.neighbours,
    )
    near = ms._neighbours_in_frame(c.neighbours, canvas.frame)
    xmin, xmax, ymin, ymax = canvas.frame.bounds
    assert len(near) > 0
    for geom in near.geometry:
        gx0, gy0, gx1, gy1 = geom.bounds
        assert (
            gx0 >= xmin - 1e-6 and gx1 <= xmax + 1e-6 and gy0 >= ymin - 1e-6 and gy1 <= ymax + 1e-6
        )
    # reaching the sides of the rectangle: a buffer round the country would stop short of them
    reach = max(g.bounds[2] for g in near.geometry)
    assert reach > xmax - 0.05 * (xmax - xmin)
    assert near["gap"].dtype == bool and near["gap"].sum() == 1


# --------------------------------------------------------------------------------------------------------------------- synthetic data


def test_the_synthetic_fields_are_spatially_correlated_not_noise_per_cell(countries):
    c = _country(countries, "PRT")
    for field in (c.cf, c.grid):
        both = np.isfinite(field[:, 1:]) & np.isfinite(field[:, :-1])
        a, b = field[:, 1:][both], field[:, :-1][both]
        assert np.corrcoef(a, b)[0, 1] > 0.85, "neighbouring cells are nearly independent"
    fine = fine_layer(c, "capacity_factor")
    assert fine is not None and fine.cell_deg == pytest.approx(0.01)
    both = np.isfinite(fine.grid[:, 1:]) & np.isfinite(fine.grid[:, :-1])
    assert np.corrcoef(fine.grid[:, 1:][both], fine.grid[:, :-1][both])[0, 1] > 0.9
    assert fine_layer(c, "forcing") is None and fine_layer(c, "eligibility") is None
    assert fine_layer(_country(countries, "BRA"), "density") is None  # too large to be worth it


def test_the_fine_layer_is_the_same_field_as_the_cells(countries):
    c = _country(countries, "PRT")
    fine = fine_layer(c, "capacity_factor")
    mean = display.block_mean(fine.grid, 5)
    both = np.isfinite(mean) & np.isfinite(c.cf)
    assert both.sum() > 0.9 * np.isfinite(c.cf).sum()
    assert np.abs(mean[both] - c.cf[both]).max() < 0.05  # the noise of a pixel, not another field


# ------------------------------------------------------------------------------------------ the display layers of the potential (step 3)


def _inputs(k=5, rows=6, cols=7, seed=3):
    rng = np.random.default_rng(seed)
    fine = (rows * k, cols * k)
    pvout = (
        4.0 + 1.2 * np.sin(np.linspace(0, 3, fine[1]))[None, :] + 0.05 * rng.standard_normal(fine)
    )
    fraction = np.clip(rng.uniform(0.0, 1.0, fine) * (rng.uniform(size=fine) > 0.2), 0, 1)
    area = np.full(fine, 0.9)
    cf_fine = pvout / 24.0
    analysis_cf = display.block_mean(cf_fine, k, area * fraction)
    elig = display.block_sum(area * fraction, k)
    cell_area = display.block_sum(area, k)
    density = 80.0 * elig / cell_area
    analysis_cf[0, 0] = np.nan  # a cell that F5 did not retain
    settings = CfSettings({"gamma": -0.004}, None, None, ["pvout"], 1.225, 298.15, 24.0)
    return {
        "model": PvoutWithTemperature(),
        "settings": settings,
        "resources": {"pvout": pvout},
        "eligible_fraction": fraction,
        "pixel_area_km2": area,
        "extent": (-8.0, -7.65, 40.0, 40.3),
        "analysis_cf": analysis_cf,
        "analysis_eligible_area_km2": elig,
        "analysis_capacity_density": np.where(np.isfinite(analysis_cf), density, np.nan),
        "capacity_density_mw_km2": 80.0,
        "cell_area_km2": cell_area,
        "k": k,
    }


def test_the_display_layers_aggregate_back_to_the_analysis_cell():
    build = dl.build_display_layers(**_inputs())
    names = {c.name: c for c in build.checks}
    assert set(names) == {"capacity-factor", "eligible-area", "capacity-density"}
    assert all(c.ok for c in build.checks)
    assert (
        names["capacity-factor"].max_rel_diff <= 0.01
        and names["eligible-area"].max_rel_diff <= 1e-6
    )
    assert set(build.layers) == set(dl.LAYERS) and all(
        l.cell_deg == pytest.approx(0.01) for l in build.layers.values()
    )
    cf = build.layers["capacity-factor"].grid
    assert np.isnan(cf[:5, :5]).all(), "a pixel of a cell that F5 did not retain has no value"
    assert np.nanmin(cf) > 0 and np.nanmax(cf) < 0.5
    energy = build.layers["energy-density"].grid
    cap = build.layers["capacity-density"].grid
    ok = np.isfinite(energy)
    assert np.allclose(energy[ok], cap[ok] * cf[ok] * 8.76)


def _wind_inputs(k=5, rows=4, cols=5, seed=11):
    """Wind pixels and the analysis side computed by the F5 route (`prepare_pixels`: the model per pixel, then the eligible-area mean)."""
    from geofrea.core.constants import ISA_T0_K, RHO0_KG_M3
    from geofrea.technical_potential.cf_models import WeibullWithAirDensity
    from geofrea.technical_potential.pixel_inputs import CellPixels
    from geofrea.technical_potential.power_curve import load_power_curve

    curve = load_power_curve(
        Path(__file__).resolve().parents[1] / "fixtures" / "power_curves" / "synthetic_curve.yaml"
    )
    rng = np.random.default_rng(seed)
    fine = (rows * k, cols * k)
    layers = {}
    for h, f in ((100, 1.0), (150, 1.06), (200, 1.1)):
        layers[f"weibull_a_{h}m"] = f * (7.5 + 2.5 * rng.random(fine))
        layers[f"weibull_k_{h}m"] = 1.8 + 0.8 * rng.random(fine)
        layers[f"air_density_{h}m"] = 1.2 - 0.12 * rng.random(fine)
    fraction = np.clip(rng.uniform(0.0, 1.0, fine) * (rng.uniform(size=fine) > 0.2), 0, 1)
    area = np.full(fine, 0.9)
    settings = CfSettings(
        {"eta_loss": 0.85, "hub_height_m": 125.0}, curve, None, list(layers), RHO0_KG_M3, ISA_T0_K, 24.0
    )
    weight = area * fraction
    def blocks(a):
        return a.reshape(rows, k, cols, k).transpose(0, 2, 1, 3).reshape(rows * cols, k * k)

    w, usable = blocks(weight), blocks(weight) > 0
    has = usable.any(axis=1)
    pixels = CellPixels(
        offsets=np.concatenate([[0], np.cumsum(usable[has].sum(axis=1))]).astype("int64"),
        weight_km2=w[has][usable[has]],
        resources={n: blocks(g)[has][usable[has]] for n, g in layers.items()},
    )
    candidates = pd.DataFrame(index=np.arange(int(has.sum())))
    for name, grid in layers.items():  # cell means, as F3 writes them (they feed the flags only)
        candidates[name] = (blocks(grid)[has] * w[has]).sum(axis=1) / w[has].sum(axis=1)
    model = WeibullWithAirDensity()
    prepared = model.prepare_pixels(candidates, settings, pixels)
    n = len(candidates)
    cell_cf = prepared.member(np.arange(n), np.ones(n), np.zeros(n), np.ones(n))
    analysis_cf = np.full(rows * cols, np.nan)
    analysis_cf[has] = cell_cf
    analysis_cf = analysis_cf.reshape(rows, cols)
    elig = display.block_sum(weight, k)
    cell_area = display.block_sum(area, k)
    return {
        "model": model,
        "settings": settings,
        "resources": layers,
        "eligible_fraction": fraction,
        "pixel_area_km2": area,
        "extent": (-8.0, -7.75, 40.0, 40.2),
        "analysis_cf": analysis_cf,
        "analysis_eligible_area_km2": np.where(np.isfinite(analysis_cf), elig, np.nan),
        "analysis_capacity_density": np.where(np.isfinite(analysis_cf), 80.0 * elig / cell_area, np.nan),
        "capacity_density_mw_km2": 80.0,
        "cell_area_km2": cell_area,
        "k": k,
    }


def test_the_wind_capacity_factor_of_the_display_layer_aggregates_to_the_cell_exactly():
    """D-F5-038: F5 and the display evaluate the same model on the same pixels and weight them the same way, so the check is an identity."""
    build = dl.build_display_layers(**_wind_inputs())
    check = {c.name: c for c in build.checks}["capacity-factor"]
    assert check.ok and check.tolerance == dl.PIXEL_IDENTITY_TOLERANCE
    assert check.max_rel_diff < 1e-12


def test_a_wind_cell_that_is_half_a_percent_off_the_pixel_mean_is_refused_where_one_percent_used_to_pass():
    inputs = _wind_inputs()
    cf = inputs["analysis_cf"].copy()
    cf[1, 2] *= 1.005
    inputs["analysis_cf"] = cf
    with pytest.raises(dl.DisplayLayerError, match="capacity-factor"):
        dl.build_display_layers(**inputs)


def test_a_model_evaluated_on_the_cell_means_keeps_the_float32_tolerance():
    build = dl.build_display_layers(**_inputs())
    check = {c.name: c for c in build.checks}["capacity-factor"]
    assert check.tolerance == dl.EXACT_TOLERANCE


def test_a_layer_that_does_not_reproduce_the_analysis_is_refused():
    wrong_cf = _inputs()
    wrong_cf["analysis_cf"] = wrong_cf["analysis_cf"] * 1.05
    with pytest.raises(dl.DisplayLayerError, match="capacity-factor"):
        dl.build_display_layers(**wrong_cf)
    wrong_area = _inputs()
    wrong_area["analysis_eligible_area_km2"] = wrong_area["analysis_eligible_area_km2"] * 1.01
    with pytest.raises(dl.DisplayLayerError, match="eligible-area"):
        dl.build_display_layers(**wrong_area)
    misshaped = _inputs()
    misshaped["k"] = 4
    with pytest.raises(dl.DisplayLayerError):
        dl.build_display_layers(**misshaped)


def test_aggregation_check_reports_a_missing_cell_and_the_sum_mode():
    fine = np.ones((10, 10))
    analysis = np.ones((2, 2))
    analysis[0, 0] = np.nan
    assert not display.check_aggregation("x", fine, analysis, 5).ok
    assert display.check_aggregation(
        "x", fine, np.full((2, 2), 25.0), 5, how="sum", tolerance=1e-9
    ).ok
    with pytest.raises(ValueError):
        display.block_mean(np.ones((7, 7)), 5)


def test_the_layers_are_written_with_their_own_fingerprint_and_read_back(tmp_path):
    inputs = _inputs()
    build = dl.build_display_layers(**inputs)
    again = dl.build_display_layers(**inputs)
    assert build.fingerprint == again.fingerprint and len(build.fingerprint) == 16
    changed = _inputs(seed=4)
    assert dl.build_display_layers(**changed).fingerprint != build.fingerprint
    assert (
        dl.load_display_layer(tmp_path, "capacity-factor", "solar") is None
    )  # nothing built: the cells are drawn
    paths = dl.write_display_layers(tmp_path, "solar", build)
    record = json.loads(dl.meta_path(tmp_path, "solar").read_text(encoding="utf-8"))
    assert (
        record["fingerprint"] == build.fingerprint
        and record["display_only"]
        and all(c["ok"] for c in record["checks"])
    )
    assert all(p.name.startswith("display_") for p in paths.values())
    back = dl.load_display_layer(tmp_path, "capacity-factor", "solar")
    original = build.layers["capacity-factor"]
    assert back.grid.shape == original.grid.shape and back.cell_deg == pytest.approx(0.01)
    assert np.allclose(back.extent, original.extent)
    assert np.allclose(back.grid, original.grid, equal_nan=True, atol=1e-6)
    dl.meta_path(tmp_path, "solar").unlink()
    assert (
        dl.load_display_layer(tmp_path, "capacity-factor", "solar") is None
    )  # no record: not used


def test_no_analysis_artifact_is_a_display_layer():
    """The layers have their own names: nothing the analysis reads starts with `display_`."""
    assert all(
        name.startswith("display_")
        for name in (dl.display_path(".", n, "solar").name for n in dl.LAYERS)
    )
    assert not any(n.startswith("potential_") for n in dl.LAYERS)


# ---------------------------------------------------------------------------------------------------------------------------- config


def test_display_smoothing_is_auto_by_default_and_only_auto_or_off():
    base = {
        "per_cell_classes": {"method": "quantile", "classes": 7},
        "per_state": {
            "method": "fisher_jenks",
            "classes": 6,
            "basis": "central",
            "open_last_class": True,
        },
        "significant_figures": 2,
        "palette": "viridis",
    }
    assert AbsoluteMapsConfig(**base).display_smoothing == "auto"
    assert AbsoluteMapsConfig(**base, display_smoothing="off").display_smoothing == "off"
    with pytest.raises(ValidationError):
        AbsoluteMapsConfig(**base, display_smoothing="bilinear")


def test_the_experiments_file_carries_the_option():
    import yaml

    from geofrea.core import paths as core_paths  # noqa: F401  (the repo root is the config home)

    root = __import__("pathlib").Path(__file__).resolve().parents[2]
    data = yaml.safe_load((root / "config" / "experiments.yaml").read_text(encoding="utf-8"))
    assert data["absolute_maps"]["display_smoothing"] == "auto"


def test_pixels_per_cell_follow_the_latitude_and_the_pixel():
    assert display.px_per_cell(0.05, 0.0, 1000.0) == pytest.approx(
        0.05 * display.M_PER_DEG / 1000.0
    )
    assert display.px_per_cell(0.05, 60.0, 1000.0) < display.px_per_cell(0.05, 0.0, 1000.0)
    assert math.isfinite(display.px_per_cell(0.05, 89.9, 1000.0))
    assert display.upsample_factor(0.5, (10, 10)) == 2
    assert display.upsample_factor(7.2, (10, 10)) == 8
    assert display.upsample_factor(40.0, (4000, 4000)) < 40


def test_with_partial_only_the_layers_that_depend_on_a_failed_check_are_refused(tmp_path):
    wrong_cf = _inputs()
    wrong_cf["analysis_cf"] = wrong_cf["analysis_cf"] * 1.05
    build = dl.build_display_layers(**wrong_cf, partial=True)
    assert set(build.refused) == {"capacity-factor", "energy-density"}
    assert set(build.layers) == {"eligible-fraction", "capacity-density"}
    dl.write_display_layers(tmp_path, "t", build)
    record = json.loads(dl.meta_path(tmp_path, "t").read_text(encoding="utf-8"))
    assert set(record["refused"]) == {"capacity-factor", "energy-density"}
    assert dl.load_display_layer(tmp_path, "capacity-factor", "t") is None
    assert dl.load_display_layer(tmp_path, "capacity-density", "t") is not None
    wrong_area = _inputs()
    wrong_area["analysis_eligible_area_km2"] = wrong_area["analysis_eligible_area_km2"] * 1.01
    with pytest.raises(dl.DisplayLayerError):  # nothing is left
        dl.build_display_layers(**wrong_area, partial=True)


def test_a_country_that_does_not_need_the_fine_layer_leaves_no_stale_layer(tmp_path, monkeypatch):
    build = dl.build_display_layers(**_inputs())
    dl.write_display_layers(tmp_path, "t", build)
    monkeypatch.setattr(dl, "country_needs_fine_layer", lambda ctx, iso, cell_deg: (False, 1.6))
    assert (
        dl.ensure_display_layers(
            "ZZZ", "t", None, None, potential_dir=tmp_path, cells_dir=tmp_path, siting_dir=tmp_path
        )
        == "not needed"
    )
    assert dl.load_display_layer(tmp_path, "capacity-factor", "t") is None


def test_a_refusal_is_recorded_and_removes_the_rasters(tmp_path):
    dl.write_display_layers(tmp_path, "t", dl.build_display_layers(**_inputs()))
    dl.write_refusal(tmp_path, "t", "why", 11.8)
    assert dl.load_display_layer(tmp_path, "capacity-factor", "t") is None
    assert json.loads(dl.meta_path(tmp_path, "t").read_text(encoding="utf-8"))["refused"] == "why"


def test_the_display_layers_are_written_as_cloud_optimized_geotiffs(tmp_path):
    """R71-25: the display layers use the writer of every other raster, so they are COG (A-07) and keep their values."""
    import numpy as np
    import rasterio

    from geofrea.technical_potential.display_layers import (
        DisplayBuild,
        display_path,
        write_display_layers,
    )
    from geofrea.viz.display import DisplayLayer

    grid = np.full((300, 400), np.nan)
    grid[10:200, 20:300] = np.linspace(0.1, 0.4, 280)[None, :]
    layer = DisplayLayer("capacity-factor", grid, (-9.0, -5.0, 37.0, 40.0), 0.01)
    written = write_display_layers(
        tmp_path, "wind", DisplayBuild({"capacity-factor": layer}, [], "abc123")
    )
    path = display_path(tmp_path, "capacity-factor", "wind")
    assert written["capacity-factor"] == path
    with rasterio.open(path) as src:
        assert src.profile["tiled"]
        assert src.tags(ns="IMAGE_STRUCTURE").get("LAYOUT") == "COG"
        back = src.read(1)
        assert src.nodata == -9999.0
    np.testing.assert_allclose(
        np.where(back == -9999.0, np.nan, back), grid.astype("float32"), equal_nan=True
    )
